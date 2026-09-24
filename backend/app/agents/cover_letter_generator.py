from pathlib import Path
from ..models.candidate import verified
from ..utils.validators import safe_filename,digest,contains_skill
from ..utils.config import write_json
from .resume_tailor import render_pdf
def compose(profile,job):
    name=verified(profile,"full_name")
    if not name:raise ValueError("Verified candidate name required")
    projects=verified(profile,"projects") or []
    import json
    keywords=job.get('required_skills',[])+job.get('preferred_skills',[])
    ranked=sorted(projects,key=lambda p:sum(contains_skill(json.dumps(p),k) for k in keywords),reverse=True)
    first=next((p for p in ranked if p.get('name') and p.get('bullets')),None)
    paragraphs=["Dear Hiring Team,","I am applying for the "+job["title"]+" position at "+job["company"]+"."]
    if first:
        paragraphs.append("My project work includes "+first["name"]+". "+first["bullets"][0])
    responsibilities=job.get("responsibilities",[])
    if responsibilities:
        paragraphs.append("The opportunity to contribute to "+responsibilities[0].rstrip(".").lower()+" is particularly relevant to the work I want to pursue.")
    paragraphs.extend(["I would welcome the opportunity to discuss my project work and how I could contribute to your team.","Kind regards,",name])
    return paragraphs

def generate(profile,job,root):
    from ..integrations.browser import job_revision
    name=verified(profile,'full_name');paragraphs=compose(profile,job)
    fingerprint=digest({'profile_hash':digest(profile),'job_revision':job_revision(job),'paragraphs':paragraphs,'version':2})
    blocks=[{"kind":"normal","text":p,"field":None} for p in paragraphs]
    stem=safe_filename(name+"_"+job["company"]+"_"+job["title"])+"_"+fingerprint[:8]
    folder=Path(root)/"generated/cover_letters";folder.mkdir(parents=True,exist_ok=True)
    from docx import Document
    from docx.shared import Pt,RGBColor
    doc=Document();doc.styles["Normal"].font.name="Calibri";doc.styles["Normal"].font.size=Pt(11)
    for p in paragraphs:doc.add_paragraph(p)
    doc.save(folder/(stem+".docx"));render_pdf(blocks,folder/(stem+".pdf"))
    manifest={"docx_path":str(folder/(stem+".docx")),"pdf_path":str(folder/(stem+".pdf")),"text":"\n\n".join(paragraphs),
              "fingerprint":fingerprint,"visual_review":"PENDING","source_fields":["full_name","projects"],"job_id":job["job_id"],
              "company":job['company'],"job_title":job['title'],"profile_hash":digest(profile),"job_revision":job_revision(job),"generator_version":2}
    write_json(folder/(stem+".json"),manifest)
    return manifest
