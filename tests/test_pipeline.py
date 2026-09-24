import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date,datetime,timezone,timedelta
from backend.app.models.candidate import empty_profile,verify
from backend.app.models.job import normalise
from backend.app.models.application import transition_allowed
from backend.app.agents.duplicate_checker import same_job
from backend.app.agents.eligibility_checker import evaluate
from backend.app.agents.job_scorer import score
from backend.app.agents.resume_tailor import tailor
from backend.app.agents.resume_validator import validate
from backend.app.agents.cover_letter_generator import generate
from backend.app.agents.application_agent import gates,answer_question,reserve_submission,confirm_submission
from backend.app.agents.email_classifier import classify
from backend.app.agents.email_monitor import match_application
from backend.app.agents.deadline_manager import extract_deadlines
from backend.app.integrations.database import Database
from backend.app.integrations.mcp_jobs import JobsMCP
from backend.app.integrations.browser import prepare_packet
from backend.app.services.job_service import ingest
from backend.app.orchestrator import Orchestrator
from backend.app.utils.config import write_json,now
from backend.app.utils.validators import contains_skill
from backend.app.utils.logger import redact

def profile():
    p=empty_profile()
    values={"full_name":"Test Candidate","email":"candidate@example.test","location":"Melbourne, VIC","phone":"+61 400 000 000",
        "education":[{"qualification":"Bachelor of Software Engineering","institution":"Example University","dates":"2026","bullets":[]}],
        "technical_skills":["Python","React","C++","Git","Linux","OOP"],"projects":[{"name":"Local Demo","technologies":"Python, React","dates":"2026","bullets":["Built a local test application with validation."]}],
        "employment_experience":[{"role":"Test Assistant","company":"Example Company","dates":"2025","bullets":["Supported a test project."]}],
        "work_rights":True,"graduation_date":"2027-06-01","citizenship":"Australian","availability":"December 2026"}
    for k,v in values.items():verify(p,k,v,"Synthetic unit-test fixture")
    p["identity_confirmed"]=True
    return p
def job(**changes):
    return normalise({"company":"Example Employer","title":"Software Engineering Intern","location":"Melbourne, VIC, Australia","source":"test fixture",
        "source_url":"https://example.test/jobs/42","description":"Synthetic fixture only; never submit.","required_skills":["Python"],
        "preferred_skills":["React"],"requirements":[{"field":"education","op":"contains","value":"Software Engineering","label":"Relevant degree"}],
        "requirements_reviewed":True,"listing_state":"OPEN",**changes})

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="job-agent-test-")
        self.root=Path(self.temp.name)
        self.db=Database(self.root/"data/test.sqlite3")
        self.p=profile();self.j=job();self.prefs={"excluded_titles":["Senior Engineer"],"application_threshold":70}
    def tearDown(self):self.temp.cleanup()
    def test_normalisation_preserves_unknown(self):
        j=job();self.assertIsNone(j["salary_min"]);self.assertIsNone(j["graduation_date"] if "graduation_date" in j else None)
        self.assertEqual(j["job_id"],job()["job_id"])
    def test_duplicate_across_boards(self):
        self.assertTrue(same_job(self.j,job(source="other",source_url="https://another.test/advert/9")))
    def test_two_roles_on_shared_careers_url_are_not_duplicates(self):
        b=job(title="Junior Software Developer")
        self.assertFalse(same_job(self.j,b));self.assertEqual(ingest(self.db,[self.j,b])["new_jobs"],2)
    def test_two_requisitions_preserved(self):
        self.assertFalse(same_job(job(external_id="1"),job(external_id="2")))
    def test_prefer_official_listing_without_new_application(self):
        a=job(is_official=False);b=job(is_official=True,source="employer",source_url="https://employer.test/job/42")
        ingest(self.db,[a,b]);self.assertEqual(len(self.db.rows("jobs")),1);self.assertEqual(len(self.db.rows("applications")),1)
        self.assertIn("employer.test",self.db.rows("jobs")[0]["canonical_url"])
    def test_unknown_rights_block(self):
        verify(self.p,"work_rights",None,"fixture")
        self.assertEqual(evaluate(self.j,self.p,self.prefs)["status"],"NEEDS_REVIEW")
    def test_unknown_visa_string_not_rights(self):
        self.p["work_rights"]="student visa"
        self.assertEqual(evaluate(self.j,self.p,self.prefs)["status"],"NEEDS_REVIEW")
    def test_invalid_profile_types(self):
        with self.assertRaises(ValueError):verify(self.p,"requires_sponsorship","no","fixture")
        with self.assertRaises(ValueError):verify(self.p,"graduation_date","sometime next year","fixture")
    def test_known_failure_not_eligible(self):
        self.p["citizenship"]="New Zealand"
        j=job(requirements=[{"field":"citizenship","op":"equals","value":"Australian","label":"Citizenship"}])
        self.assertEqual(evaluate(j,self.p,self.prefs)["status"],"NOT_ELIGIBLE")
    def test_degree_missing_is_review(self):
        verify(self.p,"education",None,"fixture")
        self.assertEqual(evaluate(self.j,self.p,self.prefs)["status"],"NEEDS_REVIEW")
    def test_eligible_with_verified_requirements(self):
        self.assertEqual(evaluate(self.j,self.p,self.prefs)["status"],"ELIGIBLE")
    def test_closed_and_senior_excluded(self):
        self.assertEqual(evaluate(job(closing_at="2020-01-01"),self.p,self.prefs)["status"],"NOT_ELIGIBLE")
        self.assertEqual(evaluate(job(title="Senior Software Engineer"),self.p,self.prefs)["status"],"NOT_ELIGIBLE")
    def test_case_insensitive_skills(self):
        self.assertTrue(contains_skill('["Python", "OOP", "C++"]',"Python"))
        self.assertTrue(contains_skill('["Python", "OOP", "C++"]',"OOP"))
        self.assertFalse(contains_skill("JavaScript","Java"))
        self.assertFalse(contains_skill("C++","C#"))
    def test_optional_skills_do_not_disqualify(self):
        j=job(preferred_skills=["Rust","Go","Elixir"]);e=evaluate(j,self.p,self.prefs)
        s=score(j,self.p,e,self.prefs)
        self.assertEqual(e["status"],"ELIGIBLE");self.assertEqual(s["components"]["technical_skills"],30)
        self.assertEqual(s["optional_missing_skills"],["Rust","Go","Elixir"])
    def test_mcp_write_action_refused(self):
        with self.assertRaises(ValueError):JobsMCP().call("apply_to_job",{})
    def test_mcp_failure_does_not_lose_official_jobs(self):
        write_json(self.root/"data/candidate_profile.json",self.p);write_json(self.root/"data/job_preferences.json",{"application_threshold":70})
        write_json(self.root/"data/inbox/jobs/fixture.json",[self.j])
        with patch("backend.app.agents.job_finder.JobsMCP.search",side_effect=TimeoutError):
            r=Orchestrator(self.root).run(live=True,generate_documents=False)
        self.assertEqual(r["new_jobs"],1);self.assertTrue(r["errors"]);self.assertEqual(r["applications_submitted"],0)
    def test_repeat_run_idempotent(self):
        write_json(self.root/"data/candidate_profile.json",self.p);write_json(self.root/"data/job_preferences.json",{"application_threshold":70})
        write_json(self.root/"data/inbox/jobs/fixture.json",[self.j])
        o=Orchestrator(self.root);a=o.run(False,False);b=o.run(False,False)
        self.assertEqual(a["new_jobs"],1);self.assertEqual(b["new_jobs"],0);self.assertEqual(len(o.db.rows("applications")),1)
    def test_resume_generation_preserves_facts(self):
        m=tailor(self.p,self.j,self.root);m["visual_review"]="PASS"
        v=validate(m,self.p,self.j)
        self.assertEqual(v["result"],"PASS",v["errors"])
        self.assertTrue(Path(m["docx_path"]).exists());self.assertTrue(Path(m["pdf_path"]).exists())
    def test_invented_claim_fails(self):
        m=tailor(self.p,self.j,self.root);m["claims"].append({"field":"technical_skills","text":"Kubernetes expert"})
        self.assertFalse(validate(m,self.p,self.j)["facts_pass"])
    def test_unmanifested_docx_text_fails(self):
        from docx import Document
        m=tailor(self.p,self.j,self.root)
        doc=Document(m["docx_path"]);doc.add_paragraph("Invented PhD at Imaginary University");doc.save(m["docx_path"])
        self.assertFalse(validate(m,self.p,self.j)["facts_pass"])
    def test_resume_identity_and_visual_gate(self):
        m=tailor(self.p,self.j,self.root);self.p["identity_confirmed"]=False
        v=validate(m,self.p,self.j);self.assertEqual(v["result"],"FAIL")
    def test_wrong_job_fails(self):
        m=tailor(self.p,self.j,self.root)
        self.assertFalse(validate(m,self.p,job(company="Different Employer"))["facts_pass"])
    def test_cover_letter_uses_real_project(self):
        m=generate(self.p,self.j,self.root)
        self.assertIn("Local Demo",m["text"]);self.assertIn("Example Employer",m["text"]);self.assertTrue(Path(m["pdf_path"]).exists())
    def test_answer_memory_legal_unknown_and_verified(self):
        answers=[{"question":"Your preferred name?","answer":"Test","verified":True,"requires_manual_confirmation":False}]
        self.assertEqual(answer_question("Your preferred name?",answers)["action"],"AUTOFILL")
        self.assertEqual(answer_question("What is your GPA?",answers)["action"],"ASK")
        self.assertEqual(answer_question("Are you authorised to work?",answers)["action"],"MANUAL")
    def test_tracking_rejects_false_application(self):
        ingest(self.db,[self.j]);a=self.db.rows("applications")[0]
        with self.assertRaises(ValueError):self.db.update_application(a["application_id"],{},"APPLIED")
        self.assertEqual(self.db.application(a["application_id"])["status"],"FOUND")
    def test_status_cannot_regress(self):
        self.assertFalse(transition_allowed("INTERVIEW","APPLICATION_RECEIVED"))
        self.assertFalse(transition_allowed("REJECTED","INTERVIEW"))
    def test_dry_run_blocks_submission_even_when_approved(self):
        ingest(self.db,[self.j]);a=self.db.rows("applications")[0]
        g=gates({"dry_run":True,"production_approved":True,"automation_level":2,"application_threshold":70},self.p,self.j,a,self.db)
        self.assertIn("DRY_RUN",g["blockers"]);self.assertFalse(g["allowed"])
    def test_unknown_form_never_submits(self):
        ingest(self.db,[self.j]);a=self.db.rows("applications")[0]
        config={"dry_run":False,"production_approved":True,"automation_level":3,"application_threshold":70}
        with self.assertRaises(ValueError):reserve_submission(config,self.p,self.j,a,self.db)
    def test_duplicate_attempt_is_database_enforced(self):
        ingest(self.db,[self.j]);a=self.db.rows("applications")[0]
        with self.db.connect() as c:c.execute("INSERT INTO submission_attempts VALUES(?,?,?,?,?,?)",(self.j["job_id"],a["application_id"],"RESERVED","fake-fixture",None,now()))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as c:c.execute("INSERT INTO submission_attempts VALUES(?,?,?,?,?,?)",(self.j["job_id"],a["application_id"],"RESERVED","fake-fixture",None,now()))
    def test_email_contextual_classification(self):
        cases=[("Thank you for applying","We have received your application for the developer role.","APPLICATION_CONFIRMATION"),
               ("Your application","Unfortunately we will not progress your application for this position.","REJECTION"),
               ("Assessment invitation","Please complete the coding assessment within 48 hours using this link.","ASSESSMENT"),
               ("Interview invitation","We would like to invite you to interview. Please send your availability for a video meeting.","INTERVIEW"),
               ("Job offer","We are pleased to offer you the software developer position. Your employment start date follows.","OFFER")]
        for subject,body,expected in cases:self.assertEqual(classify({"subject":subject,"body":body})["classification"],expected)
    def test_job_alert_not_application(self):
        self.assertEqual(classify({"subject":"Recommended jobs: interview tips","body":"Thank you for applying to our job alerts. Please complete your profile."})["classification"],"UNKNOWN")
    def test_email_snippet_needs_full_body(self):
        self.assertEqual(classify({"subject":"Thank you for applying"})["classification"],"UNKNOWN")
    def test_email_match_requires_known_submitted_application(self):
        app={"application_id":"fake","job_id":self.j["job_id"],"company":"Example Employer","role":"Software Engineering Intern","date_applied":None}
        msg={"subject":"Example Employer Software Engineering Intern","body":"Thank you for applying","received_at":now()}
        self.assertIsNone(match_application(msg,[app],[self.j])[0])
        app["date_applied"]="2026-01-01T00:00:00+00:00"
        self.assertEqual(match_application(msg,[app],[self.j])[0]["application_id"],"fake")
    def test_deadline_absolute_and_relative(self):
        a=extract_deadlines("Applications close 30 September 2026","2026-09-07T00:00:00+00:00")
        self.assertEqual(a[0]["due_at"],"2026-09-30")
        b=extract_deadlines("Complete the assessment within 48 hours","2026-09-07T00:00:00+00:00")
        self.assertEqual(b[0]["due_at"],"2026-09-09T00:00:00+00:00")
    def test_ambiguous_interview_time_requires_review(self):
        d=extract_deadlines("Interview on 2026-09-18 at 2pm","2026-09-07T00:00:00+00:00")
        self.assertEqual(d[0]["review"],"NEEDS_REVIEW")
    def test_logs_redact_secrets(self):
        self.assertNotIn("secret123",redact("token=secret123"))
        self.assertEqual(redact({"password":"secret123"})["password"],"[REDACTED]")
if __name__=="__main__":unittest.main()

