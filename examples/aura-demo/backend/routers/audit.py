from fastapi import APIRouter, Depends
from pathlib import Path
import json

from core.auth import get_current_user

router = APIRouter()
_AUDIT = Path(__file__).parent.parent / "data" / "audit.jsonl"


def append_audit(entry: dict) -> None:
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT.open("a") as f:
        f.write(json.dumps(entry) + "\n")


@router.get("/audit")
def audit_tail(limit: int = 50, _user=Depends(get_current_user)):
    if not _AUDIT.exists():
        return []
    lines = _AUDIT.read_text().splitlines()[-limit:]
    return [json.loads(l) for l in lines if l.strip()]