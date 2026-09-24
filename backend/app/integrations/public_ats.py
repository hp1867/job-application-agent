"""Read-only public Greenhouse/Lever APIs. No submission API, keys or candidate payloads."""
import html,json,re
from html.parser import HTMLParser
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit
from ..utils.config import now
from ..models.job import normalise

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("API redirect requires source review")

class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,text):self.parts.append(text)

def plain(value):
    parser=PlainText();parser.feed(html.unescape(html.unescape(value or "")))
    return " ".join(" ".join(parser.parts).split())

def fetch_json(url):
    if urlsplit(url).hostname not in {"boards-api.greenhouse.io","api.lever.co"}:raise ValueError("Unaudited ATS API host")
    request=Request(url,headers={"Accept":"application/json","User-Agent":"JobApplicationAgent/1.0 (public job discovery)"})
    with build_opener(NoRedirect()).open(request,timeout=20) as response:
        raw=response.read(4_000_001)
    if len(raw)>4_000_000:raise ValueError("ATS response exceeds size limit")
    return json.loads(raw)

def read_board(config):
    board=config.get("board","");provider=config.get("provider")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",board):raise ValueError("Invalid board token")
    if not config.get("company") or not config.get("evidence_url"):raise ValueError("Reviewed employer board evidence required")
    if provider=="greenhouse":
        url=f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        records=fetch_json(url).get("jobs",[])
    elif provider=="lever":
        url=f"https://api.lever.co/v0/postings/{board}?mode=json"
        records=fetch_json(url)
        if len(records)>=1000:raise ValueError("Large board requires explicit pagination review")
    else:raise ValueError("Unsupported public ATS provider")
    jobs=[]
    for record in records:
        if provider=="greenhouse":
            raw={"title":record["title"],"source_url":record["absolute_url"],"location":record.get("location",{}).get("name"),
                 "description":plain(record.get("content")),"external_id":str(record["id"]),"posted_at":record.get("first_published"),"closing_at":record.get("application_deadline")}
        else:
            categories=record.get("categories",{})
            raw={"title":record["text"],"source_url":record.get("hostedUrl") or record["applyUrl"],"location":categories.get("location"),
                 "employment_type":categories.get("commitment"),"description":plain(record.get("descriptionPlain") or record.get("description"))+" "+" ".join(plain(x.get("content")) for x in record.get("lists",[])),"external_id":record["id"]}
        raw.update(company=config["company"],source=provider.title()+" employer board",is_official=True,requirements_reviewed=False,
                   listing_state="OPEN",listing_verified_at=now(),source_evidence=[{"url":url,"source":provider,"fetched_at":now(),"employer_evidence":config["evidence_url"]}])
        jobs.append(normalise(raw))
    return jobs

def search_scope(job):
    title=job["title"].lower();location=(job.get("location") or "").lower()
    junior=bool(re.search(r"intern|graduate|junior|associate|entry|vacationer|cadet",title))
    technical=bool(re.search(r"software|developer|cyber|security|technology|\bit\b|\bsoc\b",title))
    senior=bool(re.search(r"senior|principal|staff|\blead\b|manager|director",title))
    australia=any(x in location for x in ("australia","melbourne","victoria","sydney","brisbane","adelaide","perth","canberra"))
    return junior and technical and not senior and australia
