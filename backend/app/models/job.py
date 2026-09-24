from dataclasses import dataclass, field, asdict
from ..utils.config import now
from ..utils.validators import canonical_url, digest, normal

@dataclass
class Job:
    job_id: str
    company: str
    title: str
    location: str | None
    source: str
    source_url: str
    canonical_url: str
    external_id: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    description: str = ""
    required_skills: list = field(default_factory=list)
    preferred_skills: list = field(default_factory=list)
    experience_required: str | None = None
    education_required: str | None = None
    work_rights_requirement: str | None = None
    citizenship_requirement: str | None = None
    clearance_requirement: str | None = None
    posted_at: str | None = None
    closing_at: str | None = None
    date_discovered: str = field(default_factory=now)
    requirements: list = field(default_factory=list)
    responsibilities: list = field(default_factory=list)
    preferred_requirements: list = field(default_factory=list)
    employer_domains: list = field(default_factory=list)
    is_official: bool = False
    requirements_reviewed: bool = False
    listing_verified_at: str | None = None
    listing_state: str = "UNKNOWN"
    cover_letter_required: bool = False
    source_evidence: list = field(default_factory=list)
    analysis: dict = field(default_factory=dict)

def normalise(raw):
    required = ("company","title","source_url","source")
    if any(not raw.get(k) for k in required):
        raise ValueError("Job requires company, title, source and source_url")
    if any(not isinstance(raw[k],str) for k in required):raise ValueError("Job identity fields must be text")
    for key in ("required_skills","preferred_skills"):
        if key in raw and (not isinstance(raw[key],list) or not all(isinstance(s,str) for s in raw[key])):raise ValueError("Skills must be a list of text")
    for key in ("salary_min","salary_max"):
        if raw.get(key) is not None:
            import math
            if type(raw[key]) not in (int,float) or not math.isfinite(raw[key]) or raw[key]<0:raise ValueError("Salary must be a finite non-negative number")
    canonical_url(raw["source_url"])
    url = canonical_url(raw.get("canonical_url") or raw["source_url"])
    identity = [normal(raw["company"]),normal(raw["title"]),normal(raw.get("location")),url]
    data = {k:v for k,v in raw.items() if k in Job.__dataclass_fields__}
    data.update(job_id=raw.get("job_id") or digest(identity)[:24], canonical_url=url)
    data.setdefault("location",None)
    return asdict(Job(**data))
