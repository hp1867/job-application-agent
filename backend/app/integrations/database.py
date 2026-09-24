import json, sqlite3, uuid
from pathlib import Path
from ..models.application import transition_allowed
from ..utils.config import now
from ..utils.logger import redact
from ..utils.validators import digest

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, canonical_url TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS job_sources(job_id TEXT NOT NULL REFERENCES jobs(job_id),url TEXT NOT NULL,source TEXT NOT NULL,UNIQUE(job_id,url));
CREATE TABLE IF NOT EXISTS applications(application_id TEXT PRIMARY KEY,job_id TEXT UNIQUE NOT NULL REFERENCES jobs(job_id),status TEXT NOT NULL,data TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS status_history(event_id INTEGER PRIMARY KEY,application_id TEXT NOT NULL REFERENCES applications(application_id),old_status TEXT,new_status TEXT NOT NULL,time TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT PRIMARY KEY,application_id TEXT NOT NULL REFERENCES applications(application_id),kind TEXT NOT NULL,fingerprint TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(application_id,kind,fingerprint));
CREATE TABLE IF NOT EXISTS email_events(email_id TEXT PRIMARY KEY,application_id TEXT REFERENCES applications(application_id),data TEXT NOT NULL,received_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deadlines(deadline_id TEXT PRIMARY KEY,application_id TEXT REFERENCES applications(application_id),job_id TEXT REFERENCES jobs(job_id),due_at TEXT,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS application_answers(normalised_question TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity_logs(id INTEGER PRIMARY KEY,time TEXT NOT NULL,module TEXT NOT NULL,job_id TEXT,application_id TEXT,action TEXT NOT NULL,result TEXT NOT NULL,error TEXT);
CREATE TABLE IF NOT EXISTS submission_attempts(job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),application_id TEXT NOT NULL REFERENCES applications(application_id),state TEXT NOT NULL,packet_hash TEXT NOT NULL,evidence TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS submission_targets(target_key TEXT PRIMARY KEY,job_id TEXT UNIQUE NOT NULL REFERENCES jobs(job_id));
CREATE TABLE IF NOT EXISTS approvals(application_id TEXT PRIMARY KEY REFERENCES applications(application_id),packet_hash TEXT NOT NULL,approved_at TEXT NOT NULL,expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,started_at TEXT NOT NULL,completed_at TEXT,report TEXT);
CREATE TABLE IF NOT EXISTS run_lock(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT NOT NULL,expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(notification_id TEXT PRIMARY KEY,data TEXT NOT NULL,created_at TEXT NOT NULL,read_at TEXT);
"""
class Database:
    def __init__(self,path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript(SCHEMA)
    def connect(self):
        c=sqlite3.connect(self.path,timeout=20,factory=ClosingConnection)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c
    def rows(self,table):
        allowed={"jobs","applications","artifacts","email_events","deadlines","activity_logs","runs","notifications","application_answers"}
        if table not in allowed: raise ValueError("Unknown table")
        with self.connect() as c:
            rows=[dict(r) for r in c.execute("SELECT * FROM "+table)]
        if table=="activity_logs": return rows[-300:][::-1]
        return [json.loads(r["data"]) if "data" in r else r for r in rows]
    def job(self,job_id):
        return next((j for j in self.rows("jobs") if j["job_id"]==job_id),None)
    def application(self,app_id):
        return next((a for a in self.rows("applications") if a["application_id"]==app_id),None)
    def save_job(self,j):
        with self.connect() as c:
            c.execute("INSERT INTO jobs VALUES(?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET canonical_url=excluded.canonical_url,data=excluded.data,updated_at=excluded.updated_at",(j["job_id"],j["canonical_url"],json.dumps(j),now()))
            for s in j.get("source_evidence",[]) + [{"url":j["source_url"],"source":j["source"]}]:
                c.execute("INSERT OR IGNORE INTO job_sources VALUES(?,?,?)",(j["job_id"],s.get("url",j["source_url"]),s.get("source",j["source"])))
    def ensure_application(self,j):
        with self.connect() as c:
            row=c.execute("SELECT data FROM applications WHERE job_id=?",(j["job_id"],)).fetchone()
            if row: return json.loads(row["data"])
            aid=str(uuid.uuid4())
            data={"application_id":aid,"job_id":j["job_id"],"company":j["company"],"role":j["title"],"location":j["location"],
                  "job_url":j["canonical_url"],"source":j["source"],"score":None,"date_found":j["date_discovered"],"date_applied":None,
                  "resume_version":None,"cover_letter_version":None,"status":"FOUND","next_action":"Analyse listing",
                  "last_updated":now(),"notes":"","validation":None,"packet":None}
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?)",(aid,j["job_id"],"FOUND",json.dumps(data),now()))
            c.execute("INSERT INTO status_history(application_id,new_status,time,reason) VALUES(?,?,?,?)",(aid,"FOUND",now(),"Listing discovered"))
            return data
    def update_application(self,aid,changes,status=None,reason=""):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT data FROM applications WHERE application_id=?",(aid,)).fetchone()
            if not row: raise ValueError("Application not found")
            a=json.loads(row["data"]); old=a["status"]; new=status or old
            if not transition_allowed(old,new): raise ValueError("Invalid status transition: "+old+" to "+new)
            if new=="APPLIED" and old!="APPLIED":
                receipt=c.execute("SELECT evidence FROM submission_attempts WHERE job_id=? AND state='CONFIRMED'",(a["job_id"],)).fetchone()
                if not receipt or not receipt["evidence"]: raise ValueError("Confirmed submission evidence required")
            for protected in ("application_id","job_id","status","date_applied"):
                if protected in changes: raise ValueError("Protected application field: "+protected)
            a.update(changes); a.update(status=new,last_updated=now())
            if new=="APPLIED" and old!=new: a["date_applied"]=now()
            c.execute("UPDATE applications SET status=?,data=?,updated_at=? WHERE application_id=?",(new,json.dumps(a),now(),aid))
            if old!=new:
                c.execute("INSERT INTO status_history(application_id,old_status,new_status,time,reason) VALUES(?,?,?,?,?)",(aid,old,new,now(),reason))
            return a
    def history(self,aid):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM status_history WHERE application_id=? ORDER BY event_id",(aid,))]
    def artifact(self,aid,kind,fingerprint,data):
        art_id=digest([aid,kind,fingerprint])[:24]
        with self.connect() as c:
            old=c.execute('SELECT created_at FROM artifacts WHERE artifact_id=?',(art_id,)).fetchone()
            data={**data,"artifact_id":art_id,"application_id":aid,"kind":kind,"fingerprint":fingerprint,"created_at":old['created_at'] if old else now()}
            c.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?) ON CONFLICT(artifact_id) DO UPDATE SET data=excluded.data",(art_id,aid,kind,fingerprint,json.dumps(data),now()))
        return data
    def log(self,module,action,result="OK",error=None,job_id=None,application_id=None):
        with self.connect() as c:
            c.execute("INSERT INTO activity_logs(time,module,job_id,application_id,action,result,error) VALUES(?,?,?,?,?,?,?)",
                      (now(),module,job_id,application_id,redact(action),result,redact(error)))
    def save_deadline(self,d):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO deadlines VALUES(?,?,?,?,?)",(d["deadline_id"],d.get("application_id"),d.get("job_id"),d.get("due_at"),json.dumps(d)))
    def notify(self,key,data):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO notifications VALUES(?,?,?,NULL)",(key,json.dumps({**data,"notification_id":key}),now()))
