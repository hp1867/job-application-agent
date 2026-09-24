from pathlib import Path
import hashlib, shutil, re
from ..utils.config import write_json,now
from ..models.candidate import empty_profile
from .resume_parser import parse_resume_text

def extract_resume(source,root):
    source=Path(source).resolve()
    if source.suffix.lower() not in {".pdf",".docx",".txt"}: raise ValueError("Supported formats: PDF, DOCX, TXT")
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    dest=Path(root)/"master_resume"/(sha[:12]+"_"+source.name)
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:
        raise ValueError('Preserved original hash mismatch; refusing to overwrite it')
    if not dest.exists(): shutil.copy2(source,dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:
        raise ValueError('Source changed during import; preserved snapshot requires review')
    from .document_extraction import extract_docx,extract_pdf
    if source.suffix.lower()=='.pdf':extraction=extract_pdf(dest)
    elif source.suffix.lower()=='.docx':extraction=extract_docx(dest)
    else:extraction={'text':dest.read_text(encoding='utf-8'),'segments':[],'warnings':[], 'reading_order':'Plain text line order','visual_review':'PENDING'}
    text=extraction['text']
    if len(text.strip())<80: raise ValueError("Resume is not text-readable; OCR or user review required")
    structured=parse_resume_text(text)
    structured_path=Path(root)/'data/resume_imports'/(sha+'.structured.json')
    write_json(structured_path,structured)
    manifest={"original_path":str(source),"preserved_path":str(dest),"sha256":sha,"imported_at":now(),"text":text,'structured_path':str(structured_path),
              'extraction':{k:v for k,v in extraction.items() if k!='text'},'review_required':True}
    write_json(Path(root)/'data/resume_imports'/(sha+'.json'),manifest)
    write_json(Path(root)/"data/resume_import.json",manifest)
    proposal=empty_profile()
    proposal['extraction_proposals']=structured['proposals']
    proposal['structured_resume_path']=str(structured_path)
    proposal['review_required']=True
    proposal["master_resume"]={k:v for k,v in manifest.items() if k!="text"}
    write_json(Path(root)/"data/candidate_import_proposal.json",proposal)
    return {k:v for k,v in manifest.items() if k!="text"}
