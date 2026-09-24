from datetime import date
import json, re
from ..models.candidate import verified
from ..utils.validators import contains_skill
from ..utils.role_scope import assess
from ..utils.location_match import compatibility

def evaluate(job,profile,preferences,today=None):
    today=today or date.today()
    checks=[]
    def add(label,state,reason): checks.append({"requirement":label,"result":state,"reason":reason})
    scope=assess(job,preferences)
    add('Target role scope',{'IN_SCOPE':'PASS','OUT_OF_SCOPE':'FAIL','NEEDS_REVIEW':'UNKNOWN'}[scope['status']],scope['reason'])
    if not profile.get("identity_confirmed"):
        add("Candidate identity","UNKNOWN","Candidate details and master resume will be supplied and confirmed later")
    checks.append(compatibility(job,profile))
    title=job["title"].casefold()
    if any(x.casefold() in title for x in preferences.get("excluded_titles",[])) or re.search(r"\b(senior|principal|lead|manager)\b",title):
        add("Seniority","FAIL","Outside configured entry-level scope")
    if job.get("listing_state")=="CLOSED":
        add("Listing","FAIL","Employer listing is closed or removed")
    if job.get("closing_at") and job["closing_at"][:10]<today.isoformat():
        add("Closing date","FAIL","Application deadline has passed")
    if not job.get("requirements_reviewed"):
        add("Mandatory requirements","UNKNOWN","Full employer requirements need review")
    # Australian work authority is essential even when the listing does not spell it out.
    rights=verified(profile,"work_rights")
    if rights is None: add("Australian work rights","UNKNOWN","Work rights have not been supplied")
    elif rights is False or (isinstance(rights,dict) and rights.get("authorised") is False):
        add("Australian work rights","FAIL","Verified profile says not authorised")
    elif isinstance(rights,dict) and rights.get("restrictions"):
        add("Work restrictions","UNKNOWN","Check hours and visa restrictions against this role")
    elif rights is True or (isinstance(rights,dict) and rights.get("authorised") is True):
        if isinstance(rights,dict) and rights.get("expires_at") and rights["expires_at"][:10]<today.isoformat():
            add("Australian work rights","FAIL","Recorded work authority has expired")
        else: add("Australian work rights","PASS","Verified work authority recorded")
    else: add("Australian work rights","UNKNOWN","An explicit work authority answer is required")
    for req in job.get("requirements",[]):
        field=req.get("field")
        value=verified(profile,field)
        op=req.get("op","equals"); expected=req.get("value"); result=None
        if op=="manual":
            add(req["label"],"UNKNOWN",req.get("reason","Employer interpretation required")); continue
        if value is not None:
            if op=="equals": result=value==expected
            elif op=="one_of": result=value in expected
            elif op=="before_or_on": result=str(value)[:10]<=expected
            elif op=="after_or_on": result=str(value)[:10]>=expected
            elif op=="between": result=expected[0]<=str(value)[:10]<=expected[1]
            elif op=="contains": result=expected.casefold() in json.dumps(value).casefold()
            elif op=="any_skill": result=any(contains_skill(json.dumps(value),s) for s in expected)
            elif op=="exists": result=bool(value)
        add(req.get("label",field),"UNKNOWN" if result is None else ("PASS" if result else "FAIL"),
            "Verified information unavailable or operator unsupported" if result is None else "Compared with verified profile")
    # A raw qualification requirement must not disappear merely because the
    # listing was marked reviewed. Unsupported conditions remain reviewable.
    for raw,fields in (('education_required',{'education','graduation_date'}),
                       ('experience_required',{'employment_experience'})):
        if job.get(raw) and not any(r.get('field') in fields for r in job.get('requirements',[])):
            add(raw,'UNKNOWN','Explicit qualification requirement needs a structured, source-backed check')
    # Unparsed legal requirements can never turn into automatic eligibility.
    for field in ("citizenship_requirement","work_rights_requirement","clearance_requirement"):
        if job.get(field) and not any(r.get("field") in ({"citizenship_requirement":"citizenship","work_rights_requirement":"work_rights","clearance_requirement":"security_clearance"}[field],) for r in job.get("requirements",[])):
            add(field,"UNKNOWN","Explicit listing requirement needs a structured check")
    skills=json.dumps(verified(profile,"technical_skills") or [])
    for skill in job.get("required_skills",[]):
        add("Mandatory skill: "+skill,"PASS" if contains_skill(skills,skill) else "UNKNOWN",
            "Supported by master resume" if contains_skill(skills,skill) else "No verified evidence; confirm proficiency or equivalent")
    state="NOT_ELIGIBLE" if any(c["result"]=="FAIL" for c in checks) else ("NEEDS_REVIEW" if any(c["result"]=="UNKNOWN" for c in checks) else "ELIGIBLE")
    return {"status":state,"checks":checks,"unknowns":[c["requirement"] for c in checks if c["result"]=="UNKNOWN"],
            "reasons":[c["reason"] for c in checks if c["result"]!="PASS"]}
