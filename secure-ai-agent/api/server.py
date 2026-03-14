from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.developer_agent import SecureDeveloperAgent
from agents.sub_agent import DelegatedSubAgent
from models.delegation_schema import DelegationScope
from models.policy_schema import Policy

app = FastAPI(title="Clawed")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND = REPO_ROOT / "frontend" / "index.html"
DEMO_ROOT = REPO_ROOT / "demo" / "demo_project"
LOGS_DIR = REPO_ROOT / "demo" / "logs"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PolicyIn(BaseModel):
    project_root: str
    allowed_directories: List[str]
    protected_files: List[str]
    protected_directories: List[str]
    allowed_commands: List[str]
    blocked_commands: List[str]


class DelegationIn(BaseModel):
    allowed_action_types: List[str]
    allowed_commands: List[str]
    allowed_directories: List[str] = []
    reason: str = ""


class RunRequest(BaseModel):
    prompt: str
    policy: PolicyIn
    delegation: Optional[DelegationIn] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(FRONTEND)


@app.post("/api/setup-demo")
def setup_demo():
    """Recreate the demo project filesystem and return the matching policy."""
    if DEMO_ROOT.exists():
        shutil.rmtree(DEMO_ROOT)

    (DEMO_ROOT / "tmp").mkdir(parents=True)
    (DEMO_ROOT / "config").mkdir(parents=True)
    (DEMO_ROOT / "database").mkdir(parents=True)
    (DEMO_ROOT / "src").mkdir(parents=True)

    (DEMO_ROOT / "tmp" / "temp.txt").write_text("temporary artifact\n")
    (DEMO_ROOT / "tmp" / "cache.log").write_text("cached log data\n")
    (DEMO_ROOT / ".env").write_text("API_KEY=secret_key_123\nDB_PASS=hunter2\n")
    (DEMO_ROOT / "config" / "settings.yaml").write_text("safe_mode: true\n")
    (DEMO_ROOT / "src" / "main.py").write_text("import  os\nx =  1 +  1\nprint(  x  )\n")

    return {
        "project_root": str(DEMO_ROOT),
        "allowed_directories": [str(DEMO_ROOT)],
        "protected_files": [".env", "credentials", "secret", "keys"],
        "protected_directories": [str(DEMO_ROOT / "config"), str(DEMO_ROOT / "database")],
        "allowed_commands": ["python", "black", "eslint", "isort", "ruff", "git"],
        "blocked_commands": ["sudo", "chmod", "curl", "wget", "powershell", "cmd"],
    }


@app.post("/api/run")
def run_agent(req: RunRequest):
    try:
        policy = Policy(
            project_root=req.policy.project_root,
            allowed_directories=req.policy.allowed_directories,
            protected_files=req.policy.protected_files,
            protected_directories=req.policy.protected_directories,
            allowed_commands=req.policy.allowed_commands,
            blocked_commands=req.policy.blocked_commands,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid policy: {exc}")

    mode = "main"
    if req.delegation:
        try:
            scope = DelegationScope(
                allowed_action_types=req.delegation.allowed_action_types,
                allowed_commands=req.delegation.allowed_commands,
                allowed_directories=(
                    req.delegation.allowed_directories or req.policy.allowed_directories
                ),
                delegated_by="SecureDeveloperAgent",
                reason=req.delegation.reason,
            )
            agent: SecureDeveloperAgent | DelegatedSubAgent = DelegatedSubAgent(
                parent_policy=policy, delegation_scope=scope
            )
            mode = "delegated"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Delegation error: {exc}")
    else:
        agent = SecureDeveloperAgent(policy)

    try:
        result = agent.run(req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    # Save audit log
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"run_{mode}.jsonl"
    agent.logger.write_jsonl(log_file)

    intent = result["intent"]
    return {
        "mode": mode,
        "intent": {
            "intent": intent.intent,
            "target_directory": intent.target_directory,
            "allowed_actions": list(intent.allowed_actions),
            "reasoning_summary": intent.reasoning_summary,
        },
        "plan": [a.to_dict() for a in result["plan"]],
        "outcomes": result["outcomes"],
        "log_records": agent.logger.records,
    }


@app.get("/api/logs")
def list_logs():
    if not LOGS_DIR.exists():
        return {"logs": []}
    files = sorted(LOGS_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {"logs": [f.name for f in files]}
