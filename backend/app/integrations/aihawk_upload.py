"""Resume-upload extension over the installed AIHawk browser session.

The caller still owns candidate, eligibility, website and application gates.
No arbitrary filesystem upload, script injection, submit click or retry.
"""
import hashlib,json
from pathlib import Path

async def upload_document(session,selector,packet,kind,root,observation):
    if observation.get('website_permits_automation') is not True or not observation.get('website_policy_evidence'):
        raise ValueError('Observed website permission required')
    if any(observation.get(k) for k in ('captcha','mfa','login_required')):
        raise ValueError('Manual website step required')
    value=packet.get('documents',{}).get(kind)
    if not value:raise ValueError('Document is not in the application packet')
    path=Path(value).resolve();allowed=(Path(root)/'generated').resolve()
    if not path.is_relative_to(allowed) or not path.is_file():raise ValueError('Document must be in the project generated directory')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=packet.get('document_hashes',{}).get(kind):
        raise ValueError('Document changed since preparation')
    from aihawk.mcp import actions
    snapshot=json.loads(await actions.snapshot(session))
    if not observation.get('observed_url') or snapshot.get('url')!=observation['observed_url']:
        raise ValueError('Page changed since website permission was observed')
    matches=[item for item in snapshot.get('interactive_elements',[]) if item.get('selector')==selector]
    if len(matches)!=1 or matches[0].get('tag')!='input' or matches[0].get('type')!='file':
        raise ValueError('An exact observed file-input control is required')
    await session.page().set_input_files(selector,str(path),timeout=15000)
    return {'selected':True,'kind':kind,'requires_observed_upload_confirmation':True}
