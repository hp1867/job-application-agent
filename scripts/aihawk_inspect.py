"""Read-only first inspection of a public application page using real AIHawk.

Fresh session, no credentials, no filling/clicks/uploads, and no non-GET requests.
Inspection is not website permission or application readiness.
"""
import argparse,asyncio,json,sys,uuid
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.integrations.aihawk_session import AIHawkEdgeSession
from backend.app.utils.config import write_json,now
from aihawk.mcp import actions
from backend.app.integrations.greenhouse_observer import map_snapshot

async def inspect(url,visible=False):
    parsed=urlsplit(url)
    # Initial supported read-only discovery surface; other hosts need review.
    if parsed.scheme!='https' or parsed.hostname!='job-boards.greenhouse.io' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Inspector currently supports public HTTPS Greenhouse job-board pages only')
    if '/jobs/' not in parsed.path:raise ValueError('An exact public job listing URL is required')
    session=AIHawkEdgeSession(headless=not visible);blocked=[]
    allowed_hosts={parsed.hostname,'job-boards.cdn.greenhouse.io','s9-recruiting.cdn.greenhouse.io'}
    try:
        await session.start()
        async def guard(route):
            target=urlsplit(route.request.url)
            if route.request.method not in {'GET','HEAD'} or target.scheme!='https' or target.hostname not in allowed_hosts:
                blocked.append({'host':target.hostname,'method':route.request.method});await route.abort();return
            await route.continue_()
        await session._context.route('**/*',guard)
        await actions.navigate(session,url)
        snapshot=json.loads(await actions.snapshot(session,max_chars=40000))
        report={'inspected_at':now(),'requested_url':url,'snapshot':snapshot,'mapping_proposal':map_snapshot(snapshot),'blocked_requests':blocked,
            'website_permission':'UNKNOWN','application_readiness':'NEEDS_REVIEW','submitted':False,
            'scope':'Read-only AIHawk public listing inspection; restricted resource loading may omit controls'}
        path=ROOT/'data/browser_inspections'/(str(uuid.uuid4())+'.json');write_json(path,report)
        print(json.dumps({'report':str(path),'title':snapshot.get('title'),'observed_url':snapshot.get('url'),
            'visible_control_count':len(snapshot.get('interactive_elements',[])),'blocked_requests':len(blocked),
            'website_permission':'UNKNOWN','submitted':False},indent=2),flush=True)
        if visible:
            print('Read-only inspection complete. Close this demo Edge window when finished viewing.',flush=True)
            while session._browser.is_connected():
                await asyncio.sleep(1)
    finally:await session.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('url');parser.add_argument('--visible',action='store_true');args=parser.parse_args()
    asyncio.run(inspect(args.url,True) if args.visible else asyncio.wait_for(inspect(args.url),60))
