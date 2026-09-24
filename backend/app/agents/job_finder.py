from pathlib import Path
from urllib.error import HTTPError,URLError
from ..utils.config import read_json,now,write_json
from ..models.job import normalise
from ..integrations.mcp_jobs import JobsMCP
def discover(root,db,live=True):
    jobs=[]; errors=[]; sources=[]
    inbox=Path(root)/"data/inbox/jobs"
    for path in sorted(inbox.glob("*.json")) if inbox.exists() else []:
        try:records=read_json(path,[])
        except (ValueError,OSError):
            errors.append({"source":path.name,"error":"INVALID_CAPTURE","next_action":"Repair the captured JSON; other sources continue"})
            continue
        records=records.get("jobs",[]) if isinstance(records,dict) else records
        for record in records:
            try: jobs.append(normalise(record))
            except Exception as exc: errors.append({"source":path.name,"error":str(exc),"next_action":"Correct invalid imported listing"})
        sources.append({"source":path.name,"result":"IMPORTED","count":len(records)})
    if live:
        from ..integrations.public_ats import read_board,search_scope
        config=read_json(Path(root)/"data/discovery_sources.json",{})
        for board in config.get("public_ats",[])[:5]:
            if board.get("enabled") is not True:continue
            source=board.get("company","Employer")+" public ATS"
            try:
                records=read_board(board);selected=[j for j in records if search_scope(j)]
                jobs.extend(selected)
                sources.append({"source":source,"result":"OK","count":len(selected),"board_jobs_checked":len(records)})
            except Exception as exc:
                errors.append({"source":source,"error":type(exc).__name__,"next_action":"Review API access or retry next run; other sources continue"})
                db.log("job_finder",source,"SOURCE_UNAVAILABLE",error=type(exc).__name__)
        try:
            result=JobsMCP().search()
            records=result if isinstance(result,list) else result.get("jobs",result.get("results",[]))
            for r in records if isinstance(records,list) else []:
                url=r.get("apply_url") or r.get("url") or r.get("job_url")
                if not url: continue
                company=r.get("company_name") or r.get("company")
                if isinstance(company,dict): company=company.get("name")
                raw={"company":company,"title":r.get("title"),"location":r.get("location"),"external_id":r.get("id"),"source":"AI Dev Jobs MCP",
                     "source_url":url,"description":r.get("description") or "","posted_at":r.get("posted_at"),"remote_type":(r.get("workplace") or "").upper() or None,
                     "preferred_skills":r.get("tags",[]),"source_evidence":[{"url":url,"source":"AI Dev Jobs MCP","fetched_at":now()}]}
                try: jobs.append(normalise(raw))
                except ValueError as exc: errors.append({"source":"AI Dev Jobs MCP","error":str(exc),"next_action":"Review source schema"})
            sources.append({"source":"AI Dev Jobs MCP","result":"OK","count":len(records) if isinstance(records,list) else 0})
        except Exception as exc:
            code=getattr(exc,"code",None)
            kind="RATE_LIMITED" if code==429 else "FORBIDDEN" if code==403 else "MCP_UNAVAILABLE"
            errors.append({"source":"AI Dev Jobs MCP","error":kind,"next_action":"Use official listings and search connector; retry next scheduled run"})
            db.log("job_finder","Read-only MCP discovery",kind,error=type(exc).__name__)
    return jobs,sources,errors
