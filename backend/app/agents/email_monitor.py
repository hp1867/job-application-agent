import json,re
from urllib.parse import urlsplit
from .email_classifier import classify
from .deadline_manager import extract_deadlines
from ..models.email_event import STATUS_MAP
from ..models.application import transition_allowed
from ..integrations.gmail import GmailReader
from ..utils.validators import normal
def match_application(message,applications,jobs):
    text=normal(message.get("subject","")+" "+message.get("body",""))
    sender=message.get("sender","").lower()
    scores=[]
    for app in applications:
        if not app.get("date_applied"):continue
        from datetime import datetime
        try:
            received=datetime.fromisoformat(message["received_at"]);applied=datetime.fromisoformat(app["date_applied"])
            if received.tzinfo is None or applied.tzinfo is None or received<applied:continue
        except (KeyError,ValueError,TypeError):continue
        job=next((j for j in jobs if j["job_id"]==app["job_id"]),{})
        company=normal(app["company"])
        company_hit=bool(company and re.search(r"\b"+re.escape(company)+r"\b",text))
        title_tokens=set(normal(app["role"]).split())-{"the","a","and","program","2026","2027","australia"}
        title_hit=bool(title_tokens) and len(title_tokens&set(text.split()))/len(title_tokens)>=.7
        domain_hit=any(re.search(r"@(?:[a-z0-9-]+\.)*"+re.escape(d)+r"(?:>|\s|$)",sender) for d in job.get("employer_domains",[]))
        ref=app.get("employer_application_id")
        ref_hit=bool(ref and str(ref).lower() in message.get("body","").lower())
        score=(.45 if company_hit else 0)+(.35 if title_hit else 0)+(.2 if domain_hit else 0)
        if ref_hit:score=max(score,.98)
        if score>=.8:scores.append((score,app))
    scores.sort(key=lambda x:x[0],reverse=True)
    if not scores or len(scores)>1 and scores[0][0]-scores[1][0]<.15:return None,0
    return scores[0][1],scores[0][0]
def monitor(root,db,profile):
    from ..utils.config import post_submission_enabled
    if not post_submission_enabled(root):
        return {"state":"USER_MANAGED_POST_APPLICATION","processed":0,"events":[]}
    if profile.get("intake_deferred") or not profile.get("identity_confirmed"):
        return {"state":"CANDIDATE_INTAKE_DEFERRED","processed":0,"events":[]}
    if not any(a.get("date_applied") for a in db.rows("applications")):
        return {"state":"NO_SUBMITTED_APPLICATIONS","processed":0,"events":[]}
    reader=GmailReader(root);status=reader.status(profile)
    if not status["candidate_mailbox_confirmed"]:
        return {"state":"NEEDS_MAILBOX_CONFIRMATION","processed":0,"events":[],"next_action":status["next_action"]}
    try:
        messages=reader.api_messages('newer_than:30d -in:spam -in:trash {"application" "interview" "assessment" "offer"}') if status["mode"]=="oauth" else reader.connector_captures()
    except Exception as exc:
        db.log("gmail","Read recruitment messages","EMAIL_API_UNAVAILABLE",error=type(exc).__name__)
        return {"state":"EMAIL_API_UNAVAILABLE","processed":0,"events":[]}
    seen={e["email_id"] for e in db.rows("email_events")};events=[]
    for message in messages:
        eid=message.get("email_id") or message.get("id")
        if not eid or eid in seen:continue
        app,match_confidence=match_application(message,db.rows("applications"),db.rows("jobs"))
        # Do not store unrelated correspondence in the recruitment database.
        if not app:continue
        classification=classify(message)
        event={**classification,"email_id":eid,"application_id":app["application_id"],"match_confidence":match_confidence,
               "received_at":message["received_at"],"subject":message.get("subject",""),"sender":message.get("sender",""),
               "source_url":"https://mail.google.com/mail/u/0/#all/"+eid}
        with db.connect() as c:c.execute("INSERT OR IGNORE INTO email_events VALUES(?,?,?,?)",(eid,app["application_id"],json.dumps(event),message["received_at"]))
        status_new=STATUS_MAP.get(classification["classification"])
        if status_new and classification["confidence"]>=.85 and transition_allowed(app["status"],status_new):
            db.update_application(app["application_id"],{"next_action":"Review "+classification["classification"].lower().replace("_"," ")},status_new,"Matched full recruitment email "+eid)
            db.notify("email:"+eid,{"title":classification["classification"].replace("_"," "),"application_id":app["application_id"],"company":app["company"]})
        for d in extract_deadlines(message.get("body",""),message["received_at"],app["application_id"],app["job_id"],"email:"+eid):
            db.save_deadline(d)
        events.append(event);seen.add(eid)
    return {"state":"OK","processed":len(events),"events":events}
