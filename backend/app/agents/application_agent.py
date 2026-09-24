from datetime import datetime,timezone,timedelta
import hashlib,json,sqlite3
from pathlib import Path
from ..models.candidate import verified
from ..integrations.browser import packet_hash,job_revision
from ..utils.validators import digest,normal,canonical_url
from ..utils.config import now
LEGAL_MARKERS=("authorised","authorized","sponsorship","citizenship","visa","clearance","criminal","conviction","declaration","certify","consent","agree","disability","ethnicity","gender","salary","work rights","right to work")

def submission_target(job):
    return digest([canonical_url(job['canonical_url']),normal(job['title'])])
def answer_question(question,answers):
    q=normal(question)
    if any(x in q for x in LEGAL_MARKERS):
        return {"action":"MANUAL","reason":"Sensitive or legal declaration"}
    matching=[a for a in answers if normal(a.get("normalised_question") or a["question"])==q]
    if len({digest({key:a.get(key) for key in ('answer','verified','requires_manual_confirmation')}) for a in matching})>1:
        return {'action':'ASK','reason':'Conflicting stored answers require review'}
    a=matching[0] if matching else None
    if not a or not a.get("verified") or a.get("answer") is None:
        return {"action":"ASK","reason":"No verified answer"}
    if a.get("requires_manual_confirmation"): return {"action":"MANUAL","reason":"Answer requires confirmation"}
    return {"action":"AUTOFILL","answer":a["answer"]}
def gates(config,profile,job,application,db,require_approval=True):
    reasons=[];packet=application.get("packet") or {}
    if profile.get("intake_deferred"):reasons.append("CANDIDATE_INTAKE_DEFERRED")
    if application.get("status") not in {"READY_TO_APPLY","WAITING_FOR_APPROVAL"}:reasons.append("APPLICATION_NOT_READY")
    current=db.application(application["application_id"])
    if not current or digest(current)!=digest(application):reasons.append("APPLICATION_STATE_CHANGED")
    current_job=db.job(job["job_id"])
    if not current_job or digest(current_job)!=digest(job):reasons.append("JOB_STATE_CHANGED")
    from .eligibility_checker import evaluate
    if evaluate(job,profile,config)["status"]!="ELIGIBLE":reasons.append("FRESH_ELIGIBILITY_CHECK_FAILED")
    if job.get("listing_state")!="OPEN":reasons.append("LISTING_NOT_CONFIRMED_OPEN")
    try:
        stamp=datetime.fromisoformat(job["listing_verified_at"])
        age=datetime.now(timezone.utc)-stamp
        if age<timedelta(minutes=-5) or age>timedelta(hours=24):reasons.append("LISTING_RECHECK_REQUIRED")
    except (KeyError,ValueError,TypeError):reasons.append("LISTING_RECHECK_REQUIRED")
    if job.get("closing_at") and job["closing_at"][:10]<now()[:10]:reasons.append("JOB_CLOSED")
    if config["dry_run"]:reasons.append("DRY_RUN")
    if not config["production_approved"]:reasons.append("PRODUCTION_NOT_APPROVED")
    if config["automation_level"]==1:reasons.append("MANUAL_SUBMISSION_LEVEL_1")
    if config["automation_level"] not in (1,2,3):reasons.append("INVALID_AUTOMATION_LEVEL")
    if not profile.get("identity_confirmed"):reasons.append("CANDIDATE_UNCONFIRMED")
    if job.get("analysis",{}).get("eligibility",{}).get("status")!="ELIGIBLE":reasons.append("ELIGIBILITY_NOT_CONFIRMED")
    score=job.get("analysis",{}).get("scoring",{}).get("overall_score",0)
    threshold=max(config["application_threshold"],config.get("auto_submit_threshold",80)) if config["automation_level"]==3 else config["application_threshold"]
    if score < threshold or config["automation_level"]==3 and score<=threshold:reasons.append("SCORE_BELOW_THRESHOLD")
    validation=application.get("validation") or {}
    if validation.get("result")!="PASS":reasons.append("RESUME_VALIDATION_FAILED")
    for kind,key in (("resume","pdf_sha256"),):
        doc=packet.get("documents",{}).get(kind)
        if not doc or not Path(doc).is_file() or hashlib.sha256(Path(doc).read_bytes()).hexdigest()!=validation.get(key):
            reasons.append("RESUME_FILE_CHANGED_OR_MISSING")
    if packet.get("profile_hash")!=digest(profile):reasons.append("PROFILE_CHANGED")
    if 'answer_memory_revisions' in config:
        from ..utils.answer_memory import review_hash
        if packet.get('answer_memory_hash')!=review_hash(config['answer_memory_revisions'],packet.get('questions',[])):reasons.append('ANSWER_MEMORY_CHANGED_REVIEW_REQUIRED')
    if packet.get("job_revision")!=job_revision(job):reasons.append("JOB_REQUIREMENTS_CHANGED")
    fields=packet.get("verified_fields",{})
    if not all(fields.get(k) for k in ("full_name","email")):reasons.append("CONTACT_INFORMATION_MISSING")
    if any(verified(profile,k) is None or verified(profile,k)!=v for k,v in fields.items()):reasons.append("UNVERIFIED_FORM_FIELD")
    for kind,path in packet.get("documents",{}).items():
        if path and (not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=packet.get("document_hashes",{}).get(kind)):
            reasons.append("APPLICATION_DOCUMENT_CHANGED")
    if packet.get("job_id")!=job["job_id"] or packet.get("destination")!=job["canonical_url"]:reasons.append("WRONG_APPLICATION_TARGET")
    if not packet.get("form_reviewed"):reasons.append("FORM_NOT_REVIEWED")
    if not packet.get("fields_filled"):reasons.append("FORM_NOT_FILLED")
    if not packet.get("uploads_confirmed"):reasons.append("UPLOADS_NOT_CONFIRMED")
    if packet.get("website_permits_automation") is not True or not packet.get("website_policy_evidence"):reasons.append("WEBSITE_PERMISSION_UNCONFIRMED")
    if not packet.get("legal_review_complete"):reasons.append("LEGAL_REVIEW_REQUIRED")
    for flag in ("captcha","mfa","login_required"):
        if packet.get(flag):reasons.append(flag.upper())
    if any(not q.get("verified") or q.get("answer") is None or q.get("requires_manual_confirmation") for q in packet.get("questions",[])):
        reasons.append("UNRESOLVED_QUESTIONS")
    if (job.get("cover_letter_required") or packet.get('documents',{}).get('cover_letter')) and (not application.get("cover_letter_version") or application.get("cover_validation")!="PASS"):
        reasons.append("COVER_LETTER_NOT_VALIDATED")
    try:
        age=datetime.now(timezone.utc)-datetime.fromisoformat(packet["observed_at"])
        if age<timedelta(minutes=-5) or age>timedelta(hours=2):reasons.append("FORM_REVIEW_EXPIRED")
    except (KeyError,ValueError,TypeError):reasons.append("FORM_REVIEW_TIMESTAMP_MISSING")
    with db.connect() as c:
        if c.execute("SELECT 1 FROM submission_attempts WHERE job_id=?",(job["job_id"],)).fetchone():reasons.append("SUBMISSION_ALREADY_ATTEMPTED")
        if c.execute('SELECT 1 FROM submission_targets WHERE target_key=?',(submission_target(job),)).fetchone():reasons.append('SUBMISSION_TARGET_ALREADY_ATTEMPTED')
        # Cover reservations made before the target-key migration as well.
        for prior in c.execute('SELECT j.data FROM submission_attempts s JOIN jobs j ON j.job_id=s.job_id'):
            if submission_target(json.loads(prior['data']))==submission_target(job):
                if 'SUBMISSION_TARGET_ALREADY_ATTEMPTED' not in reasons:reasons.append('SUBMISSION_TARGET_ALREADY_ATTEMPTED')
                break
        if require_approval and config["automation_level"]==2:
            a=c.execute("SELECT * FROM approvals WHERE application_id=?",(application["application_id"],)).fetchone()
            if not a or a["packet_hash"]!=packet_hash(packet) or a["expires_at"]<now():reasons.append("EXACT_APPLICATION_APPROVAL_REQUIRED")
    return {"allowed":not reasons,"blockers":reasons,"packet_hash":packet_hash(packet)}

def reserve_submission(config,profile,job,application,db):
    gate=gates(config,profile,job,application,db)
    if not gate["allowed"]:raise ValueError(", ".join(gate["blockers"]))
    # UNIQUE(job_id) makes concurrent attempts and uncertain retries fail closed.
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO submission_targets VALUES(?,?)',(submission_target(job),job['job_id']))
        c.execute("INSERT INTO submission_attempts VALUES(?,?,?,?,?,?)",(job["job_id"],application["application_id"],"RESERVED",gate["packet_hash"],None,now()))
    return gate
def confirm_submission(db,aid,evidence):
    if not evidence or not evidence.get("confirmation_text") or not evidence.get("confirmation_url"):
        raise ValueError("Observed confirmation text and URL required")
    a=db.application(aid)
    with db.connect() as c:
        result=c.execute("UPDATE submission_attempts SET state='CONFIRMED',evidence=? WHERE job_id=? AND state='RESERVED'",(json.dumps(evidence),a["job_id"]))
        if result.rowcount!=1:raise ValueError("No reserved submission")
    return db.update_application(aid,{"next_action":"Monitor recruitment response"},"APPLIED","Observed employer confirmation")
