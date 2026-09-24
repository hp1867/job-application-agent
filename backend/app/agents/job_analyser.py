from .eligibility_checker import evaluate
from .job_scorer import score
from ..utils.role_scope import assess
def analyse(job,profile,prefs):
    eligibility=evaluate(job,profile,prefs)
    scoring=score(job,profile,eligibility,prefs)
    return {"company":job["company"],"role":job["title"],"location":job["location"],"salary":[job.get("salary_min"),job.get("salary_max")],
            "closing_date":job.get("closing_at"),"responsibilities":job.get("responsibilities",[]),"required_requirements":job.get("requirements",[]),
            "preferred_requirements":job.get("preferred_requirements",[]),"role_scope":assess(job,prefs),"eligibility":eligibility,"scoring":scoring,
            "why_apply":["Relevant verified skills: "+", ".join(scoring["matching_skills"])] if scoring["matching_skills"] else ["Review role responsibilities against the candidate profile"],
            "potential_problems":eligibility["unknowns"]+scoring["required_missing_skills"]+[c['reason'] for c in eligibility['checks'] if c['result']=='FAIL']}
