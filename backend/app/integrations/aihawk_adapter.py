"""Adapted action descriptions from AIHawk actions_help.py.
MIT Copyright (c) 2024-2026 AIHawk contributors. See THIRD_PARTY_NOTICES.md.
The upstream free-form browser/stealth executor is not started. All actions are
structured by this project's orchestrator and executed through the approved UI connector.
"""
from ..utils.validators import public_url
UPSTREAM_COMMIT="afe1f66dd3f1572d59a78ea67688a0d0e49e8b25"
def _short(value,limit=60):
    text=" ".join((value if isinstance(value,str) else repr(value)).split())
    return text if len(text)<=limit else text[:limit-3]+"..."
def summarise(name,args=None):
    # Unlike upstream, never echo typed text, keys, tokens, form answers or scripts.
    args=args or {}
    if name=="browser_navigate":
        from urllib.parse import urlsplit
        p=urlsplit(args.get("url",""))
        return _short(p.scheme+"://"+p.netloc+p.path,80)
    if name in {"browser_type","browser_upload"}:return _short(args.get("field",""))+" <- [PRIVATE VALUE]"
    if name=="browser_click":return _short(args.get("label",""))
    if name in {"browser_read_text","browser_read_html"}:return "Inspect current application page"
    return name
def plan_application(job,verified_fields,documents):
    public_url(job["canonical_url"])
    steps=[{"tool":"browser_navigate","args":{"url":job["canonical_url"]}},
           {"tool":"browser_read_html","args":{},"purpose":"Inspect visible fields, restrictions, CAPTCHA and declarations"}]
    steps.extend({"tool":"browser_type","args":{"field":field,"value":value},"requires_observed_control":True}
                 for field,value in verified_fields.items())
    steps.extend({"tool":"browser_upload","args":{"field":kind,"path":path},"requires_observed_control":True}
                 for kind,path in documents.items() if path)
    steps.append({"tool":"browser_read_html","args":{},"purpose":"Read complete final application and record all questions"})
    return steps

