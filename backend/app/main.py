"""Local-only HTTP API and built React dashboard. No external writes or submission endpoint."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,mimetypes,secrets,threading
from .orchestrator import Orchestrator
from .utils.config import ROOT,read_json,write_json
from .models.candidate import verify,FIELDS
from .services.application_service import approve,record_form_review

def create_server(root=ROOT,port=None):
    engine=Orchestrator(root);port=engine.config["port"] if port is None else port
    csrf=secrets.token_urlsafe(32);ui=Path(root)/"frontend/dist"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def local_request(self):
            allowed={f"127.0.0.1:{port}",f"localhost:{port}"}
            return self.headers.get("Host") in allowed
        def respond(self,value,status=200):
            payload=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            if not self.local_request():return self.respond({"error":"Invalid host"},403)
            path=urlsplit(self.path).path
            if path=="/api/health":return self.respond({"ok":True,"dry_run":engine.config["dry_run"]})
            if path=="/api/state":return self.respond({**engine.state(),"csrf":csrf})
            if path.startswith("/api/artifact/"):
                parts=path.split("/"); aid=parts[3];fmt=parts[4] if len(parts)>4 else "pdf"
                if fmt not in {"pdf","docx"}:return self.respond({"error":"Invalid format"},400)
                art=next((a for a in engine.db.rows("artifacts") if a["artifact_id"]==aid),None)
                if not art:return self.respond({"error":"Not found"},404)
                file=Path(art[fmt+"_path"]).resolve()
                if not file.is_relative_to((Path(root)/"generated").resolve()):return self.respond({"error":"Invalid artifact"},403)
                if not file.is_file():return self.respond({"error":"Missing artifact"},404)
            elif path.startswith("/api/"):return self.respond({"error":"Not found"},404)
            else:
                file=(ui/unquote(path).lstrip("/")).resolve()
                if not file.is_relative_to(ui.resolve()):return self.respond({"error":"Invalid path"},403)
                if not file.is_file():file=ui/"index.html"
                if not file.is_file():return self.respond({"error":"Build the dashboard first"},503)
            data=file.read_bytes()
            self.send_response(200);self.send_header("Content-Type",mimetypes.guess_type(str(file))[0] or "application/octet-stream")
            self.send_header("Content-Length",str(len(data)));self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'")
            self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if not self.local_request() or self.headers.get("X-Job-Agent-CSRF")!=csrf:return self.respond({"error":"Invalid request token"},403)
            origin=self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{port}",f"http://localhost:{port}"}:return self.respond({"error":"Invalid origin"},403)
            try:
                length=int(self.headers.get("Content-Length","0"))
                if length<0 or length>1_000_000:raise ValueError("Invalid request size")
                data=json.loads(self.rfile.read(length) or b"{}")
                path=urlsplit(self.path).path
                if path=="/api/run":
                    result=engine.run(live=True);return self.respond(result)
                if path=="/api/preferences":
                    allowed={"target_roles","preferred_locations","excluded_titles","application_threshold","resumes_per_run","salary_min"}
                    if set(data)-allowed:raise ValueError("Unsupported preference")
                    if "application_threshold" in data and (not isinstance(data["application_threshold"],int) or not 0<=data["application_threshold"]<=100):raise ValueError("Threshold must be 0 to 100")
                    if "resumes_per_run" in data and (not isinstance(data["resumes_per_run"],int) or not 0<=data["resumes_per_run"]<=20):raise ValueError("Resume limit must be 0 to 20")
                    for key in ("target_roles","preferred_locations","excluded_titles"):
                        if key in data and (not isinstance(data[key],list) or not all(isinstance(v,str) and len(v)<=150 for v in data[key])):raise ValueError("Expected a list of text values")
                    prefs=read_json(Path(root)/"data/job_preferences.json",{})
                    policy_keys={'target_roles','preferred_locations','excluded_titles','application_threshold','salary_min'}
                    changed=any(prefs.get(key)!=data[key] for key in policy_keys & data.keys())
                    if changed:
                        from .services.preparation_lifecycle import invalidate
                        invalidate(engine.db,'Job preferences changed; rerun eligibility and review before applying',archive_documents=False)
                    prefs.update(data);write_json(Path(root)/"data/job_preferences.json",prefs)
                    from .utils.config import settings
                    engine.config=settings(root);return self.respond({"saved":True})
                if path=="/api/profile":
                    p=read_json(Path(root)/"data/candidate_profile.json",{})
                    for field,value in data.get("fields",{}).items():verify(p,field,value,"User-confirmed dashboard entry")
                    if data.get("identity_confirmed") is True:
                        from .models.candidate import verified
                        if not verified(p,"full_name") or not verified(p,"email"):raise ValueError("Supply verified name and email before confirming candidate identity")
                        p["identity_confirmed"]=True;p["intake_deferred"]=False
                    write_json(Path(root)/"data/candidate_profile.json",p)
                    from .services.candidate_intake import invalidate_preparations
                    invalidate_preparations(engine.db,"Candidate facts changed; regenerate documents and recheck eligibility")
                    return self.respond({"saved":True})
                if path=="/api/form-review":
                    return self.respond(record_form_review(engine.db,data["application_id"],data["evidence"]))
                if path=="/api/notes":
                    engine.db.update_application(data["application_id"],{"notes":str(data["notes"])[:10000]});return self.respond({"saved":True})
                if path=="/api/approve":
                    return self.respond(approve(engine.db,data["application_id"],data["packet_hash"]))
                if path=="/api/answer":
                    from .utils.validators import normal
                    from .utils.config import now
                    entry={"question":str(data["question"]),"normalised_question":normal(str(data["question"])),"answer":data.get("answer"),
                           "verified":data.get("verified") is True,"last_verified":now(),"requires_manual_confirmation":data.get("requires_manual_confirmation",True)}
                    answers=read_json(Path(root)/"data/application_answers.json",[])
                    previous=next((a for a in answers if a['normalised_question']==entry['normalised_question']),None)
                    if previous is not None and any(previous.get(key)!=entry.get(key) for key in ('answer','verified','requires_manual_confirmation')):
                        from .services.preparation_lifecycle import invalidate_answer_users
                        invalidate_answer_users(engine.db,entry['normalised_question'],'A stored answer changed; refill the affected question and review this application again')
                    answers=[a for a in answers if a["normalised_question"]!=entry["normalised_question"]]+[entry]
                    write_json(Path(root)/"data/application_answers.json",answers)
                    with engine.db.connect() as c:c.execute("INSERT INTO application_answers VALUES(?,?) ON CONFLICT(normalised_question) DO UPDATE SET data=excluded.data",(entry["normalised_question"],json.dumps(entry)))
                    return self.respond({"saved":True})
                return self.respond({"error":"Not found"},404)
            except (ValueError,KeyError,TypeError) as exc:return self.respond({"error":str(exc)},400)
            except Exception as exc:
                engine.db.log("api","Request failed","ERROR",error=type(exc).__name__)
                return self.respond({"error":"Operation failed; check activity log"},500)
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    port=server.server_address[1]
    return server

def serve(root=ROOT,port=None):
    server=create_server(root,port);port=server.server_address[1]
    print(f"Job Agent dashboard: http://127.0.0.1:{port}",flush=True)
    server.serve_forever()
