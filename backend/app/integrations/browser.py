from ..models.candidate import verified
from .aihawk_adapter import plan_application
from ..utils.validators import digest
from pathlib import Path
import hashlib
BLOCKERS={"CAPTCHA","LOGIN_REQUIRED","MFA","EXPIRED_SESSION","FORBIDDEN","RATE_LIMITED","SITE_UNAVAILABLE","JOB_REMOVED","RESUME_UPLOAD_FAILURE","COVER_LETTER_UPLOAD_FAILURE","UNKNOWN_QUESTION","BROWSER_UNAVAILABLE","AUTOMATION_PROHIBITED","FORM_STATE_CHANGED","FORM_STEP_LIMIT"}
def prepare_packet(profile,job,resume,cover=None):
    fields={k:verified(profile,k) for k in ("full_name","email","phone","location","linkedin","github","portfolio","education","employment_experience","technical_skills") if verified(profile,k) is not None}
    if not profile.get("identity_confirmed"): fields={}
    documents={"resume":resume.get("pdf_path") if resume else None,"cover_letter":cover.get("pdf_path") if cover else None}
    packet={"job_id":job["job_id"],"company":job["company"],"role":job["title"],"destination":job["canonical_url"],
            "job_revision":job_revision(job),
            "document_hashes":{k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in documents.items() if v and Path(v).is_file()},
            "verified_fields":fields,"profile_hash":digest(profile),"documents":documents,"questions":[],
            "form_reviewed":False,"fields_filled":False,"uploads_confirmed":False,"legal_review_complete":False,
            "captcha":False,"mfa":False,"login_required":False,"website_permits_automation":None,
            "website_policy_evidence":None,"observed_at":None,"submission_evidence":None,
            "next_action":"Open employer form in the connected browser and inspect it",
            "actions":plan_application(job,fields,documents)}
    packet["packet_hash"]=packet_hash(packet)
    return packet
def job_revision(job):
    return digest({k:job.get(k) for k in ("job_id","company","title","required_skills","preferred_skills","requirements","description",
        "location","remote_type","employment_type","education_required","experience_required","work_rights_requirement",
        "citizenship_requirement","clearance_requirement")})
def packet_hash(packet):
    return digest({k:v for k,v in packet.items() if k not in {"packet_hash","submission_evidence","next_action"}})
def record_blocker(db,aid,code,detail):
    if code not in BLOCKERS:raise ValueError("Unknown browser blocker")
    db.update_application(aid,{"next_action":detail,"browser_blocker":code})
    db.log("browser",code,"NEEDS_ACTION",error=detail,application_id=aid)
