from datetime import datetime,timezone,timedelta
from ..integrations.browser import prepare_packet,packet_hash
from ..utils.config import now
def prepare(db,profile,job,app,resume,cover=None):
    packet=prepare_packet(profile,job,resume,cover)
    with db.connect() as c:c.execute("DELETE FROM approvals WHERE application_id=?",(app["application_id"],))
    return db.update_application(app["application_id"],{"packet":packet,"next_action":packet["next_action"]})

def record_form_review(db,aid,evidence):
    """Record observed form state, never fabricate a browser visit or click Submit."""
    app=db.application(aid)
    if not app or app["status"] not in {"READY_TO_APPLY","WAITING_FOR_APPROVAL"}:raise ValueError("Prepare and validate the application first")
    packet=dict(app.get("packet") or {})
    if evidence.get("expected_packet_hash")!=packet_hash(packet):raise ValueError("Application changed; inspect the current packet")
    allowed={"form_reviewed","fields_filled","uploads_confirmed","legal_review_complete","captcha","mfa","login_required","website_permits_automation","website_policy_evidence","observed_at","questions","observation_source","answer_memory_hash"}
    if set(evidence)-allowed-{"expected_packet_hash"}:raise ValueError("Unsupported form evidence field")
    if not evidence.get("observation_source"):raise ValueError("Observed browser or manual review source required")
    if 'answer_memory_hash' in evidence:
        import re
        if not isinstance(evidence['answer_memory_hash'],str) or not re.fullmatch('[0-9a-f]{64}',evidence['answer_memory_hash']):raise ValueError('Invalid answer-memory revision')
    for key in allowed-{"website_policy_evidence","observed_at","questions","observation_source","answer_memory_hash"}:
        if key in evidence and type(evidence[key]) is not bool:raise ValueError("Form evidence flags must be true or false")
    for q in evidence.get("questions",[]):
        if not isinstance(q,dict) or not q.get("question"):raise ValueError("Each form question needs its exact text")
    packet.update({k:v for k,v in evidence.items() if k in allowed})
    packet["packet_hash"]=packet_hash(packet)
    with db.connect() as c:c.execute("DELETE FROM approvals WHERE application_id=?",(aid,))
    complete=all(packet.get(k) is True for k in ("form_reviewed","fields_filled","uploads_confirmed","legal_review_complete","website_permits_automation"))
    complete=complete and not any(packet.get(k) for k in ("captcha","mfa","login_required")) and bool(packet.get("observed_at") and packet.get("website_policy_evidence"))
    complete=complete and all(q.get("verified") is True and q.get("answer") is not None and not q.get("requires_manual_confirmation") for q in packet.get("questions",[]))
    status="WAITING_FOR_APPROVAL" if complete else "READY_TO_APPLY"
    return db.update_application(aid,{"packet":packet,"browser_blocker":None if complete else app.get('browser_blocker'),"next_action":"Review exact application and approve" if complete else "Resolve form blockers; no submission permitted"},status,"Observed employer form review recorded")
def approve(db,aid,expected_hash):
    app=db.application(aid)
    if not app or app["status"]!="WAITING_FOR_APPROVAL":raise ValueError("Application is not ready for approval")
    packet=app.get("packet") or {}
    actual=packet_hash(packet)
    if actual!=expected_hash:raise ValueError("Application changed; review again")
    if (app.get("validation") or {}).get("result")!="PASS":raise ValueError("Validated documents required")
    with db.connect() as c:
        c.execute("INSERT INTO approvals VALUES(?,?,?,?) ON CONFLICT(application_id) DO UPDATE SET packet_hash=excluded.packet_hash,approved_at=excluded.approved_at,expires_at=excluded.expires_at",
                  (aid,actual,now(),(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()))
    db.log("application","User approved exact application","APPROVED",application_id=aid)
    return {"approved":True,"submitted":False}
