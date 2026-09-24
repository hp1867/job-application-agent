import json,re
from ..models.candidate import verified
from ..utils.validators import contains_skill
from ..utils.role_scope import assess
from ..utils.location_match import preference_points, compatibility
WEIGHTS={"technical_skills":30,"experience_projects":20,"education":15,"career_relevance":15,"location":10,"eligibility":10}
def score(job,profile,eligibility,prefs):
    skill_text=json.dumps(verified(profile,"technical_skills") or [])
    required=job.get("required_skills",[])
    optional=job.get("preferred_skills",[])
    matches=[s for s in dict.fromkeys(required+optional) if contains_skill(skill_text,s)]
    missing_req=[s for s in required if s not in matches]
    missing_opt=[s for s in optional if s not in matches]
    # Optional gaps cannot erase evidence of every required skill.
    technical=30*sum(s in matches for s in required)/len(required) if required else (30*sum(s in matches for s in optional)/len(optional) if optional else 15 if verified(profile,"technical_skills") else 0)
    alternatives=[r for r in job.get("requirements",[]) if r.get("op")=="any_skill"]
    if not required and alternatives:
        technical=30*sum(any(contains_skill(skill_text,s) for s in r["value"]) for r in alternatives)/len(alternatives)
    project_text=json.dumps(verified(profile,"projects") or [])
    relevant=[s for s in required+optional if contains_skill(project_text,s)]
    experience=min(20,8+4*len(set(relevant))) if verified(profile,"projects") else 0
    if not required and not optional and alternatives and verified(profile,"projects"):
        experience=15
    education=15 if verified(profile,"education") and any(c["requirement"].lower().find("degree")>=0 and c["result"]=="PASS" for c in eligibility["checks"]) else (10 if verified(profile,"education") else 0)
    title=job["title"].lower()
    role=assess(job,prefs)['status']
    career=0 if role=='OUT_OF_SCOPE' else 15 if role=='IN_SCOPE' and re.search(r'\b(intern|graduate|junior|associate|entry|vacationer|cadet)\b',title) else 5
    location=preference_points(job,profile,prefs)
    points={"technical_skills":round(technical,1),"experience_projects":experience,"education":education,"career_relevance":career,"location":location,
            "eligibility":{"ELIGIBLE":10,"LIKELY_ELIGIBLE":6,"NEEDS_REVIEW":0,"NOT_ELIGIBLE":0}[eligibility["status"]]}
    overall=round(sum(points.values()))
    recommendation=next(label for minimum,label in [(90,"PRIORITY"),(80,"STRONG MATCH"),(70,"GOOD MATCH"),(60,"REVIEW"),(0,"LOW PRIORITY")] if overall>=minimum)
    if profile.get("intake_deferred"):
        overall=None
        recommendation="AWAITING_CANDIDATE"
        points={k:None for k in WEIGHTS}
    return {"overall_score":overall,"components":points,"weights":WEIGHTS,"matching_skills":matches,"missing_skills":missing_req+missing_opt,
            "required_missing_skills":missing_req,"optional_missing_skills":missing_opt,"education_match":education,
            "experience_match":experience,"location_match":location,"location_details":compatibility(job,profile),"eligibility":eligibility["status"],"recommendation":recommendation,
            "score_type":"RULE_BASED_RELEVANCE","provisional":eligibility["status"]!="ELIGIBLE",
            "note":"Relevance estimate, not an ATS vendor score or acceptance probability. Unknown eligibility earns no points."}
