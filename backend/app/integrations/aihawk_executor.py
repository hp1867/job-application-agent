"""Reusable, fill-only AIHawk executor for the durable application queue.

An observer must inspect the live employer form and provide reviewed mappings.
This executor cannot grant website permission, guess fields, log in or submit.
"""
import hashlib,json
from pathlib import Path
from .form_steps import resolve_control,validate_advance
from .aihawk_upload import upload_document
from ..utils.config import read_json


def observed_control(snapshot,locator):
    if not isinstance(locator,dict) or set(locator) not in ({'id'},{'selector'}):
        raise ValueError('An exact observed id or selector is required')
    key=next(iter(locator));value=locator[key]
    if not isinstance(value,str) or not value:raise ValueError('Empty control locator')
    matches=[x for x in snapshot.get('interactive_elements',[]) if x.get(key)==value]
    if len(matches)!=1 or not matches[0].get('selector'):raise ValueError('Control is missing or ambiguous')
    if matches[0].get('disabled'):raise ValueError('Control is disabled')
    return matches[0]


class AIHawkExecutor:
    def __init__(self,session,queue,observer):
        self.session=session;self.queue=queue;self.observer=observer

    def context(self,command):
        self.queue.validate_claim(command)
        run=self.queue.run(command['run_id'])
        if not run or run['phase']!='fill' or run['application_id']!=command['application_id']:
            raise ValueError('Exact active fill workflow required')
        return self.queue.validate_context(run)

    async def execute(self,command):
        from aihawk.mcp import actions
        if command['action'] not in {'FILL','UPLOAD','ADVANCE'}:
            raise ValueError('Only verified fill, upload and non-submitting continuation are exposed')
        app=self.context(command)
        page=await self.observer()
        if page.get('website_permits_automation') is not True or not page.get('website_policy_evidence'):
            raise ValueError('Current website permission evidence required')
        if any(page.get(k) for k in ('captcha','mfa','login_required')):raise ValueError('Manual website step required')
        snapshot=json.loads(await actions.snapshot(self.session))
        if not page.get('observed_url') or snapshot.get('url')!=page['observed_url']:
            raise ValueError('Page changed since observation')
        if snapshot.get('unmeasurable') or snapshot.get('truncated'):
            raise ValueError('Incomplete browser snapshot requires review')
        # The observer is trusted workflow code, never instructions supplied by a listing.
        if page.get('application_identity_verified') is not True or not page.get('application_identity_evidence'):
            raise ValueError('Observed employer and exact role identity required')
        app=self.context(command);packet=app['packet'];payload=command['payload'];action=command['action']
        if action=='FILL':
            fields=[x for x in page.get('fields',[]) if x.get('locator')==payload.get('locator')]
            if len(fields)!=1:raise ValueError('Field mapping is missing or ambiguous')
            profile=read_json(self.queue.root/'data/candidate_profile.json',{})
            answers=read_json(self.queue.root/'data/application_answers.json',[])
            answer=resolve_control(fields[0],profile,packet,answers)
            if answer['action']!='AUTOFILL' or answer.get('answer')!=payload.get('value'):
                raise ValueError('Queued value does not match a safe verified source')
            target=observed_control(snapshot,payload['locator'])
            if target['tag']=='select':
                from .native_select import select_verified_label
                await select_verified_label(self.session.page(),target['selector'],payload['value'],lambda:self.context(command))
            else:
                if target.get('role')=='combobox':raise ValueError('Custom combobox selection requires manual review')
                if target['tag'] not in {'input','textarea'} or target.get('type','text') not in {'text','email','tel','url','search','textarea'}:
                    raise ValueError('This control requires a separately reviewed input adapter')
                if not isinstance(payload['value'],str):raise ValueError('Text control requires a verified text value')
                await actions.type_text(self.session,target['selector'],payload['value'])
                if await self.session.page().input_value(target['selector'])!=payload['value']:
                    raise ValueError('Typed value was not observed; do not retry automatically')
        elif action=='UPLOAD':
            kinds=[k for k,v in page.get('upload_controls',{}).items() if v==payload.get('locator')]
            if len(kinds)!=1:raise ValueError('Upload mapping is missing or ambiguous')
            kind=kinds[0];path=packet.get('documents',{}).get(kind)
            if not path or Path(path).resolve()!=Path(payload.get('path','')).resolve():raise ValueError('Unexpected upload document')
            if payload.get('sha256')!=packet.get('document_hashes',{}).get(kind):raise ValueError('Upload revision changed')
            target=observed_control(snapshot,payload['locator'])
            await upload_document(self.session,target['selector'],packet,kind,self.queue.root,page)
        else:
            if page.get('is_final_step') is not False or payload.get('step_id')!=page.get('step_id'):
                raise ValueError('Continuation is unavailable on final or changed steps')
            control=validate_advance(payload.get('control'),page['step_id'])
            if control!=page.get('next_control'):raise ValueError('Continuation evidence changed')
            target=observed_control(snapshot,control['locator'])
            if target['tag']!='button' or target.get('type')!='button' or target.get('text')!=control['label']:
                raise ValueError('Exact non-submit button required')
            if page.get('fields_filled') is not True or page.get('legal_review_complete') is not True:
                raise ValueError('Current step is not ready to continue')
            await actions.click(self.session,target['selector'])
        self.context(command)
        return {'ok':True,'observation_source':'Installed AIHawk action completed; final workflow observation still required'}
