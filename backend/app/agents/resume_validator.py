import json,re,hashlib
from pathlib import Path
from ..models.candidate import verified
from ..utils.validators import digest,contains_skill

def flat_strings(value):
    if isinstance(value,str):return [value]
    if isinstance(value,list):return [s for v in value for s in flat_strings(v)]
    if isinstance(value,dict):return [s for v in value.values() for s in flat_strings(v)]
    return [str(value)] if value is not None else []
def clean(text):return " ".join(text.replace("\ufffd","").split())
def validate(manifest,profile,job):
    from pypdf import PdfReader
    from docx import Document
    errors=[]
    if manifest.get("profile_hash")!=digest(profile): errors.append("Profile changed after resume creation")
    if manifest.get("job_id")!=job["job_id"] or manifest.get("company")!=job["company"] or manifest.get("job_title")!=job["title"]:
        errors.append("Wrong application target")
    for claim in manifest["claims"]:
        source=verified(profile,claim["field"])
        # Composite metadata lines contain only joined exact source values.
        parts=claim["text"].split(" | ")
        allowed=flat_strings(source)
        if any(part not in allowed for part in parts): errors.append("Unsupported claim in "+claim["field"]+": "+claim["text"][:70])
    pdf=Path(manifest["pdf_path"]); docx=Path(manifest["docx_path"])
    try:
        pdf_reader=PdfReader(pdf)
        pdftext=clean(" ".join(p.extract_text() or "" for p in pdf_reader.pages))
        doctext=clean(" ".join(p.text for p in Document(docx).paragraphs))
        expected_doc=clean(" ".join(b["text"] for b in manifest["blocks"]))
        if doctext != expected_doc: errors.append("DOCX contains unexpected or changed content")
        expected_pdf=clean(" ".join(("- " if b["kind"]=="bullet" else "")+b["text"] for b in manifest["blocks"]))
        if pdftext != expected_pdf: errors.append("PDF contains unexpected or changed content")
        for b in manifest["blocks"]:
            if clean(b["text"]) not in pdftext: errors.append("PDF omitted or corrupted text: "+b["text"][:50])
            if clean(b["text"]) not in doctext: errors.append("DOCX omitted or corrupted text: "+b["text"][:50])
        if len(pdftext)<100:errors.append("PDF is not readable")
        if "\ufffd" in pdftext or "\u25a0" in pdftext:errors.append("PDF contains replacement glyphs")
    except Exception as exc:
        errors.append("Artifact readability failure: "+type(exc).__name__); pdftext=""; pdf_reader=None
    required=job.get("required_skills",[]); optional=job.get("preferred_skills",[])
    keywords=required+optional
    coverage=sum(contains_skill(pdftext,k) for k in keywords)/len(keywords) if keywords else None
    facts_pass=not errors
    from .ats_relevance import report
    relevance_report=report(manifest,job,pdftext,facts_pass=facts_pass)
    if manifest.get("visual_review")!="PASS": errors.append("Visual layout review pending for DOCX and PDF")
    if not profile.get("identity_confirmed"): errors.append("Candidate identity needs confirmation")
    return {"result":"FAIL" if errors else "PASS","facts_pass":facts_pass,"errors":errors,
            "ats_relevance_report":relevance_report,
            "ats_relevance_score":round(coverage*100) if coverage is not None else None,
            "ats_note":"Transparent keyword coverage, not a third-party ATS score",
            "keyword_coverage":{k:contains_skill(pdftext,k) for k in keywords},"page_count":len(pdf_reader.pages) if pdf_reader else None,
            "pdf_sha256":hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.exists() else None,
            "docx_sha256":hashlib.sha256(docx.read_bytes()).hexdigest() if docx.exists() else None}
