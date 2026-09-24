"""Developer-only isolated browser transport fixture. Never changes real candidate data."""
import hashlib,json,shutil,tempfile
from pathlib import Path
from tests.test_pipeline import profile,job
from backend.app.orchestrator import Orchestrator
from backend.app.agents.job_analyser import analyse
from backend.app.integrations.browser import prepare_packet
from backend.app.utils.config import ROOT,write_json

def main():
    base=ROOT/'tmp';base.mkdir(exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='browser-fixture-',dir=base))
    engine=Orchestrator(root);p=profile()
    write_json(root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'application_threshold':70})
    j=job(source_url='https://example.test/jobs/browser-fixture');j['analysis']=analyse(j,p,{})
    write_json(root/'data/candidate_profile.json',p)
    write_json(root/'data/browser_fixture.json',{'synthetic_test_only':True,'browser_url':'http://127.0.0.1:8767/'})
    document=root/'generated/resumes/synthetic-browser-resume.txt'
    shutil.copyfile(ROOT/'tests/fixtures/browser_form/resume.txt',document)
    engine.db.save_job(j);a=engine.db.ensure_application(j)
    for status in ('ANALYSED','SHORTLISTED','RESUME_READY','READY_TO_APPLY'):a=engine.db.update_application(a['application_id'],{},status,'Synthetic browser transport test setup, not document visual QA')
    packet=prepare_packet(p,j,{'pdf_path':str(document)})
    engine.db.update_application(a['application_id'],{'packet':packet,'score':95,'validation':{'result':'PASS','synthetic_test_stub':True,'note':'Transport fixture only; not a real resume validation'}})
    result={'root':str(root),'application_id':a['application_id'],'browser_url':'http://127.0.0.1:8767/','resume_file':str(document),'submitted':False,'test_validation_stub':True}
    write_json(root/'fixture.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
