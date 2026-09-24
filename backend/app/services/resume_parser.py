"""Lossless text segmentation and conservative, unverified resume proposals.

No external model or candidate inference is used. Each proposed value points to
the exact extracted-text span supporting it. Unlabelled entities remain raw text.
"""
import re

HEADINGS={
    'education':'education','academic qualifications':'education',
    'experience':'employment_experience','work experience':'employment_experience',
    'employment history':'employment_experience','professional experience':'employment_experience',
    'projects':'projects','personal projects':'projects','academic projects':'projects',
    'skills':'technical_skills','technical skills':'technical_skills',
    'soft skills':'soft_skills','certifications':'certifications','certificates':'certifications',
    'achievements':'achievements','awards':'achievements','languages':'languages',
    'summary':'summary','professional summary':'summary','profile':'summary',
    'contact':'contact','contact information':'contact',
    'references':'references','publications':'publications','interests':'interests','volunteering':'volunteering',
}
LABELS={'name':'full_name','full name':'full_name','email':'email','phone':'phone','mobile':'phone',
        'location':'location','linkedin':'linkedin','github':'github','portfolio':'portfolio',
        'availability':'availability','graduation date':'graduation_date',
        'visa':'visa_status','visa status':'visa_status','work rights':'work_rights',
        'citizenship':'citizenship','sponsorship':'requires_sponsorship','salary expectation':'salary_expectation'}
ENTRY_LABELS={'qualification','degree','institution','university','role','title','company','employer',
              'dates','start date','end date','project name','name','technologies'}
CONTACT_FIELDS={'full_name','email','phone','location','linkedin','github','portfolio'}
LIST_FIELDS={'technical_skills','soft_skills','certifications','achievements','languages'}

def parse_resume_text(text):
    if not isinstance(text,str):raise TypeError('Extracted resume text must be text')
    lines=[];offset=0;sections=[];proposals=[];section=None
    for index,raw in enumerate(text.splitlines(keepends=True),1):
        end=offset+len(raw);content=raw.rstrip('\r\n');stripped=content.strip()
        item={'line':index,'start':offset,'end':end,'text':raw};lines.append(item)
        heading=re.fullmatch(r'\s*([A-Za-z][A-Za-z /&-]{1,60})\s*:\s*(.*?)\s*',content)
        heading_name=(heading.group(1) if heading else stripped.rstrip(':')).casefold()
        category=HEADINGS.get(heading_name)
        if category:
            section={'category':category,'heading':heading_name,'line_start':index,'start':offset,'end':end,'line_ids':[],'entries':[]}
            sections.append(section)
        if section is None:
            section={'category':'unclassified','heading':None,'line_start':index,'start':offset,'end':end,'line_ids':[],'entries':[]};sections.append(section)
        section['line_ids'].append(index);section['end']=end
        def propose(field,value,start,stop,kind='explicit_label'):
            if value:
                proposals.append({'field':field,'value':value,'verified':False,'requires_review':True,'extraction_kind':kind,
                                  'source':{'start':start,'end':stop,'line':index,'text':text[start:stop]}})
        if heading and heading.group(2) and heading_name in LABELS and (LABELS[heading_name] not in CONTACT_FIELDS or section['category'] in {'contact','unclassified'}):
            begin=offset+heading.start(2);finish=offset+heading.end(2)
            propose(LABELS[heading_name],heading.group(2),begin,finish)
        # Only dedicated skill/list sections are split; never mine skills from prose.
        if section['category'] in LIST_FIELDS:
            value=heading.group(2) if category and heading else '' if category else stripped.lstrip('-*• ').strip()
            base=offset+(heading.start(2) if category and heading else content.find(value))
            for token in re.finditer(r'[^,;|]+',value):
                fragment=token.group();trimmed=fragment.strip()
                if trimmed.endswith('.') or len(trimmed.split())>8:continue  # Preserve ambiguous prose, do not turn it into a skill/language.
                begin=base+token.start()+len(fragment)-len(fragment.lstrip())
                propose(section['category'],trimmed,begin,begin+len(trimmed),'section_list_item')
        if section['category'] in {'education','employment_experience','projects'} and not category:
            if stripped:
                if not section['entries'] or section['entries'][-1].get('closed'):
                    section['entries'].append({'start':offset,'end':end,'labelled_values':{},'line_ids':[]})
                entry=section['entries'][-1];entry['end']=end;entry['line_ids'].append(index)
                if heading and heading_name in ENTRY_LABELS:
                    entry['labelled_values'].setdefault(heading_name,[]).append({'value':heading.group(2),
                        'start':offset+heading.start(2),'end':offset+heading.end(2)})
            elif section['entries']:section['entries'][-1]['closed']=True
        offset=end
    for section in sections:
        section['source_text']=text[section['start']:section['end']]
        for entry in section['entries']:
            entry.pop('closed',None);entry['source_text']=text[entry['start']:entry['end']]
            entry['requires_review']=True
    # Unambiguous email extraction is still a proposal, never verified identity.
    matches=[match for match in re.finditer(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',text)
             if any(s['category'] in {'contact','unclassified'} and s['start']<=match.start()<s['end'] for s in sections)]
    emails={match.group() for match in matches}
    if len(emails)==1 and not any(p['field']=='email' for p in proposals):
        match=matches[0]
        proposals.append({'field':'email','value':match.group(),'verified':False,'requires_review':True,'extraction_kind':'unique_email',
                          'source':{'start':match.start(),'end':match.end(),'text':match.group()}})
    conflicts=[]
    for field in LABELS.values():
        values={p['value'] for p in proposals if p['field']==field}
        if len(values)>1:conflicts.append(field)
    if len(emails)>1:conflicts.append('email')
    return {'schema_version':1,'parser_version':1,'source_text':text,'lines':lines,'sections':sections,'proposals':proposals,
            'conflicting_fields':sorted(set(conflicts)),'verification_state':'UNVERIFIED_PROPOSALS',
            'review_notes':['Section entries preserve source wording; unlabeled institutions, employers and dates are not inferred.',
                            'Legal, date and numeric values are raw text proposals, not validated candidate facts.']}
