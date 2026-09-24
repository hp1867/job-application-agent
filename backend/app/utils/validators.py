import hashlib, json, re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def normal(text):
    return re.sub(r"[^a-z0-9+#]+", " ", (text or "").casefold()).strip()
def public_url(value):
    p = urlsplit(value or "")
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("A public HTTPS URL without credentials is required")
    import ipaddress
    host = p.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("Private destinations are not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and not ip.is_global:
        raise ValueError("Private destinations are not allowed")
    return value
def canonical_url(value):
    public_url(value)
    p = urlsplit(value)
    query = [(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "tracking")) and k.lower() not in {"ref","referrer","source","src","gh_src"}]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
def safe_filename(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:160]
def contains_skill(text, skill):
    aliases = {"javascript":["javascript", "js"], "node.js":["node.js","nodejs","node/express"],
               "express.js":["express.js","express"], "c++":["c++"], "c#":["c#"],"react":["react","reactjs"],
               "cybersecurity":["cybersecurity","cyber security"],"ci/cd":["ci/cd","ci cd"]}
    items = aliases.get(skill.casefold(), [skill])
    return any(re.search(r"(?<![a-z0-9])"+re.escape(x.casefold())+r"(?![a-z0-9+#])",text.casefold()) for x in items)
