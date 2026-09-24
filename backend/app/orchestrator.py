from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import json,uuid,sqlite3
from .utils.config import ROOT,settings,read_json,write_json,now
from .models.candidate import empty_profile
from .models.application import PREPARATION
from .integrations.database import Database
from .agents.job_finder import discover
from .services.job_service import ingest
from .agents.job_analyser import analyse
from .agents.resume_tailor import tailor
from .agents.resume_validator import validate
from .agents.cover_letter_generator import generate
from .services.application_service import prepare
from .agents.email_monitor import monitor
from .agents.deadline_manager import extract_deadlines
from .services.notification_service import notify_deadlines
from .agents.interview_support import prepare_interview

class Orchestrator:
    def __init__(self,root=ROOT):
        self.root=Path(root);self.config=settings(root);self.db=Database(self.config["database"])
        for folder in ("data/inbox/jobs","data/inbox/gmail","generated/resumes","generated/cover_letters","generated/reports","generated/interview_prep","logs","master_resume"):
            (self.root/folder).mkdir(parents=True,exist_ok=True)
        if not (self.root/"data/candidate_profile.json").exists():write_json(self.root/"data/candidate_profile.json",empty_profile())
        defaults={"job_preferences":{"target_roles":[],"preferred_locations":[],"excluded_titles":[],"application_threshold":70},"application_answers":[],"discovery_sources":{"public_ats":[]}}
        for name,fallback in defaults.items():
            path=self.root/"data"/(name+".json")
            if not path.exists():write_json(path,read_json(self.root/"data"/(name+".example.json"),fallback))
        self.config=settings(self.root)
    def run(self,live=True,generate_documents=True):
        self.config=settings(self.root)
        run_id=str(uuid.uuid4());start=now()
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            lock=c.execute("SELECT * FROM run_lock WHERE id=1").fetchone()
            if lock and lock["expires_at"]>now():raise ValueError("Another run is already active")
            c.execute("DELETE FROM run_lock WHERE id=1")
            c.execute("INSERT INTO run_lock VALUES(1,?,?)",(run_id,(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat()))
            c.execute("INSERT INTO runs VALUES(?,?,NULL,NULL)",(run_id,start))
        try:
            return self._run(run_id,start,live,generate_documents)
        except Exception as exc:
            self.db.log("orchestrator","Run failed","ERROR",error=type(exc).__name__+": "+str(exc)[:300])
            with self.db.connect() as c:c.execute("UPDATE runs SET completed_at=?,report=? WHERE run_id=?",(now(),json.dumps({"error":type(exc).__name__}),run_id))
            raise
        finally:
            with self.db.connect() as c:c.execute("DELETE FROM run_lock WHERE id=1 AND run_id=?",(run_id,))
    def _run(self,run_id,start,live,generate_documents):
        profile=read_json(self.root/"data/candidate_profile.json",empty_profile())
        if not profile.get("identity_confirmed") or profile.get("intake_deferred"):
            generate_documents=False
        prefs=read_json(self.root/"data/job_preferences.json",{})
        incoming,sources,errors=discover(self.root,self.db,live)
        counts=ingest(self.db,incoming)
        with self.db.connect() as connection:
            attempted={row['application_id'] for row in connection.execute('SELECT application_id FROM submission_attempts')}
        for job in self.db.rows("jobs"):
            job["analysis"]=analyse(job,profile,prefs);self.db.save_job(job)
            app=self.db.ensure_application(job)
            if app['application_id'] in attempted:continue  # Preserve the exact attempted packet and its history.
            if app['status'] in PREPARATION:
                from .services.preparation_lifecycle import reconcile
                app=reconcile(self.db,self.root,profile,job,app,job['analysis']['eligibility'])
            if app["status"]=="FOUND":app=self.db.update_application(app["application_id"],{},"ANALYSED","Eligibility and score computed")
            score=job["analysis"]["scoring"]["overall_score"]
            if app["status"] in PREPARATION:
                app=self.db.update_application(app["application_id"],{"score":score,"eligibility":job["analysis"]["eligibility"],"analysis_stale":False})
                if profile.get("intake_deferred"):
                    app=self.db.update_application(app["application_id"],{"next_action":"Candidate intake deferred; discover and track jobs until details are supplied"})
                if job["analysis"]["eligibility"]["status"]=="NOT_ELIGIBLE":
                    self.db.update_application(app["application_id"],{"next_action":"Outside eligibility or preference requirements"})
                elif score is not None and score>=self.config["application_threshold"] and app["status"]=="ANALYSED":
                    self.db.update_application(app["application_id"],{"next_action":"Prepare a factual resume; resolve eligibility before applying"},"SHORTLISTED","Meets relevance threshold")
            if job.get("closing_at"):
                for d in extract_deadlines("Applications close "+job["closing_at"][:10],now(),app["application_id"],job["job_id"],job["canonical_url"]):self.db.save_deadline(d)
        prepared=0; generated=0
        ranked=sorted(self.db.rows("jobs"),key=lambda j:j["analysis"]["scoring"]["overall_score"] or 0,reverse=True)
        suitable=[j for j in ranked if j['analysis']['eligibility']['status']!='NOT_ELIGIBLE']
        for job in ranked:
            app=next(a for a in self.db.rows("applications") if a["job_id"]==job["job_id"])
            if app['application_id'] in attempted:continue
            if app["status"] not in PREPARATION or job["analysis"]["eligibility"]["status"]=="NOT_ELIGIBLE" or app["score"] is None or app["score"]<self.config["application_threshold"]:continue
            if generate_documents and generated<prefs.get("resumes_per_run",5):
                try:
                    from .utils.validators import digest
                    from .integrations.browser import job_revision
                    revision=job_revision(job)
                    existing=[a for a in self.db.rows("artifacts") if a["application_id"]==app["application_id"] and a["kind"]=="resume" and not a.get('archived') and a.get("profile_hash")==digest(profile) and a.get("job_revision")==revision and a.get("generator_version")==2]
                    resume=existing[-1] if existing else tailor(profile,job,self.root)
                    validation=validate(resume,profile,job)
                    if not validation["facts_pass"]: raise ValueError("; ".join(validation["errors"]))
                    artifact=self.db.artifact(app["application_id"],"resume",resume["fingerprint"],resume)
                    app=self.db.update_application(app["application_id"],{"resume_version":artifact["artifact_id"],"validation":validation,
                        "next_action":"Resolve: "+", ".join(job["analysis"]["eligibility"]["unknowns"]+validation["errors"])})
                    cover=None
                    if job.get("cover_letter_required") or app["score"]>=90:
                        from .agents.cover_letter_validator import validate_cover
                        existing_covers=[a for a in self.db.rows('artifacts') if a['application_id']==app['application_id'] and a['kind']=='cover_letter' and not a.get('archived') and a.get('profile_hash')==digest(profile) and a.get('job_revision')==revision and a.get('generator_version')==2]
                        cover=existing_covers[-1] if existing_covers else generate(profile,job,self.root)
                        cv=validate_cover(cover,profile,job)
                        if not cv['facts_pass']:raise ValueError('; '.join(cv['errors']))
                        ca=self.db.artifact(app["application_id"],"cover_letter",cover["fingerprint"],cover)
                        app=self.db.update_application(app["application_id"],{"cover_letter_version":ca["artifact_id"],"cover_validation":cv['result'],"cover_validation_details":cv})
                    if validation["result"]=="PASS" and app["status"]=="SHORTLISTED":
                        app=self.db.update_application(app["application_id"],{},"RESUME_READY","Resume content and visual validation passed")
                    if not app.get("packet") or app["packet"].get("profile_hash")!=digest(profile) or app["packet"].get("job_revision")!=revision or app["packet"].get("documents",{}).get("resume")!=resume["pdf_path"]:
                        app=prepare(self.db,profile,job,app,resume,cover)
                    if app["status"]=="RESUME_READY" and job["analysis"]["eligibility"]["status"]=="ELIGIBLE" and (not job.get('cover_letter_required') or app.get('cover_validation')=='PASS'):
                        app=self.db.update_application(app["application_id"],{"next_action":"Open and complete employer form"},"READY_TO_APPLY","Eligibility confirmed")
                    generated+=1
                    if not existing:prepared+=1
                except Exception as exc:
                    message=type(exc).__name__+": "+str(exc)[:250]
                    errors.append({"source":job["company"],"error":message,"next_action":"Repair resume before application"})
                    self.db.update_application(app["application_id"],{"next_action":"Resume generation/validation needs attention","error":message})
                    self.db.log("resume","Prepare verified resume","FAIL",error=message,job_id=job["job_id"],application_id=app["application_id"])
        mail=monitor(self.root,self.db,profile) if self.config['post_submission_enabled'] else {"status":"USER_MANAGED_POST_APPLICATION","processed":0}
        for app in self.db.rows("applications"):
            if self.config['post_submission_enabled'] and profile.get("identity_confirmed") and app["status"] in {"INTERVIEW","SECOND_INTERVIEW","FINAL_INTERVIEW"}:
                path=prepare_interview(profile,self.db.job(app["job_id"]),self.root)
                self.db.update_application(app["application_id"],{"interview_prep":path})
        deadlines=notify_deadlines(self.db) if self.config['post_submission_enabled'] else []
        report={"run_id":run_id,"started_at":start,"completed_at":now(),"dry_run":self.config["dry_run"],"automation_level":self.config["automation_level"],
                "jobs_found":len(incoming),**counts,"strong_matches":sum((j["analysis"]["scoring"]["overall_score"] or 0)>=80 and j["analysis"]["eligibility"]["status"]!="NOT_ELIGIBLE" for j in ranked),
                "applications_prepared":prepared,"resumes_processed":generated,"applications_submitted":0,"sources":sources,
                "excluded_jobs":len(ranked)-len(suitable),
                "email":mail,"deadlines":deadlines,"errors":errors,
                "candidate_identity_confirmed":profile.get("identity_confirmed",False),
                "candidate_intake_deferred":profile.get("intake_deferred",False),
                "top_jobs":[{"job_id":j["job_id"],"company":j["company"],"title":j["title"],"score":j["analysis"]["scoring"]["overall_score"],
                            "eligibility":j["analysis"]["eligibility"]["status"],"unknowns":j["analysis"]["eligibility"]["unknowns"],"url":j["canonical_url"]} for j in suitable[:10]],
                "status_counts":dict(Counter(a["status"] for a in self.db.rows("applications")))}
        report["applications_waiting_for_approval"]=report["status_counts"].get("WAITING_FOR_APPROVAL",0)
        write_json(self.root/"generated/reports/latest.json",report)
        write_json(self.root/"generated/reports"/(run_id+".json"),report)
        with self.db.connect() as c:c.execute("UPDATE runs SET completed_at=?,report=? WHERE run_id=?",(now(),json.dumps(report),run_id))
        self.db.log("orchestrator","Completed run "+run_id,"DRY_RUN" if self.config["dry_run"] else "COMPLETE")
        return report
    def state(self):
        applications=self.db.rows("applications"); submitted=[a for a in applications if a.get("date_applied")]
        history={a["application_id"]:self.db.history(a["application_id"]) for a in applications}
        n=len(submitted)
        def rate(states):
            hits=sum(any(h["new_status"] in states for h in history[a["application_id"]]) for a in submitted)
            return round(hits/n*100,1) if n else 0
        jobs=self.db.rows("jobs"); scores=[j.get("analysis",{}).get("scoring",{}).get("overall_score") for j in jobs]
        scores=[s for s in scores if s is not None]
        return {"jobs":jobs,"applications":applications,"history":history,"artifacts":[a for a in self.db.rows("artifacts") if not a.get("archived")],
                "email_events":self.db.rows("email_events"),"deadlines":self.db.rows("deadlines"),"logs":self.db.rows("activity_logs"),
                "notifications":self.db.rows("notifications"),"settings":self.config,"preferences":read_json(self.root/"data/job_preferences.json",{}),
                "profile":read_json(self.root/"data/candidate_profile.json",{}),"answers":read_json(self.root/"data/application_answers.json",[]),
                "integrations":read_json(self.root/"data/integrations.json",{}),"report":read_json(self.root/"generated/reports/latest.json",{}),
                "schedule":read_json(self.root/"data/schedule_status.json",{}),
                "metrics":{"jobs_discovered":len(jobs),"applications_submitted":n,"average_match_score":round(sum(scores)/len(scores),1) if scores else None,
                           "response_rate":rate({"APPLICATION_RECEIVED","ASSESSMENT","PHONE_SCREEN","INTERVIEW","OFFER","REJECTED"}),
                           "assessment_rate":rate({"ASSESSMENT"}),"interview_rate":rate({"INTERVIEW","SECOND_INTERVIEW","FINAL_INTERVIEW"}),"offer_rate":rate({"OFFER"})}}
    def mail_only(self):
        self.config=settings(self.root)
        profile=read_json(self.root/"data/candidate_profile.json",empty_profile())
        if not self.config['post_submission_enabled']:
            mail={"state":"USER_MANAGED_POST_APPLICATION","processed":0}
        elif profile.get("intake_deferred") or not profile.get("identity_confirmed"):
            mail={"state":"CANDIDATE_INTAKE_DEFERRED","processed":0}
        elif not any(a.get("date_applied") for a in self.db.rows("applications")):
            mail={"state":"NO_SUBMITTED_APPLICATIONS","processed":0}
        else:
            mail=monitor(self.root,self.db,profile)
            for app in self.db.rows("applications"):
                if app["status"] in {"INTERVIEW","SECOND_INTERVIEW","FINAL_INTERVIEW"}:
                    path=prepare_interview(profile,self.db.job(app["job_id"]),self.root)
                    self.db.update_application(app["application_id"],{"interview_prep":path})
        report={"stage":"MAIL","completed_at":now(),"email":mail,"deadlines":notify_deadlines(self.db) if self.config['post_submission_enabled'] else [],"applications_submitted":0}
        write_json(self.root/"generated/reports/latest-mail.json",report)
        return report
