"""Read-only Gmail REST option plus connector capture bridge. No send scope or action."""
import json,base64
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from pathlib import Path
from ..utils.config import env_values,read_json
def flatten_mime(part):
    pieces=[]
    body=part.get("body") or {}
    mime=part.get("mime_type") or part.get("mimeType","")
    if mime in ("text/plain","text/html"):
        text=body.get("content")
        if not text and body.get("data"):
            text=base64.urlsafe_b64decode(body["data"]+"===").decode("utf-8",errors="replace")
        if text:pieces.append(text)
    for child in part.get("parts") or []:pieces.extend(flatten_mime(child))
    return pieces
class GmailReader:
    SCOPE="https://www.googleapis.com/auth/gmail.readonly"
    def __init__(self,root):
        self.env=env_values(root);self.root=Path(root)
    def status(self,profile):
        connection=read_json(self.root/"data/integrations.json",{}).get("gmail",{})
        address=connection.get("email")
        confirmed=self.env.get("GMAIL_CANDIDATE_CONFIRMED","false").lower()=="true"
        matches=bool(address and profile.get("email") and address.casefold()==profile["email"].casefold())
        return {"mode":self.env.get("GMAIL_MODE","connector"),"connected":connection.get("connected",False),
                "mailbox":address,"candidate_mailbox_confirmed":confirmed and (matches or connection.get("explicitly_authorised_for_candidate") is True),
                "next_action":None if confirmed and matches else "Confirm candidate mailbox or connect the candidate's mail account"}
    def connector_captures(self):
        folder=self.root/"data/inbox/gmail"
        messages=[]
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            data=read_json(path,[])
            messages.extend(data.get("messages",[]) if isinstance(data,dict) else data)
        return messages
    def _token(self):
        keys=["GMAIL_CLIENT_ID","GMAIL_CLIENT_SECRET","GMAIL_REFRESH_TOKEN"]
        if not all(self.env.get(k) for k in keys):raise ValueError("Read-only Gmail OAuth is not configured")
        body=urlencode({"client_id":self.env[keys[0]],"client_secret":self.env[keys[1]],"refresh_token":self.env[keys[2]],"grant_type":"refresh_token"}).encode()
        with urlopen(Request("https://oauth2.googleapis.com/token",body),timeout=20) as r:return json.load(r)["access_token"]
    def api_messages(self,query):
        token=self._token()
        headers={"Authorization":"Bearer "+token}
        base="https://gmail.googleapis.com/gmail/v1/users/me/messages"
        messages=[];page=None
        for _ in range(5):
            q={"q":query,"maxResults":100}
            if page:q["pageToken"]=page
            with urlopen(Request(base+"?"+urlencode(q),headers=headers),timeout=20) as r:listing=json.load(r)
            for item in listing.get("messages",[]):
                with urlopen(Request(base+"/"+item["id"]+"?format=full",headers=headers),timeout=20) as r:message=json.load(r)
                payload=message.get("payload",{});h={x["name"].lower():x["value"] for x in payload.get("headers",[])}
                from datetime import datetime,timezone
                messages.append({"email_id":item["id"],"subject":h.get("subject",""),"sender":h.get("from",""),
                                 "body":"\n".join(flatten_mime(payload)),
                                 "received_at":datetime.fromtimestamp(int(message["internalDate"])/1000,timezone.utc).isoformat()})
            page=listing.get("nextPageToken")
            if not page:break
        return messages

