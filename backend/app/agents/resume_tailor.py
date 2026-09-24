from pathlib import Path
import json
from ..models.candidate import verified
from ..utils.validators import digest,safe_filename,contains_skill
from ..utils.config import write_json

def tailor(profile,job,root):
    if not verified(profile,"full_name") or not verified(profile,"email") or not verified(profile,"education"):
        raise ValueError("Verified name, email and education are required to generate a resume")
    keywords=job.get("required_skills",[])+job.get("preferred_skills",[])
    def rank(item): return sum(contains_skill(json.dumps(item),k) for k in keywords)
    skills=sorted(verified(profile,"technical_skills") or [],key=rank,reverse=True)[:35]
    projects=sorted(verified(profile,"projects") or [],key=rank,reverse=True)
    experience=verified(profile,"employment_experience") or []
    blocks=[]
    claims=[]
    def add(kind,text,field):
        if not text: return
        blocks.append({"kind":kind,"text":str(text),"field":field})
        claims.append({"text":str(text),"field":field})
    add("title",verified(profile,"full_name"),"full_name")
    contact=[(f,verified(profile,f)) for f in ("location","phone","email","linkedin","github","portfolio") if verified(profile,f)]
    for f,v in contact: add("contact",v,f)
    blocks.append({"kind":"target","text":"Application for "+job["title"]+" at "+job["company"],"field":None})
    blocks.append({"kind":"heading","text":"Education","field":None})
    for e in verified(profile,"education") or []:
        add("subheading",e.get("qualification"),"education")
        add("normal"," | ".join(str(e[k]) for k in ("institution","location","dates") if e.get(k)),"education")
        for b in e.get("bullets",[])[:1]: add("bullet",b,"education")
    blocks.append({"kind":"heading","text":"Technical Skills","field":None})
    # Skills are exact source phrases: qualifiers such as fundamentals remain intact.
    for start in range(0,len(skills),10):
        group=skills[start:start+10]
        blocks.append({"kind":"normal","text":" | ".join(group),"field":"technical_skills"})
        claims.extend({"text":s,"field":"technical_skills"} for s in group)
    blocks.append({"kind":"heading","text":"Selected Projects","field":None})
    for project in projects[:4]:
        add("subheading",project.get("name"),"projects")
        add("normal"," | ".join(str(project[k]) for k in ("context","technologies","dates") if project.get(k)),"projects")
        for b in project.get("bullets",[])[:2]: add("bullet",b,"projects")
    blocks.append({"kind":"heading","text":"Employment Experience","field":None})
    for e in experience[:3]:
        add("subheading",e.get("role"),"employment_experience")
        add("normal"," | ".join(str(e[k]) for k in ("company","location","dates") if e.get(k)),"employment_experience")
        for b in e.get("bullets",[])[:1]: add("bullet",b,"employment_experience")
    if verified(profile,"certifications"):
        blocks.append({"kind":"heading","text":"Certifications","field":None})
        for c in verified(profile,"certifications"): add("normal",c,"certifications")
    from ..integrations.browser import job_revision as current_job_revision
    job_revision=current_job_revision(job)
    fingerprint=digest({"profile":profile,"job_revision":job_revision,"version":2})
    stem=safe_filename(profile["full_name"]+"_"+job["company"]+"_"+job["title"])+"_"+fingerprint[:8]
    out=Path(root)/"generated/resumes"; out.mkdir(parents=True,exist_ok=True)
    docx_path=out/(stem+".docx"); pdf_path=out/(stem+".pdf")
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    doc=Document()
    sec=doc.sections[0]
    sec.page_width=Inches(8.27); sec.page_height=Inches(11.69)
    sec.top_margin=sec.bottom_margin=Inches(.62); sec.left_margin=sec.right_margin=Inches(.7)
    for name in ("Normal","Title","Heading 1","Heading 2"):
        style=doc.styles[name]; style.font.name="Calibri"; style.font.color.rgb=RGBColor(0,0,0)
    doc.styles["Normal"].font.size=Pt(10)
    doc.styles["Normal"].paragraph_format.space_after=Pt(3)
    doc.styles["Title"].font.size=Pt(21)
    doc.styles["Heading 1"].font.size=Pt(12)
    doc.styles["Heading 1"].paragraph_format.space_before=Pt(9)
    doc.styles["Heading 2"].font.size=Pt(10.5)
    for b in blocks:
        kind=b["kind"]; style={"title":"Title","heading":"Heading 1","subheading":"Heading 2","bullet":"List Bullet"}.get(kind,"Normal")
        p=doc.add_paragraph(b["text"],style)
        if kind=="contact":
            p.paragraph_format.space_after=Pt(0)
            for r in p.runs:r.font.size=Pt(9)
        if kind=="target":
            p.paragraph_format.space_before=Pt(6)
            for r in p.runs:r.font.italic=True
    doc.core_properties.author=profile["full_name"]; doc.core_properties.title=job["title"]+" application"
    doc.save(docx_path)
    render_pdf(blocks,pdf_path)
    manifest={"fingerprint":fingerprint,"docx_path":str(docx_path),"pdf_path":str(pdf_path),"job_id":job["job_id"],
              "company":job["company"],"job_title":job["title"],"claims":claims,"blocks":blocks,"visual_review":"PENDING",
              "profile_hash":digest(profile),"job_revision":job_revision,"generator_version":2,"pdf_render_method":"reportlab","tailoring":"Verified source phrases reordered for role relevance"}
    write_json(out/(stem+".json"),manifest)
    return manifest

def render_pdf(blocks,path):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.enums import TA_LEFT
    from xml.sax.saxutils import escape
    styles=getSampleStyleSheet()
    sizes={"title":(20,24),"heading":(12,15),"subheading":(10.5,13),"normal":(10,13),"bullet":(10,13),"contact":(9,11),"target":(10,13)}
    for kind,(size,leading) in sizes.items():
        styles.add(ParagraphStyle("resume_"+kind,fontName="Helvetica-Bold" if kind in {"title","heading","subheading"} else "Helvetica",
            fontSize=size,leading=leading,spaceAfter=3 if kind!="contact" else 0,spaceBefore=8 if kind=="heading" else 0,
            keepWithNext=kind in {"title","heading","subheading"},leftIndent=10 if kind=="bullet" else 0))
    story=[]
    for b in blocks:
        text=escape(b["text"]).replace("\n","<br/>")
        if b["kind"]=="bullet":text="- "+text
        story.append(Paragraph(text,styles["resume_"+b["kind"]]))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=42,bottomMargin=42).build(story)
