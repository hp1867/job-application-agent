"""Scoped read-only Streamable HTTP MCP client. Never installs server code."""
import json
from urllib.request import Request,urlopen
from ..utils.validators import public_url
ALLOWED_TOOLS={"search_jobs","get_job","list_companies","get_company","get_stats","get_similar_jobs","list_tags"}
ENDPOINT="https://aidevboard.com/mcp"
class JobsMCP:
    def __init__(self,endpoint=ENDPOINT):
        if endpoint!=ENDPOINT: raise ValueError("MCP endpoint has not been audited")
        self.endpoint=public_url(endpoint); self.session=None; self.counter=0
    def rpc(self,method,params=None,notification=False):
        self.counter+=1
        payload={"jsonrpc":"2.0","method":method,"params":params or {}}
        if not notification: payload["id"]=self.counter
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"}
        if self.session: headers["Mcp-Session-Id"]=self.session
        with urlopen(Request(self.endpoint,json.dumps(payload).encode(),headers),timeout=25) as response:
            self.session=response.headers.get("Mcp-Session-Id") or self.session
            raw=response.read(2_000_001).decode()
            if len(raw)>2_000_000: raise ValueError("MCP response too large")
        if not raw.strip(): return {}
        if raw.lstrip().startswith("data:"):
            raw="\n".join(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
        result=json.loads(raw)
        if result.get("error"): raise ValueError("MCP returned an error")
        return result.get("result",{})
    def initialise(self):
        info=self.rpc("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"job-application-agent","version":"1.0.0"}})
        self.rpc("notifications/initialized",notification=True)
        return info
    def call(self,name,arguments):
        if name not in ALLOWED_TOOLS: raise ValueError("MCP action is outside read-only allowlist")
        if name=="search_jobs" and set(arguments)-{"query","location","level","limit","posted_within_days","workplace","tags","company","global_remote"}:
            raise ValueError("Unexpected search parameters")
        return self.rpc("tools/call",{"name":name,"arguments":arguments})
    def search(self,query="software",location="Australia",limit=25):
        self.initialise()
        result=self.call("search_jobs",{"query":query,"location":location,"limit":limit,"posted_within_days":30})
        if result.get("isError"): raise ValueError("Job source unavailable")
        if result.get("structuredContent"): return result["structuredContent"]
        texts=[c.get("text","") for c in result.get("content",[]) if c.get("type")=="text"]
        for t in texts:
            try: return json.loads(t)
            except ValueError: continue
        return {"raw_text":"\n".join(texts),"jobs":[]}

