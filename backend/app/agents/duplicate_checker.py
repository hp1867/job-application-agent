from difflib import SequenceMatcher
from ..utils.validators import normal
import re

def company_key(value):
    return re.sub(r'\b(?:pty|ltd|limited|inc|incorporated|corp|corporation)\b','',normal(value)).strip()
def same_job(a,b):
    company = company_key(a['company']) == company_key(b['company'])
    if not company: return False
    title = SequenceMatcher(None,normal(a["title"]),normal(b["title"])).ratio()
    if a.get("external_id") and b.get("external_id") and a["external_id"] != b["external_id"] and a["source"]==b["source"]:
        return False
    if a.get("external_id") and a["external_id"]==b.get("external_id") and a["source"]==b["source"]: return True
    if a["canonical_url"]==b["canonical_url"] and title>=0.95: return True
    location = normal(a.get("location"))==normal(b.get("location"))
    if title>=0.97 and location: return True
    description = SequenceMatcher(None,normal(a.get("description")),normal(b.get("description"))).ratio()
    return title>=0.87 and location and len(a.get("description",""))>100 and description>=0.94
def merge(existing,incoming):
    from datetime import datetime,timezone
    def rank(record):
        try:
            stamp=datetime.fromisoformat(record.get("listing_verified_at") or "")
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            time=stamp.timestamp()
            if time>datetime.now(timezone.utc).timestamp()+300:time=0
        except (ValueError,TypeError):time=0
        return (bool(record.get("is_official")),time)
    preferred=incoming if rank(incoming)>=rank(existing) else existing
    out={**existing,**preferred,"job_id":existing["job_id"],"date_discovered":existing["date_discovered"]}
    if preferred is incoming and existing.get("requirements_reviewed") and not incoming.get("requirements_reviewed") and normal(existing.get("description"))==normal(incoming.get("description")):
        for key in ("requirements_reviewed","requirements","required_skills","preferred_skills","responsibilities","preferred_requirements","salary_min","salary_max","currency","cover_letter_required"):
            if key in existing:out[key]=existing[key]
    evidence=existing.get("source_evidence",[])+incoming.get("source_evidence",[])+[{"url":incoming["source_url"],"source":incoming["source"]}]
    out["source_evidence"]=list({s["url"]:s for s in evidence}.values())
    return out
