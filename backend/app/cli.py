import argparse,json
from pathlib import Path
from .utils.config import ROOT,read_json,write_json
from .orchestrator import Orchestrator
def main():
    parser=argparse.ArgumentParser(description="Persistent verified-facts job application agent")
    parser.add_argument("--root",type=Path,default=ROOT)
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init");sub.add_parser("report")
    sub.add_parser("defer-candidate")
    sub.add_parser("mail-only");sub.add_parser("export-schemas")
    review=sub.add_parser('review-artifact');review.add_argument('artifact_id');review.add_argument('evidence',type=Path)
    browser=sub.add_parser('browser-run',help='Run a gated workflow using the connected browser command bridge')
    browser.add_argument('application_id');browser.add_argument('--phase',choices=['fill','submit'],default='fill');browser.add_argument('--timeout',type=int,default=300)
    next_action=sub.add_parser('browser-next',help='Claim one browser action once; no automatic UI retry')
    next_action.add_argument('--run-id')
    reply=sub.add_parser('browser-reply',help='Acknowledge one observed browser action using its claim token')
    reply.add_argument('command_id');reply.add_argument('--token',required=True);reply.add_argument('--result-json',required=True);reply.add_argument('--error')
    sub.add_parser('browser-status')
    daily=sub.add_parser("daily-report");daily.add_argument("--date")
    run=sub.add_parser("run");run.add_argument("--offline",action="store_true");run.add_argument("--no-documents",action="store_true")
    serve=sub.add_parser("serve");serve.add_argument("--port",type=int)
    imp=sub.add_parser("import-resume");imp.add_argument("path")
    for name in ("ingest-jobs","ingest-emails"):
        p=sub.add_parser(name);p.add_argument("path",type=Path)
    args=parser.parse_args()
    engine=Orchestrator(args.root)
    if args.command=="init":result={"root":str(args.root),"database":engine.config["database"],"dry_run":engine.config["dry_run"]}
    elif args.command=="run":result=engine.run(live=not args.offline,generate_documents=not args.no_documents)
    elif args.command=="report":result=read_json(args.root/"generated/reports/latest.json",{})
    elif args.command=="defer-candidate":
        from .services.candidate_intake import defer_candidate
        result=defer_candidate(args.root,engine.db)
    elif args.command=="mail-only":result=engine.mail_only()
    elif args.command=='review-artifact':
        from .services.artifact_review import record_review
        result=record_review(args.root,engine.db,args.artifact_id,read_json(args.evidence))
    elif args.command=='browser-run':
        from .services.browser_service import run_browser
        result=run_browser(args.root,engine.db,args.application_id,args.phase,args.timeout)
    elif args.command in {'browser-next','browser-reply','browser-status'}:
        from .integrations.browser_queue import BrowserQueue
        queue=BrowserQueue(args.root,engine.db)
        if args.command=='browser-next':result=queue.claim(args.run_id)
        elif args.command=='browser-reply':result=queue.reply(args.command_id,args.token,json.loads(args.result_json),args.error)
        else:result=queue.status()
    elif args.command=="daily-report":
        from .services.report_service import daily_report
        result=daily_report(args.root,engine.db,args.date)
    elif args.command=="export-schemas":
        from .models.contracts import export_schemas
        result=export_schemas(args.root)
    elif args.command=="serve":
        from .main import serve
        return serve(args.root,args.port)
    elif args.command=="import-resume":
        from .services.resume_service import extract_resume
        result=extract_resume(args.path,args.root)
    else:
        from .utils.validators import digest
        data=read_json(args.path)
        if data is None:raise ValueError("Input file not found")
        folder="jobs" if args.command=="ingest-jobs" else "gmail"
        target=args.root/"data/inbox"/folder/(digest(data)[:16]+".json")
        write_json(target,data);result={"ingested":str(target)}
    print(json.dumps(result,indent=2,ensure_ascii=True))
if __name__=="__main__":main()
