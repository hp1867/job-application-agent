"""Calendar-day reports from durable events, not cumulative dashboard counts."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from ..utils.config import now,write_json
from ..agents.deadline_manager import upcoming

def local_day(value):
    if not value:return None
    if len(value)==10:return value
    try:return datetime.fromisoformat(value).astimezone(ZoneInfo("Australia/Sydney")).date().isoformat()
    except (ValueError,TypeError):return None

def daily_report(root,db,day=None):
    day=day or local_day(now())
    datetime.strptime(day,"%Y-%m-%d")
    applications=db.rows("applications");jobs=db.rows("jobs")
    runs=[json.loads(r["report"]) for r in db.rows("runs") if r.get("report") and local_day(r["completed_at"])==day]
    history=[h for a in applications for h in db.history(a["application_id"]) if local_day(h["time"])==day]
    def transitioned(*statuses):return len({h["application_id"] for h in history if h["new_status"] in statuses})
    report={"report_date":day,"timezone":"Australia/Sydney","generated_at":now(),
        "jobs_found":sum(r.get("jobs_found",0) for r in runs),
        "new_jobs":sum(local_day(j["date_discovered"])==day for j in jobs),
        "strong_matches":sum((j.get("analysis",{}).get("scoring",{}).get("overall_score") or 0)>=80 and j.get("analysis",{}).get("eligibility",{}).get("status")!="NOT_ELIGIBLE" for j in jobs),
        "unscored_jobs":sum(j.get("analysis",{}).get("scoring",{}).get("overall_score") is None for j in jobs),
        "applications_prepared":len({a["application_id"] for a in db.rows("artifacts") if a["kind"]=="resume" and not a.get("archived") and local_day(a.get("created_at"))==day}),
        "archived_drafts":sum(a.get("archived") is True and local_day(a.get("created_at"))==day for a in db.rows("artifacts")),
        "waiting_for_approval":sum(a["status"]=="WAITING_FOR_APPROVAL" for a in applications),
        "applications_submitted":sum(local_day(a.get("date_applied"))==day for a in applications),
        "application_confirmations":transitioned("APPLICATION_RECEIVED"),"assessments":transitioned("ASSESSMENT"),
        "interviews":transitioned("PHONE_SCREEN","INTERVIEW","SECOND_INTERVIEW","FINAL_INTERVIEW"),
        "rejections":transitioned("REJECTED"),"offers":transitioned("OFFER"),"deadlines":upcoming(db,7),
        "errors":[e for r in runs for e in r.get("errors",[])],
        "counting_note":"Jobs found counts listing observations; new jobs counts unique records. Recruitment outcomes count distinct applications changed today."}
    from pathlib import Path
    write_json(Path(root)/"generated/reports"/("daily-"+day+".json"),report)
    return report
