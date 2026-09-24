import re
from datetime import datetime,timezone,timedelta,date
from ..utils.validators import digest
MONTHS={m.lower():i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}
def extract_deadlines(text,received_at,application_id=None,job_id=None,source=None):
    deadlines=[]
    for sentence in re.split(r"[\n.!?]+",text):
        if not re.search(r"deadline|closes?|closing|complete.{0,40}\bby\b|interview|assessment.{0,50}within|offer.{0,30}by|follow[ -]?up",sentence,re.I):continue
        kind="INTERVIEW_BOOKING" if re.search(r'(book|booking|schedule).{0,30}interview|interview.{0,30}(booking|book by)',sentence,re.I) else "INTERVIEW" if re.search("interview",sentence,re.I) else "ASSESSMENT" if re.search("assessment",sentence,re.I) else "OFFER" if re.search("offer",sentence,re.I) else "FOLLOW_UP" if re.search(r'follow[ -]?up',sentence,re.I) else "APPLICATION"
        dates=[]
        for iso in re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b",sentence):
            try:dates.append(date.fromisoformat(iso).isoformat())
            except ValueError:pass
        for day,month,year in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})\b",sentence):
            try:dates.append(date(int(year),MONTHS[month.lower()],int(day)).isoformat())
            except (ValueError,KeyError):pass
        relative=re.search(r"within\s+(\d+)\s+(hours?|days?)",sentence,re.I)
        if relative:
            dt=datetime.fromisoformat(received_at)
            if dt.tzinfo is not None:
                delta=timedelta(hours=int(relative[1])) if relative[2].lower().startswith("hour") else timedelta(days=int(relative[1]))
                dates.append((dt+delta).isoformat())
        # Use a clock time only when its timezone is stated, never infer it from a date.
        clock=re.search(r'\b(\d{1,2})(?::([0-5]\d))?\s*(am|pm)?\s*(AEST|AEDT|UTC|GMT)\b',sentence,re.I)
        if clock:
            hour=int(clock[1]);minute=int(clock[2] or 0);meridian=(clock[3] or '').lower()
            valid=(1<=hour<=12) if meridian else (0<=hour<=23)
            if valid:
                if meridian:hour=hour%12+(12 if meridian=='pm' else 0)
                offset={'AEST':10,'AEDT':11,'UTC':0,'GMT':0}[clock[4].upper()]
                dates=[datetime.fromisoformat(d).replace(hour=hour,minute=minute,tzinfo=timezone(timedelta(hours=offset))).isoformat() if len(d)==10 else d for d in dates]
        instants=re.findall(r'\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})\b',sentence)
        for value in instants:
            try:
                instant=datetime.fromisoformat(value)
                dates=[d for d in dates if d!=value[:10]]+[instant.isoformat()]
            except ValueError:pass
        for due in set(dates):
            time_unknown=kind in {"INTERVIEW","INTERVIEW_BOOKING"} and "T" not in due
            deadlines.append({"deadline_id":digest([source,job_id,application_id,kind,due])[:24],"application_id":application_id,"job_id":job_id,
                "kind":kind,"due_at":due,"timezone":"Australia/Sydney" if "T" not in due else "FROM_SOURCE","source":source,
                "evidence":sentence.strip()[:300],"precision":"day" if "T" not in due else "instant",
                "review":"NEEDS_REVIEW" if time_unknown else "CONFIRMED","note":"Interview time and timezone require verification" if time_unknown else None})
        if not dates and re.search(r"tomorrow|next |friday|monday|tuesday|wednesday|thursday|saturday|sunday|\d{1,2}/\d{1,2}|within\s+\d|\d{1,2}\s+[A-Za-z]+\s+20\d{2}",sentence,re.I):
            deadlines.append({"deadline_id":digest([source,sentence])[:24],"application_id":application_id,"job_id":job_id,"kind":kind,"due_at":None,
                              "evidence":sentence.strip()[:300],"review":"NEEDS_REVIEW","source":source,"note":"Ambiguous date; confirm explicitly"})
    return deadlines
def upcoming(db,days=7):
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo("Australia/Sydney")).date()
    applications={a['application_id']:a for a in db.rows('applications')}
    output=[]
    for d in db.rows('deadlines'):
        app=applications.get(d.get('application_id'),{})
        if app.get('status') in {'REJECTED','WITHDRAWN','CLOSED'}:continue
        if d['kind']=='APPLICATION' and app.get('date_applied'):continue
        if app.get('status')=='OFFER' and d['kind'] not in {'OFFER','FOLLOW_UP'}:continue
        if not d.get('due_at'):continue
        due=datetime.fromisoformat(d['due_at'])
        local=due.astimezone(ZoneInfo('Australia/Sydney')).date() if due.tzinfo else due.date()
        if today<=local<=today+timedelta(days=days):output.append(d)
    return output
