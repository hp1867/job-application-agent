"""Source-observed Greenhouse field mapping; never grants permission to fill.

Only exact contact labels map to profile fields. Names are not split, custom
questions are not guessed, and complex/ambiguous controls require review.
"""
from urllib.parse import urlsplit

CONTACT_LABELS={'Full Name':'full_name','Email':'email','Phone':'phone','LinkedIn Profile':'linkedin',
                'Please provide your GitHub link':'github','Portfolio':'portfolio'}

def map_snapshot(snapshot):
    url=urlsplit(snapshot.get('url',''))
    if url.scheme!='https' or url.hostname!='job-boards.greenhouse.io' or '/jobs/' not in url.path:
        raise ValueError('Exact observed Greenhouse listing required')
    fields=[];uploads={};warnings=[]
    for item in snapshot.get('interactive_elements',[]):
        if item.get('tag') not in {'input','select','textarea'}:continue
        selector=item.get('selector')
        if not selector:
            warnings.append('An observed control has no unambiguous selector');continue
        label=(item.get('label') or '').strip()
        if item.get('type')=='file':
            if item.get('id')=='resume' and 'resume' not in uploads:uploads['resume']={'selector':selector}
            else:warnings.append('Additional upload control needs mapping: '+selector)
            continue
        manual=not label or item.get('role')=='combobox' or item.get('tag')=='select' or item.get('type') in {'checkbox','radio','number','date'}
        fields.append({'question':label or 'Unlabelled application control '+selector,
            'candidate_field':None if manual else CONTACT_LABELS.get(label),'locator':{'selector':selector},
            'requires_manual_confirmation':manual})
    return {'observed_url':snapshot['url'],'fields':fields,'upload_controls':uploads,'warnings':warnings,
            'website_permits_automation':None,'website_policy_evidence':None,'form_reviewed':False,
            'fields_filled':False,'uploads_confirmed':False,'legal_review_complete':False,
            'application_identity_verified':False,'application_identity_evidence':None,
            'note':'Mapping proposal only. Review website permission, exact role, missing controls and upload evidence on the live form.'}
