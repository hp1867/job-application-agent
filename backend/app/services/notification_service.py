from ..agents.deadline_manager import upcoming
def notify_deadlines(db):
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    current=datetime.now(timezone.utc);today=current.astimezone(ZoneInfo('Australia/Sydney')).date()
    for d in upcoming(db,7):
        value=datetime.fromisoformat(d['due_at'])
        if value.tzinfo:
            hours=(value-current).total_seconds()/3600
            if hours<0:continue
            window='1h' if hours<=1 else '24h' if hours<=24 else '7d'
        else:
            days=(value.date()-today).days
            window='today' if days==0 else 'tomorrow' if days==1 else '7d'
        db.notify("deadline:"+d["deadline_id"]+':'+window,{"title":d["kind"].replace("_"," ").title()+" due "+d["due_at"],"deadline":d,'reminder_window':window})
    return upcoming(db,7)
