"""Single controlled browser workflow; adapters must use a permitted visible browser.

This module does not bundle stealth automation or invent selectors. The driver supplies
observations from the actual page. Unit tests use a fake driver on synthetic fixtures.
"""
from ..agents.application_agent import answer_question,reserve_submission,confirm_submission,LEGAL_MARKERS
from ..services.application_service import record_form_review
from ..models.candidate import verified
from ..utils.config import now
from ..utils.validators import normal
from ..utils.answer_memory import revisions,review_hash
from .browser import packet_hash,record_blocker
from .form_steps import FormSteps,resolve_control

class ApplicationWorkflow:
    def __init__(self,db,driver):self.db=db;self.driver=driver

    def fill(self,profile,job,application,answers):
        aid=application["application_id"];packet=application.get("packet") or {}
        if not profile.get("identity_confirmed") or profile.get("intake_deferred"):
            raise ValueError("Verified candidate intake required")
        if application["status"]!="READY_TO_APPLY" or (application.get("validation") or {}).get("result")!="PASS":
            raise ValueError("Eligible application and validated documents required")
        if job.get("analysis",{}).get("eligibility",{}).get("status")!="ELIGIBLE":raise ValueError("Eligibility not confirmed")
        if (job.get('cover_letter_required') or packet.get('documents',{}).get('cover_letter')) and application.get('cover_validation')!='PASS':raise ValueError('Cover letter validation required before uploading')
        progress=application.get('form_progress')
        if not progress or progress.get('packet_hash')!=packet_hash(packet):
            progress=None
            self.driver.navigate(job["canonical_url"])
        page=self.driver.observe()
        if progress or 'step_id' in page:
            return FormSteps(self.db,self.driver).fill(profile,job,application,answers,page,progress)
        for flag,code in (("captcha","CAPTCHA"),("mfa","MFA"),("login_required","LOGIN_REQUIRED")):
            if page.get(flag):
                record_blocker(self.db,aid,code,"Complete the manual website step, then inspect the form again")
                return {"status":"BLOCKED","reason":code}
        if page.get("website_permits_automation") is not True or not page.get("website_policy_evidence"):
            record_blocker(self.db,aid,"AUTOMATION_PROHIBITED","Verify website permission before automated entry")
            return {"status":"BLOCKED","reason":"WEBSITE_PERMISSION_UNCONFIRMED"}
        questions=[];unresolved=[]
        for control in page.get("fields",[]):
            question=control["question"];field=control.get("candidate_field")
            answer=resolve_control(control,profile,packet,answers)
            q={"question":question,"answer":answer.get("answer"),"verified":answer["action"]=="AUTOFILL","requires_manual_confirmation":answer["action"]!="AUTOFILL"}
            questions.append(q)
            if answer["action"]=="AUTOFILL":self.driver.fill(control["locator"],answer["answer"])
            else:unresolved.append(question)
        for kind,path in packet.get("documents",{}).items():
            if not path:continue
            locator=page.get("upload_controls",{}).get(kind)
            if not locator:
                record_blocker(self.db,aid,"RESUME_UPLOAD_FAILURE" if kind=="resume" else "COVER_LETTER_UPLOAD_FAILURE","Upload control not observed; inspect the employer form")
                return {"status":"BLOCKED","reason":"UPLOAD_CONTROL_NOT_OBSERVED"}
            self.driver.upload(locator,path)
        final=self.driver.observe()
        seen={normal(q['question']) for q in questions}
        for control in final.get('fields',[]):
            question=control['question']
            if normal(question) not in seen:
                questions.append({'question':question,'answer':None,'verified':False,'requires_manual_confirmation':True})
                unresolved.append(question);seen.add(normal(question))
        evidence={"expected_packet_hash":packet_hash(packet),"observation_source":final.get("observation_source"),
            "answer_memory_hash":review_hash(revisions(answers),questions),
            "form_reviewed":final.get("form_reviewed") is True,"fields_filled":not unresolved and final.get("fields_filled") is True,
            "uploads_confirmed":final.get("uploads_confirmed") is True,"legal_review_complete":final.get("legal_review_complete") is True,
            "website_permits_automation":final.get("website_permits_automation") is True,"website_policy_evidence":final.get("website_policy_evidence"),
            "observed_at":now(),"questions":questions,**{f:final.get(f) is True for f in ("captcha","mfa","login_required")}}
        updated=record_form_review(self.db,aid,evidence)
        if unresolved:record_blocker(self.db,aid,"UNKNOWN_QUESTION","Verified or manual answers required: "+"; ".join(unresolved))
        return {"status":updated["status"],"unresolved_questions":unresolved,"submitted":False}

    def submit(self,config,profile,job,application):
        reserve_submission(config,profile,job,application,self.db)
        try:
            evidence=self.driver.submit_and_observe_confirmation()
            return confirm_submission(self.db,application["application_id"],evidence)
        except Exception as exc:
            # Keep the unique reservation forever until explicit, evidence-backed reconciliation.
            self.db.log("browser","Submission outcome uncertain","NEEDS_REVIEW",error=type(exc).__name__,application_id=application["application_id"])
            self.db.update_application(application["application_id"],{"next_action":"Submission outcome uncertain; verify employer receipt before any retry"})
            raise
