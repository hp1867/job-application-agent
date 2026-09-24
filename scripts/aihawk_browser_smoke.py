"""Real AIHawk actions on an isolated loopback fixture; never an employer."""
import asyncio,hashlib,json,os,shutil,sys,tempfile,threading
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['INVISIBLE_PLAYWRIGHT_CACHE_DIR']=str(ROOT/'.venv/aihawk/engine-cache')
from aihawk.mcp import actions
from aihawk.mcp.session import StealthSession
from backend.app.integrations.aihawk_upload import upload_document

async def run(backend='firefox'):
    root=Path(tempfile.mkdtemp(prefix='aihawk-browser-',dir=ROOT/'tmp'))
    documents=root/'generated';documents.mkdir()
    document=documents/'synthetic-browser-resume.txt'
    fixture=ROOT/'tests/fixtures/browser_form'
    shutil.copyfile(fixture/'resume.txt',document)
    files={'/':('text/html', (fixture/'index.html').read_bytes()),'/app.js':('text/javascript',(fixture/'app.js').read_bytes())}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or self.path not in files:
                self.send_error(403);return
            mime,body=files[self.path];self.send_response(200)
            self.send_header('Content-Type',mime+'; charset=utf-8')
            self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'none'; form-action 'none'; frame-src 'none'")
            self.end_headers();self.wfile.write(body)
        def do_POST(self):self.send_error(403)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    if backend=='edge':
        from backend.app.integrations.aihawk_session import AIHawkEdgeSession
        session=AIHawkEdgeSession(headless=True)
    else:
        session=StealthSession(headless=True,locale='en-AU',timezone='Australia/Sydney',prep_recaptcha=False)
    blocked=[];done=[]
    try:
        await session.start()
        async def route(request_route):
            request=request_route.request
            if not request.url.startswith(origin+'/') or request.method!='GET':
                blocked.append(request.url);await request_route.abort();return
            await request_route.continue_()
        await session._context.route('**/*',route)
        await actions.navigate(session,origin+'/');done.append('AIHawk.navigate')
        policy=await actions.read_text(session,'#policy')
        assert 'Automated filling and file selection are permitted here' in policy
        observation={'website_permits_automation':True,'website_policy_evidence':policy,'observed_url':origin+'/'}
        for identity,value in [('name','Test Candidate'),('email','candidate@example.test'),('preferred','Test')]:
            snapshot=json.loads(await actions.snapshot(session))
            control=next(item for item in snapshot['interactive_elements'] if item.get('id')==identity)
            await actions.type_text(session,control['selector'],value);done.append('AIHawk.type_text')
        snapshot=json.loads(await actions.snapshot(session))
        control=next(item for item in snapshot['interactive_elements'] if item.get('id')=='resume')
        packet={'documents':{'resume':str(document)},'document_hashes':{'resume':hashlib.sha256(document.read_bytes()).hexdigest()}}
        await upload_document(session,control['selector'],packet,'resume',root,observation);done.append('AIHawk session upload extension')
        await session.page().wait_for_function("() => document.getElementById('review').textContent.startsWith('READY FOR REVIEW')",timeout=10000)
        review=await actions.read_text(session,'#review')
        assert 'READY FOR REVIEW' in review
        assert await session.page().is_disabled('button[type=submit]')
        assert not blocked,blocked
        report={'result':'PASS','backend':backend,'tested_at':datetime.now(timezone.utc).isoformat(),'scope':'Installed AIHawk actions and session management on synthetic loopback form only',
                'actions':done,'review':review,'submitted':False,'external_page_requests':len(blocked),'captcha_preparation_enabled':False,'root':str(root)}
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        await session.close()
        server.shutdown();server.server_close();worker.join(timeout=3)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--backend',choices=['firefox','edge'],default='firefox')
    asyncio.run(asyncio.wait_for(run(parser.parse_args().backend),120))
