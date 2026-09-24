"""Actual AIHawk action layer + durable application queue, local fixture only.

This is deliberately NOT an employer controller. No submit or arbitrary click
is exposed; the optional multi-page mode allows one exact local Next button.
"""
import argparse,asyncio,hashlib,json,sys,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aihawk.mcp import actions
from backend.app.integrations.aihawk_session import AIHawkEdgeSession
from backend.app.integrations.aihawk_upload import upload_document
from backend.app.utils.config import now,write_json

ORIGIN='http://127.0.0.1:8767'

async def run(python,multi_page=False,native_dropdown=False):
    multi_page=multi_page or native_dropdown
    async def command(*args):
        proc=await asyncio.create_subprocess_exec(python,*args,cwd=ROOT,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            out,err=await asyncio.wait_for(proc.communicate(),30)
        except BaseException:
            if proc.returncode is None:proc.kill()
            await proc.wait();raise
        if proc.returncode:raise RuntimeError(err.decode(errors='replace'))
        return json.loads(out.decode())
    fixture=await command('-m','tests.browser_fixture_setup')
    root=Path(fixture['root']).resolve()
    assert root.is_relative_to(ROOT/'tmp') and fixture['test_validation_stub'] is True
    assert fixture['browser_url']==ORIGIN+'/'
    async def cli(*args):return await command('-m','backend.app.cli','--root',str(root),*args)
    fixture_files=ROOT/'tests/fixtures/browser_form'
    files={'/':('text/html',(fixture_files/('dropdown.html' if native_dropdown else 'multistep.html' if multi_page else 'index.html')).read_bytes()),
           '/app.js':('text/javascript',(fixture_files/'app.js').read_bytes())}
    if multi_page:files['/steps.js']=('text/javascript',(fixture_files/'steps.js').read_bytes())
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.headers.get('Host')!='127.0.0.1:8767' or self.path not in files:
                self.send_error(403);return
            mime,body=files[self.path];self.send_response(200)
            self.send_header('Content-Type',mime+'; charset=utf-8')
            self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'none'; form-action 'none'; frame-src 'none'")
            self.end_headers();self.wfile.write(body)
        def do_POST(self):self.send_error(403)
    server=ThreadingHTTPServer(('127.0.0.1',8767),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    session=AIHawkEdgeSession();worker=None;reader=None;blocked=[];executed=[];phases=[]
    async def observe():
        snapshot=json.loads(await actions.snapshot(session))
        assert snapshot['url']==ORIGIN+'/'
        policy=await actions.read_text(session,'#policy')
        assert 'Automated filling and file selection are permitted here' in policy
        controls=snapshot['interactive_elements']
        inputs=[x for x in controls if x.get('tag')=='input']
        assert {x.get('id') for x in inputs}.issubset({'name','email','preferred','resume'})
        page=session.page()
        assert await page.is_disabled('button[type=submit]')
        receipt=json.loads(await actions.read_text(session,'#receipt'))
        assert receipt['submitted'] is False and receipt['test_only'] is True
        result={'observation_source':'Actual installed AIHawk snapshot and local fixture receipt',
            'application_identity_verified':True,'application_identity_evidence':'Owned synthetic fixture bound to the exact isolated application',
            'observed_url':snapshot['url'],'website_permits_automation':True,'website_policy_evidence':policy,
            'fields':[{'question':label,'candidate_field':field,'locator':{'id':identity}}
                for identity,label,field in [('name','Full name','full_name'),('email','Email','email'),('preferred','Preferred name',None)]],
            'upload_controls':{'resume':{'id':'resume'}},'captcha':False,'mfa':False,'login_required':False,
            'form_reviewed':True,'legal_review_complete':True,
            'fields_filled':receipt['name']=='Test Candidate' and receipt['email']=='candidate@example.test' and receipt['preferred_name']=='Test',
            'uploads_confirmed':receipt['file_selected'] is True}
        if multi_page:
            step=await page.get_attribute('#application','data-step')
            assert step in ('contact','review')
            identity=await actions.read_text(session,'#identity')
            assert identity=='Example Employer - Software Engineering Intern'
            result.update(step_id=step,is_final_step=step=='review',
                application_identity_verified=True,application_identity_evidence=identity,
                confirmed_uploads=['resume'] if receipt['file_selected'] else [],next_control=None)
            if step=='contact':
                assert await page.is_visible('#contact') and not await page.is_visible('#review-step')
                assert await page.get_attribute('#next','type')=='button'
                assert await page.get_attribute('#next','data-next-step')=='review'
                assert await actions.read_text(session,'#next')=='Next'
                result['next_control']={'kind':'CONTINUE','submits_application':False,'label':'Next',
                    'locator':{'id':'next'},'evidence':'Owned fixture type=button moves to observed review fieldset; no network submission',
                    'next_step_id':'review'}
                result['fields']=result['fields'][:2]
                result['fields_filled']=receipt['name']=='Test Candidate' and receipt['email']=='candidate@example.test'
            else:
                assert not await page.is_visible('#contact') and await page.is_visible('#review-step')
                result['fields']=result['fields'][2:];result['upload_controls']={}
        for field in result['fields']:
            assert await page.is_visible('#'+field['locator']['id'])
        return result
    async def selector(identity):
        snapshot=json.loads(await actions.snapshot(session))
        assert snapshot['url']==ORIGIN+'/'
        matches=[x for x in snapshot['interactive_elements'] if x.get('id')==identity]
        assert len(matches)==1 and matches[0]['tag'] in {'input','select'}
        return matches[0]['selector']
    try:
        await session.start()
        async def route(r):
            if not r.request.url.startswith(ORIGIN+'/') or r.request.method!='GET':
                blocked.append(r.request.url);await r.abort();return
            await r.continue_()
        await session._context.route('**/*',route)
        for phase in (1,2):
            worker=await asyncio.create_subprocess_exec(python,'-m','backend.app.cli','--root',str(root),
                'browser-run',fixture['application_id'],'--timeout','30',cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            reader=asyncio.create_task(worker.communicate())
            while not reader.done():
                queued=(await cli('browser-next'))['command']
                if not queued:
                    await asyncio.sleep(.1);continue
                assert queued['application_id']==fixture['application_id']
                action=queued['action'];payload=queued['payload']
                try:
                    if action=='NAVIGATE':
                        assert payload['test_only'] is True and payload['url']==ORIGIN+'/'
                        await actions.navigate(session,payload['url'])
                        await session.page().wait_for_function("() => document.getElementById('receipt').textContent.length > 0")
                        result={'ok':True,**await observe()}
                    elif action=='OBSERVE':result=await observe()
                    elif action in {'FILL','UPLOAD','ADVANCE'}:
                        from backend.app.integrations.aihawk_executor import AIHawkExecutor
                        from backend.app.integrations.browser_queue import BrowserQueue
                        from backend.app.integrations.database import Database
                        executor=AIHawkExecutor(session,BrowserQueue(root,Database(root/'data/job_agent.sqlite3')),observe)
                        result=await executor.execute(queued)
                        if action=='UPLOAD':
                            await session.page().wait_for_function("() => JSON.parse(document.getElementById('receipt').textContent).file_selected")
                        if action=='ADVANCE':
                            await session.page().wait_for_function("() => document.getElementById('application').dataset.step === 'review'")
                        result={'ok':True,**await observe()}
                    else:raise ValueError('Test controller refuses submit and unknown commands')
                    await cli('browser-reply',queued['command_id'],'--token='+queued['claim_token'],'--result-json',json.dumps(result))
                    executed.append({'phase':phase,'action':action,'acknowledged':True})
                except Exception:
                    await cli('browser-reply',queued['command_id'],'--token='+queued['claim_token'],'--result-json','{}','--error','AIHawk fixture action failed; do not retry')
                    raise
            out,err=await reader
            assert worker.returncode==0,err.decode(errors='replace')
            result=json.loads(out.decode()[out.decode().index('{'):])
            assert result['submitted'] is False
            assert result['status']==('READY_TO_APPLY' if phase==1 else 'WAITING_FOR_APPROVAL')
            assert result['unresolved_questions']==(['Preferred name'] if phase==1 else [])
            phases.append(result)
            if phase==1:
                assert await session.page().input_value(await selector('preferred'))==''
                write_json(root/'data/application_answers.json',[{'question':'Preferred name','normalised_question':'preferred name',
                    'answer':'Test','verified':True,'requires_manual_confirmation':False,'last_verified':now(),'source':'Synthetic test input only'}])
        queue=await cli('browser-status')
        assert all(x['state']=='ACKNOWLEDGED' for x in queue['commands'])
        assert not blocked
        if multi_page:
            assert sum(x['action']=='ADVANCE' for x in executed)==1
            assert all(x['action'] not in ('NAVIGATE','ADVANCE','UPLOAD') for x in executed if x['phase']==2)
        report={'result':'PASS','tested_at':now(),'engine':'Installed AIHawk actions with Edge session adapter',
            'scope':'Synthetic fixture through durable application workflow; not an employer integration',
            'multi_page':multi_page,'native_dropdown':native_dropdown,'phases':phases,'commands':executed,'submitted':False,'external_page_requests':0,'root':str(root)}
        write_json(root/'aihawk-queue-report.json',report);print(json.dumps(report,indent=2))
    finally:
        if worker and worker.returncode is None:worker.kill()
        if reader:await reader
        await session.close();server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workflow-python',required=True)
    parser.add_argument('--multi-page',action='store_true');parser.add_argument('--native-dropdown',action='store_true');args=parser.parse_args()
    asyncio.run(asyncio.wait_for(run(args.workflow_python,args.multi_page,args.native_dropdown),180))
