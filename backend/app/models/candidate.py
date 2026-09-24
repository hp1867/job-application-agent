from ..utils.config import now
FIELDS = ["full_name","email","phone","location","linkedin","github","portfolio","education","employment_experience",
"projects","technical_skills","soft_skills","certifications","achievements","languages","availability","target_roles",
"preferred_locations","preferred_industries","work_rights","citizenship","visa_status","requires_sponsorship",
"graduation_date","study_year","driver_licence","security_clearance","salary_expectation","relocation_preference"]
def empty_profile():
    return {"schema_version":1,"identity_confirmed":False, **{k:None for k in FIELDS},
            "VERIFIED_INFORMATION":[], "UNKNOWN_INFORMATION":FIELDS.copy(), "provenance":{}, "master_resume":None}
def verify(profile, field, value, source):
    if field not in FIELDS or not source:
        raise ValueError("Known field and evidence source required")
    if value is not None and value != "UNKNOWN":
        if field in {"requires_sponsorship","relocation_preference"} and type(value) is not bool:
            raise ValueError("This field requires true or false")
        if field == "work_rights" and type(value) is not bool and not (isinstance(value,dict) and type(value.get("authorised")) is bool):
            raise ValueError("Work rights require true/false or an object with authorised and any restrictions")
        if field == "graduation_date":
            from datetime import date
            date.fromisoformat(value)
        if field == "study_year" and (type(value) is not int or not 1 <= value <= 10):
            raise ValueError("Study year must be a whole number from 1 to 10")
        if field in {"technical_skills","soft_skills","certifications","education","employment_experience","projects","languages","achievements","target_roles","preferred_locations","preferred_industries"} and not isinstance(value,list):
            raise ValueError("This field requires a structured list")
    profile[field] = value
    known = value is not None and value != "UNKNOWN"
    profile["VERIFIED_INFORMATION"] = sorted(set(profile.get("VERIFIED_INFORMATION",[])) - {field} | ({field} if known else set()))
    profile["UNKNOWN_INFORMATION"] = [x for x in FIELDS if x not in profile["VERIFIED_INFORMATION"]]
    profile.setdefault("provenance",{})[field] = {"source":source,"verified_at":now()} if known else None
    return profile
def verified(profile, field):
    value=profile.get(field)
    return value if value != "UNKNOWN" and field in profile.get("VERIFIED_INFORMATION",[]) and profile.get("provenance",{}).get(field) else None
