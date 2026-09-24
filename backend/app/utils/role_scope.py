"""Conservative role-family matching, independent of a board's search accuracy.

This is a preference check, not a fabricated candidate eligibility fact. Ambiguous
graduate/engineering programs require review; clearly unrelated roles fail scope.
"""
import re

DEFAULT_TARGETS=(
    'Software Engineering Intern','Software Developer Intern','Cybersecurity Intern',
    'Cyber Security Intern','Security Analyst Intern','SOC Analyst Intern','IT Intern',
    'Technology Intern','Graduate Software Engineer','Graduate Cybersecurity',
    'Junior Software Developer','Junior Security Analyst',
)
STOP={'intern','internship','internships','graduate','graduates','junior','entry','level','associate',
      'vacationer','cadet','student','trainee','program','programme','programs','opportunity','opportunities',
      'position','positions','role','roles','summer','winter','for','the','a','an','and','of','au','australia',
      'australian','melbourne','victoria','remote','hybrid','full','time','part'}

def tokens(value):
    text=value.casefold()
    text=re.sub(r'\bcyber\s*security\b','cybersecurity',text)
    text=re.sub(r'\binformation\s+technology\b','it',text)
    text=re.sub(r'\b(?:help|service)[ -]?desk\b','it',text)
    text=re.sub(r'\bsecurity\s+operations\s+(?:cent(?:er|re))\b','soc',text)
    text=re.sub(r'\b(?:front[ -]?end|back[ -]?end|full[ -]?stack)\b','software',text)
    words=re.findall(r'[a-z]+',text)
    aliases={'engineering':'engineer','development':'developer','cyber':'cybersecurity','technologies':'technology'}
    return {aliases.get(word,word) for word in words if word not in STOP}

def assess(job,preferences):
    targets=preferences.get('target_roles',DEFAULT_TARGETS)
    if not isinstance(targets,(list,tuple)) or not targets:
        return {'status':'NEEDS_REVIEW','reason':'Configure target roles before automatic shortlisting'}
    title=tokens(job.get('title',''))
    for target in targets:
        core=tokens(target)
        if core and core<=title:
            return {'status':'IN_SCOPE','reason':'Role title matches a configured role family','matched_target':target}
    # Generic program titles do not prove a specialisation either way.
    generic={'engineer','analyst','consultant','technical','specialist','systems','solutions','business'}
    if not title or title<=generic:
        return {'status':'NEEDS_REVIEW','reason':'Role specialisation is ambiguous; inspect the actual program or track'}
    return {'status':'OUT_OF_SCOPE','reason':'Role title is outside the configured target roles; source search keywords alone are not sufficient'}
