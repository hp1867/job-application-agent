"""Export JSON Schema contracts for external tools and inbox producers."""
from pathlib import Path
from .candidate import FIELDS
from .application import STATUSES
from .email_event import CLASSIFICATIONS
from ..utils.config import write_json
BASE={"$schema":"https://json-schema.org/draft/2020-12/schema"}
def export_schemas(root):
    nullable={"type":["string","null"]}
    candidate={**BASE,"title":"CandidateProfile","type":"object","required":FIELDS+["VERIFIED_INFORMATION","UNKNOWN_INFORMATION","provenance","identity_confirmed"],
        "properties":{**{k:{} for k in FIELDS},"identity_confirmed":{"type":"boolean"},"intake_deferred":{"type":"boolean"},
                      "VERIFIED_INFORMATION":{"type":"array","uniqueItems":True,"items":{"enum":FIELDS}},"UNKNOWN_INFORMATION":{"type":"array","uniqueItems":True,"items":{"enum":FIELDS}},"provenance":{"type":"object"}}}
    for k in ("full_name","email","phone","location","linkedin","github","portfolio","graduation_date"):candidate["properties"][k]=nullable
    for k in ("education","employment_experience","projects","technical_skills","soft_skills","certifications","achievements","languages","target_roles","preferred_locations","preferred_industries"):candidate["properties"][k]={"type":["array","null"]}
    for k in ("requires_sponsorship","relocation_preference"):candidate["properties"][k]={"type":["boolean","null"]}
    job={**BASE,"title":"JobInboxRecord","type":"object","required":["company","title","source","source_url"],"properties":{
        **{k:nullable for k in ("job_id","external_id","location","remote_type","employment_type","currency","experience_required","education_required","work_rights_requirement","citizenship_requirement","clearance_requirement","posted_at","closing_at","date_discovered")},
        **{k:{"type":"string","minLength":1} for k in ("company","title","source","source_url")},"description":{"type":"string"},
        "canonical_url":{"type":"string","format":"uri"},"required_skills":{"type":"array","items":{"type":"string"}},"preferred_skills":{"type":"array","items":{"type":"string"}},
        "salary_min":{"type":["number","null"]},"salary_max":{"type":["number","null"]},"requirements_reviewed":{"type":"boolean"},"requirements":{"type":"array"},"source_evidence":{"type":"array"}}}
    application={**BASE,"title":"Application","type":"object","required":["application_id","job_id","status"],"properties":{"application_id":{"type":"string"},"job_id":{"type":"string"},"status":{"enum":STATUSES},"score":{"type":["number","null"],"minimum":0,"maximum":100},"date_applied":nullable,"packet":{"type":["object","null"]}}}
    email={**BASE,"title":"EmailCapture","type":"object","required":["email_id","sender","subject","body","received_at"],"properties":{k:{"type":"string"} for k in ("email_id","sender","subject","body","received_at")}}
    answer={**BASE,"title":"VerifiedAnswer","type":"object","required":["question","normalised_question","answer","verified","last_verified","requires_manual_confirmation"],"properties":{"question":{"type":"string"},"normalised_question":{"type":"string"},"answer":{},"verified":{"type":"boolean"},"last_verified":nullable,"requires_manual_confirmation":{"type":"boolean"}}}
    event={**BASE,'title':'EmailEvent','type':'object','required':['email_id','application_id','classification','confidence','received_at'],
        'properties':{'email_id':{'type':'string'},'application_id':{'type':'string'},'classification':{'enum':CLASSIFICATIONS},'confidence':{'type':'number','minimum':0,'maximum':1},'received_at':{'type':'string'},'review':{'type':'string'}}}
    contracts={"candidate_profile":candidate,"job":job,"application":application,"email_event":event,'email_capture':email,"application_answer":answer}
    for name,schema in contracts.items():write_json(Path(root)/"schemas"/(name+".schema.json"),schema)
    return {"schemas_exported":list(contracts)}
