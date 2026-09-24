"""Validate cover letters against the exact deterministic verified-fact composition."""
import hashlib
from pathlib import Path
from ..utils.validators import digest
from ..integrations.browser import job_revision
from .cover_letter_generator import compose
from .resume_validator import clean

def validate_cover(manifest,profile,job):
    from docx import Document
    from pypdf import PdfReader
    errors=[];pdf=Path(manifest['pdf_path']);docx=Path(manifest['docx_path']);pages=None
    if manifest.get('profile_hash')!=digest(profile):errors.append('Profile changed after cover letter creation')
    if manifest.get('job_id')!=job['job_id'] or manifest.get('job_revision')!=job_revision(job):errors.append('Cover letter target or job requirements changed')
    try:
        expected=clean(' '.join(compose(profile,job)))
        if clean(manifest.get('text',''))!=expected:errors.append('Cover letter contains unsupported content')
        reader=PdfReader(pdf);pages=len(reader.pages)
        if clean(' '.join(p.extract_text() or '' for p in reader.pages))!=expected:errors.append('Cover letter PDF content changed or is unreadable')
        if clean(' '.join(p.text for p in Document(docx).paragraphs))!=expected:errors.append('Cover letter DOCX content changed or is unreadable')
    except Exception as exc:errors.append('Cover letter readability failure: '+type(exc).__name__)
    facts_pass=not errors
    if manifest.get('visual_review')!='PASS':errors.append('Visual layout review pending for DOCX and PDF')
    if not profile.get('identity_confirmed') or profile.get('intake_deferred'):errors.append('Candidate identity needs confirmation')
    return {'result':'FAIL' if errors else 'PASS','facts_pass':facts_pass,'errors':errors,'page_count':pages,
            'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.is_file() else None,
            'docx_sha256':hashlib.sha256(docx.read_bytes()).hexdigest() if docx.is_file() else None}
