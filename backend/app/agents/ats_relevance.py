"""Conservative document coverage, separate from eligibility and fact validation.

Uses only structured listing terms and validated text. Unsupported requirements
stay reviewable; this is not an ATS vendor score or a semantic qualification check.
"""
from ..utils.validators import contains_skill,normal


def terms(values):
    result=[];seen=set()
    for value in values or []:
        if isinstance(value,str) and value.strip() and normal(value) not in seen:
            result.append(value.strip());seen.add(normal(value))
    return result


def coverage(text,keywords):
    keywords=terms(keywords)
    matching=[word for word in keywords if contains_skill(text,word)]
    return {'terms':keywords,'matching':matching,'missing':[word for word in keywords if word not in matching],
            'percent':round(100*len(matching)/len(keywords)) if keywords else None}


def report(manifest,job,extracted_text,facts_pass=False):
    if not facts_pass:
        return {'status':'UNAVAILABLE','reason':'Document facts and extracted content must pass validation first',
                'overall_score':None,'is_eligibility_decision':False}
    sections={field:' '.join(block['text'] for block in manifest.get('blocks',[])
        if block.get('field')==field and isinstance(block.get('text'),str))
        for field in ('education','employment_experience','projects')}
    required=coverage(extracted_text,job.get('required_skills',[]))
    optional=coverage(extracted_text,job.get('preferred_skills',[]))
    education=[];experience=[]
    for requirement in job.get('requirements',[]):
        field=requirement.get('field')
        if field not in sections:continue
        item={'requirement':requirement.get('label') or field,'status':'NEEDS_REVIEW',
              'note':'Structured condition needs eligibility review; no lexical match inferred'}
        value=requirement.get('value');op=requirement.get('op')
        if op=='contains' and isinstance(value,str) and value.strip():
            item.update(status='TERM_PRESENT' if contains_skill(sections[field],value) else 'TERM_NOT_FOUND',term=value,
                        note='Exact term coverage in the relevant document section, not proof of eligibility')
        (education if field=='education' else experience).append(item)
    def summary(items):
        assessed=[x for x in items if x['status']!='NEEDS_REVIEW']
        return {'requirements':items,'assessed_count':len(assessed),'review_count':len(items)-len(assessed),
                'percent':round(100*sum(x['status']=='TERM_PRESENT' for x in assessed)/len(assessed)) if assessed else None}
    education=summary(education);experience=summary(experience)
    # Optional skills are diagnostic only; their absence cannot dilute required coverage.
    components={'required_skills':required['percent'],'education_terms':education['percent'],'experience_terms':experience['percent']}
    weights={'required_skills':60,'education_terms':20,'experience_terms':20}
    scored={key:value for key,value in components.items() if value is not None}
    score=round(sum(value*weights[key] for key,value in scored.items())/sum(weights[key] for key in scored)) if scored else None
    return {'status':'PARTIAL' if education['review_count'] or experience['review_count'] or len(scored)<3 else 'ASSESSED',
            'overall_score':score,'components':components,'weights':weights,'scored_components':list(scored),
            'required_skills':required,'preferred_skills':optional,'education':education,'experience':experience,
            'is_eligibility_decision':False,
            'note':'Lexical coverage of validated document content only. Missing dimensions are unscored, not passes. Optional skills do not reduce the score. Review role requirements separately.'}
