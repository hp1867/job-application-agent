import re
SECRET = re.compile(r"(?i)(bearer\s+\S+|(?:api[_-]?key|token|password|secret|authorization)\s*[:=]\s*\S+)")
def redact(value):
    if isinstance(value, dict):
        return {k:("[REDACTED]" if any(s in k.lower() for s in ("token","password","secret","answer","authorization","api_key")) else redact(v)) for k,v in value.items()}
    if isinstance(value,list):
        return [redact(v) for v in value]
    return SECRET.sub("[REDACTED]",value) if isinstance(value,str) else value
