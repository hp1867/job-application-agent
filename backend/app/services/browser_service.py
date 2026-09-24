"""Run the existing application workflow using the durable native-browser bridge."""
from pathlib import Path
from ..integrations.browser_queue import BrowserQueue,QueuedBrowserDriver
from ..integrations.application_workflow import ApplicationWorkflow
from ..utils.config import read_json,settings
from ..integrations.browser import packet_hash

def run_browser(root,db,aid,phase='fill',timeout=300):
    root=Path(root)
    queue=BrowserQueue(root,db);run_id=None
    try:
        run_id=queue.start(aid,phase)
        print('Browser workflow '+run_id+' is waiting for the connected browser bridge.',flush=True)
        profile=read_json(root/'data/candidate_profile.json',{});app=db.application(aid);job=db.job(app['job_id'])
        workflow=ApplicationWorkflow(db,QueuedBrowserDriver(queue,run_id,timeout))
        if phase=='fill':result=workflow.fill(profile,job,app,read_json(root/'data/application_answers.json',[]))
        else:result=workflow.submit(settings(root),profile,job,app)
        queue.finish(run_id);return {'run_id':run_id,**result}
    except Exception as exc:
        if run_id:queue.finish(run_id,type(exc).__name__+': '+str(exc)[:250])
        current=db.application(aid)
        bound=queue.run(run_id) if run_id else None
        if current and (not bound or current.get('packet') and packet_hash(current['packet'])==bound['packet_hash']):
            with db.connect() as connection:
                attempted=connection.execute('SELECT 1 FROM submission_attempts WHERE application_id=?',(aid,)).fetchone()
            action='Submission outcome requires receipt reconciliation; no retry permitted' if attempted else 'Browser workflow needs attention: '+str(exc)[:250]
            db.update_application(aid,{'next_action':action})
        db.log('browser_bridge','Browser workflow stopped','NEEDS_ACTION',error=type(exc).__name__,application_id=aid)
        raise
