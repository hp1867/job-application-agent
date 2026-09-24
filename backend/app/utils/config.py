from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
def now():
    return datetime.now(timezone.utc).isoformat()
def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default
def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        tmp = f.name
    os.replace(tmp, path)
def env_values(root=ROOT):
    values = {}
    path = Path(root) / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return {**values, **os.environ}
def settings(root=ROOT):
    from .answer_memory import revisions
    env = env_values(root)
    prefs = read_json(Path(root)/"data/job_preferences.json", {})
    return {"dry_run": env.get("DRY_RUN", "true").lower() != "false",
            "post_submission_enabled": post_submission_enabled(root),
            "production_approved": env.get("PRODUCTION_APPROVED", "false").lower() == "true",
            "automation_level": int(env.get("AUTOMATION_LEVEL", 2)),
            "application_threshold": prefs.get("application_threshold", int(env.get("APPLICATION_THRESHOLD", 70))),
            "auto_submit_threshold": prefs.get("auto_submit_threshold", 80),
            **({"target_roles":prefs["target_roles"]} if "target_roles" in prefs else {}),
            "answer_memory_revisions":revisions(read_json(Path(root)/'data/application_answers.json',[])),
            "timezone": "Australia/Sydney", "database": str(Path(root)/env.get("DATABASE_PATH", "data/job_agent.sqlite3")),
            "host": "127.0.0.1", "port": int(env.get("PORT", 8766))}

def post_submission_enabled(root=ROOT):
    scope=read_json(Path(root)/'data/workflow_scope.json',{})
    return scope.get('post_submission_enabled') is True
