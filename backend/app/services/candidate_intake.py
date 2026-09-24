"""Candidate intake lifecycle. Preserve unconfirmed imports; never use them by default."""
import json
from pathlib import Path
from ..models.candidate import empty_profile
from ..models.application import PREPARATION
from ..utils.config import now,read_json,write_json
from ..utils.validators import digest

def invalidate_preparations(db,reason):
    """Explicit invalidation is separate from normal recruitment status progression."""
    from .preparation_lifecycle import invalidate
    return invalidate(db,reason,archive_documents=True)

def defer_candidate(root,db):
    root=Path(root);path=root/"data/candidate_profile.json";profile=read_json(path,empty_profile())
    if profile.get("intake_deferred") and not profile.get("VERIFIED_INFORMATION"):
        return {"candidate_intake":"DEFERRED","personal_documents_enabled":False,"changed":False}
    if profile.get("VERIFIED_INFORMATION"):
        archive=root/"data/private_archive"/(digest(profile)+".json")
        if not archive.exists():write_json(archive,profile)
    clean=empty_profile();clean["intake_deferred"]=True
    write_json(path,clean)
    invalidate_preparations(db,"Candidate intake deferred by user; wait for supplied profile and resume")
    return {"candidate_intake":"DEFERRED","personal_documents_enabled":False,"changed":True,"original_files_preserved":True}
