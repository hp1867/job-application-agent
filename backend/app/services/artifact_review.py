"""Record an actual rendered-page review. Never infer visual approval from generation."""
import hashlib
from datetime import datetime,timezone,timedelta
from pathlib import Path
from ..utils.config import read_json,write_json,now
from ..agents.resume_validator import validate
from ..agents.cover_letter_validator import validate_cover
from ..models.application import PREPARATION
from .application_service import prepare

def record_review(root,db,artifact_id,evidence):
    artifact=next((a for a in db.rows('artifacts') if a['artifact_id']==artifact_id),None)
    if not artifact or artifact.get('archived'):raise ValueError('Active artifact required')
    app=db.application(artifact['application_id']);job=db.job(app['job_id'])
    if app['status'] not in PREPARATION:raise ValueError('Cannot modify documents for a submitted or closed application')
    profile=read_json(Path(root)/'data/candidate_profile.json',{})
    if not profile.get('identity_confirmed') or profile.get('intake_deferred'):raise ValueError('Candidate intake must be confirmed first')
    if evidence.get('result')!='PASS' or not evidence.get('reviewed_by') or not evidence.get('review_notes'):
        raise ValueError('Explicit reviewer, notes and PASS result are required after inspecting every page')
    try:
        age=datetime.now(timezone.utc)-datetime.fromisoformat(evidence['reviewed_at'])
        if age<timedelta(minutes=-5) or age>timedelta(hours=2):raise ValueError('Review is stale')
    except (KeyError,TypeError,ValueError):raise ValueError('A recent timezone-aware review timestamp is required')
    validator=validate if artifact['kind']=='resume' else validate_cover
    initial=validator(artifact,profile,job)
    if not initial['facts_pass']:raise ValueError('Correct document content before recording visual approval')
    pages=evidence.get('page_images',{});snapshots={}
    for fmt in ('docx','pdf'):
        file=Path(artifact[fmt+'_path'])
        if evidence.get(fmt+'_sha256')!=hashlib.sha256(file.read_bytes()).hexdigest():raise ValueError('Document changed since rendering')
        images=pages.get(fmt,[])
        if not isinstance(images,list) or not images or len(set(images))!=len(images):raise ValueError('Every rendered page must be listed once')
        expected=initial['page_count'] if fmt=='pdf' else evidence.get('docx_page_count')
        if type(expected) is not int or expected<1 or len(images)!=expected:raise ValueError('Rendered page count does not match document')
        snapshots[fmt]=[]
        for image in images:
            path=Path(image).resolve()
            if not path.is_relative_to((Path(root)/'generated').resolve()) or path.suffix.lower()!='.png' or not path.is_file():
                raise ValueError('Rendered PNG pages must be in this project generated directory')
            content=path.read_bytes()
            if not content.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid rendered PNG page')
            snapshots[fmt].append({'path':str(path),'sha256':hashlib.sha256(content).hexdigest()})
    artifact={**artifact,'visual_review':'PASS','visual_evidence':{**evidence,'page_images':snapshots,'recorded_at':now()}}
    result=validator(artifact,profile,job)
    if result['result']!='PASS':raise ValueError('; '.join(result['errors']))
    artifact=db.artifact(app['application_id'],artifact['kind'],artifact['fingerprint'],artifact)
    write_json(Path(artifact['pdf_path']).with_suffix('.json'),artifact)
    changes={'validation':result,'resume_version':artifact_id} if artifact['kind']=='resume' else {'cover_validation':result['result'],'cover_validation_details':result,'cover_letter_version':artifact_id}
    app=db.update_application(app['application_id'],changes)
    if (app.get('validation') or {}).get('result')=='PASS' and app['status']=='SHORTLISTED':
        app=db.update_application(app['application_id'],{},'RESUME_READY','Verified content and rendered-page review passed')
    cover_ok=not job.get('cover_letter_required') or app.get('cover_validation')=='PASS'
    if app['status']=='RESUME_READY' and cover_ok and job.get('analysis',{}).get('eligibility',{}).get('status')=='ELIGIBLE':
        app=db.update_application(app['application_id'],{},'READY_TO_APPLY','All required documents and eligibility confirmed')
    arts={a['artifact_id']:a for a in db.rows('artifacts')}
    if app.get('resume_version'):
        if app['status']=='WAITING_FOR_APPROVAL':app=db.update_application(app['application_id'],{},'READY_TO_APPLY','Documents reviewed; inspect the current form again')
        prepare(db,profile,job,app,arts[app['resume_version']],arts.get(app.get('cover_letter_version')))
    db.log('artifact_review','Rendered document reviewed','PASS',application_id=app['application_id'])
    return {'artifact_id':artifact_id,'validation':result,'submitted':False}
