"""Invalidate stale preparation explicitly, preserving documents and real attempts."""
import hashlib,json
from pathlib import Path
from ..models.application import PREPARATION
from ..utils.config import now
from ..utils.validators import digest

APPLICATION_JOB_FIELDS=(
    'job_id','company','title','canonical_url','location','remote_type','employment_type',
    'description','required_skills','preferred_skills','requirements','responsibilities',
    'preferred_requirements','requirements_reviewed','experience_required','education_required',
    'work_rights_requirement','citizenship_requirement','clearance_requirement','closing_at',
    'listing_state','cover_letter_required','salary_min','salary_max','currency',
)

def application_job_revision(job):
    return digest({key:job.get(key) for key in APPLICATION_JOB_FIELDS})

def invalidate(db,reason,application_ids=None,archive_documents=True):
    """Never delete an application, artifact file, history event or submission reservation.

    Scope/answer changes can retain content-validated documents but always require
    a new application packet and observed form review. Candidate/content changes
    also archive the old document records. In-flight attempts remain unretryable.
    """
    selected=set(application_ids) if application_ids is not None else None
    invalidated=[];reconciliation=[]
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        has_queue=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='browser_runs'").fetchone() is not None
        for row in connection.execute('SELECT application_id,data FROM applications').fetchall():
            app=json.loads(row['data']);aid=app['application_id']
            if selected is not None and aid not in selected:continue
            if app['status'] not in PREPARATION:continue
            # Revoke authority even if a reserved click is already in flight.
            connection.execute('DELETE FROM approvals WHERE application_id=?',(aid,))
            if has_queue:
                connection.execute("UPDATE browser_commands SET state=CASE WHEN state='CLAIMED' THEN 'UNCERTAIN' ELSE 'CANCELLED' END,error=? WHERE state IN ('QUEUED','CLAIMED') AND run_id IN (SELECT run_id FROM browser_runs WHERE application_id=? AND state='ACTIVE')",(reason,aid))
                connection.execute("UPDATE browser_runs SET state='FAILED',updated_at=?,error=? WHERE application_id=? AND state='ACTIVE'",(now(),reason,aid))
            attempt=connection.execute('SELECT 1 FROM submission_attempts WHERE job_id=?',(app['job_id'],)).fetchone()
            if attempt:
                # Preserve the exact attempted packet for receipt reconciliation.
                app.update(next_action='Preparation changed during an attempted submission; verify the employer receipt before any retry',preparation_change=reason,last_updated=now())
                connection.execute('UPDATE applications SET data=?,updated_at=? WHERE application_id=?',(json.dumps(app),now(),aid))
                reconciliation.append(aid)
                continue
            old=app['status'];status='FOUND' if old=='FOUND' else 'ANALYSED'
            app.update(status=status,score=None,eligibility=None,packet=None,next_action=reason,
                       analysis_stale=True,preparation_change=reason,last_updated=now())
            if archive_documents:
                app.update(resume_version=None,cover_letter_version=None,validation=None,cover_validation=None,cover_validation_details=None)
                for artifact in connection.execute('SELECT artifact_id,data FROM artifacts WHERE application_id=?',(aid,)).fetchall():
                    data=json.loads(artifact['data'])
                    if data.get('archived'):continue
                    data.update(archived=True,archive_reason=reason,archived_at=now())
                    connection.execute('UPDATE artifacts SET data=? WHERE artifact_id=?',(json.dumps(data),artifact['artifact_id']))
            connection.execute('UPDATE applications SET status=?,data=?,updated_at=? WHERE application_id=?',(status,json.dumps(app),now(),aid))
            connection.execute('INSERT INTO status_history(application_id,old_status,new_status,time,reason) VALUES(?,?,?,?,?)',(aid,old,status,now(),reason))
            invalidated.append(aid)
    for aid in invalidated:
        db.log('preparation','Stale preparation invalidated','NEEDS_REVIEW',error=reason,application_id=aid)
    for aid in reconciliation:
        db.log('preparation','Changed preparation with existing submission attempt','NEEDS_REVIEW',error=reason,application_id=aid)
    return {'invalidated_applications':invalidated,'receipt_reconciliation_required':reconciliation}

def invalidate_answer_users(db,normalised_question,reason):
    from ..utils.validators import normal
    ids=[app['application_id'] for app in db.rows('applications')
         if any(normal(question.get('question',''))==normalised_question for question in (app.get('packet') or {}).get('questions',[]))]
    return invalidate(db,reason,ids,archive_documents=False)

def reconcile(db,root,profile,job,app,eligibility):
    """Catch direct JSON/file edits and time-dependent eligibility on the next run."""
    from ..integrations.browser import job_revision
    packet=app.get('packet') or {};reason=None;archive=False
    if packet:
        if packet.get('profile_hash')!=digest(profile):
            reason='Candidate facts changed; regenerate documents and review the application';archive=True
        elif packet.get('job_revision')!=job_revision(job):
            reason='Job content changed; regenerate documents and review the application';archive=True
        elif packet.get('destination')!=job['canonical_url']:
            reason='Employer application destination changed; inspect the new application page'
        else:
            directory=(Path(root)/'generated').resolve()
            for kind,file in packet.get('documents',{}).items():
                if not file:continue
                path=Path(file).resolve()
                if not path.is_relative_to(directory) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=packet.get('document_hashes',{}).get(kind):
                    reason='An application document is missing or changed; regenerate and validate it';archive=True;break
        if reason is None and packet.get('form_reviewed'):
            from ..utils.config import read_json
            from ..utils.answer_memory import revisions,review_hash
            memory=revisions(read_json(Path(root)/'data/application_answers.json',[]))
            if packet.get('answer_memory_hash')!=review_hash(memory,packet.get('questions',[])):
                reason='Answers used by this form changed or were not revision-bound; review the application again'
    if reason is None and app['status'] in {'READY_TO_APPLY','WAITING_FOR_APPROVAL'}:
        if not packet:reason='The prepared application packet is missing; prepare and review it again'
        elif eligibility['status']!='ELIGIBLE':reason='Eligibility is no longer confirmed; resolve the current requirements before applying'
        elif (app.get('validation') or {}).get('result')!='PASS':reason='Resume validation is no longer valid; validate and review the documents again';archive=True
        else:
            from ..utils.config import settings
            score=job.get('analysis',{}).get('scoring',{}).get('overall_score')
            if score is None or score<settings(root)['application_threshold']:
                reason='The current match score is below the application threshold; recheck the shortlist'
    if reason:
        invalidate(db,reason,[app['application_id']],archive_documents=archive)
        return db.application(app['application_id'])
    return app
