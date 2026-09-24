from pathlib import Path
from ..models.candidate import verified
from ..utils.validators import safe_filename
def prepare_interview(profile,job,root):
    lines=["# "+job["company"]+" interview preparation","",job["title"],"",
           "## Company and role","",job.get("description",""),"","Source: "+job["canonical_url"],"",
           "## Resume walkthrough","","Introduce your degree, explain one relevant project, then connect your customer-facing work to collaboration.","",
           "## Technical practice","","Explain an implementation decision in your most relevant project. Discuss testing, errors and trade-offs.",""]
    for s in job.get("required_skills",[])+job.get("preferred_skills",[]):
        lines.append("- Explain where you used "+s+", or say clearly if it is a skill you are learning.")
    lines+=["","## Behavioural practice","","Describe a difficult problem, a time you worked with others, and how you handled feedback.","",
            "## Verified STAR material",""]
    for p in (verified(profile,"projects") or [])[:3]:
        lines+=["### "+p["name"],"","Situation: "+p.get("context","Project work") if p.get("context") else "Situation: Project work",
                "","Actions from your resume:"]+["- "+b for b in p.get("bullets",[])]+["","Result: Supply the actual outcome and measurements; do not invent metrics.",""]
    lines+=["## Questions to ask","","- What would success look like in the first three months?","- How do junior engineers receive code review and mentoring?","- Which technical problem would this role help solve first?"]
    folder=Path(root)/"generated/interview_prep";folder.mkdir(parents=True,exist_ok=True)
    path=folder/(safe_filename(job["company"]+"_"+job["title"])+".md")
    path.write_text("\n".join(lines),encoding="utf-8")
    return str(path)

