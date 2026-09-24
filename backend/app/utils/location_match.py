"""Conservative location compatibility, distinct from job-search preferences.

No geocoding, citizenship inference, or assumption that remote means worldwide.
Unknown localities and qualified restriction prose require an operator review.
"""
import re
from ..models.candidate import verified

COUNTRIES = {
    'AU': ('australia', 'au', 'aus'),
    'NZ': ('new zealand', 'nz'),
    'US': ('united states', 'usa', 'us', 'florida', 'california'),
    'GB': ('united kingdom', 'uk', 'england', 'scotland'),
    'CA': ('canada',),
}
REGIONS = {
    'VIC': ('victoria', 'vic'), 'NSW': ('new south wales', 'nsw'),
    'QLD': ('queensland', 'qld'), 'SA': ('south australia', 'sa'),
    'WA': ('western australia', 'wa'), 'TAS': ('tasmania', 'tas'),
    'ACT': ('australian capital territory', 'act'), 'NT': ('northern territory', 'nt'),
}
CITIES = ('melbourne', 'sydney', 'brisbane', 'adelaide', 'perth', 'hobart',
          'canberra', 'darwin', 'geelong', 'ballarat', 'bendigo', 'gold coast',
          'newcastle', 'wollongong')

def has(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text))

def geography(value):
    text = value.casefold().strip() if isinstance(value, str) else ''
    countries = {key for key, names in COUNTRIES.items() if any(has(text, name) for name in names)}
    regions = {key for key, names in REGIONS.items() if any(has(text, name) for name in names)}
    # State names are jurisdiction evidence only without a conflicting country.
    if regions and not countries: countries.add('AU')
    remainder = text
    known = list(CITIES) + [name for names in (*COUNTRIES.values(), *REGIONS.values()) for name in names]
    known += ['remote', 'hybrid', 'on-site', 'on site', 'onsite', 'or', 'and']
    for name in sorted(known, key=len, reverse=True):
        remainder = re.sub(r'(?<!\w)' + re.escape(name) + r'(?!\w)', ' ', remainder)
    return {'countries': countries, 'regions': regions, 'unparsed': bool(re.search(r'[a-z]', remainder)),
            'cities': {city for city in CITIES if has(text, city)}, 'text': text}

def arrangement(job):
    value = str(job.get('remote_type') or '').upper().replace('-', '_')
    text = str(job.get('location') or '').casefold()
    if value == 'HYBRID' or has(text, 'hybrid'): return 'HYBRID'
    if value in {'ONSITE', 'ON_SITE', 'ON SITE'}: return 'ONSITE'
    if value == 'REMOTE' or has(text, 'remote'): return 'REMOTE'
    return 'UNSPECIFIED'

def compatibility(job, profile):
    place = geography(job.get('location'))
    candidate = geography(verified(profile, 'location'))
    mode = arrangement(job)
    def outcome(result, reason):
        return {'requirement': 'Work location', 'result': result, 'reason': reason, 'arrangement': mode}
    if not candidate['text']: return outcome('UNKNOWN', 'Verified candidate location is unavailable')
    if not place['text']: return outcome('UNKNOWN', 'Employer work location is unspecified')
    if str(job.get('remote_type') or '').upper() == 'REMOTE' and re.search(r'\b(on[- ]site|hybrid)\b', place['text']):
        return outcome('UNKNOWN', 'Employer location and remote arrangement conflict')
    if re.search(r'\b(except|excluding|must|reside|resident|within|only|timezone|time zone)\b', place['text']):
        return outcome('UNKNOWN', 'Qualified location restrictions need explicit employer review')
    if place['unparsed'] or candidate['unparsed']:
        return outcome('UNKNOWN', 'Unresolved locality or jurisdiction text requires review; partial names are insufficient')
    # AU work authority elsewhere in eligibility cannot establish foreign authority.
    if place['countries'] != {'AU'}:
        return outcome('UNKNOWN', 'Australian work jurisdiction is not unambiguously established')
    if candidate['countries'] != {'AU'}:
        if candidate['countries'] and verified(profile, 'relocation_preference') is False:
            return outcome('FAIL', 'Listed Australian location differs from verified residence and relocation is declined')
        return outcome('UNKNOWN', 'Confirm Australian residence or a role-specific relocation plan')
    if mode == 'REMOTE':
        if place['cities'] and not place['cities'].intersection(candidate['cities']):
            return outcome('UNKNOWN', 'Remote listing names a different city; confirm whether it restricts residence')
        if place['regions'] and not place['regions'].intersection(candidate['regions']):
            return outcome('UNKNOWN', 'Remote listing names a region; confirm residence eligibility')
        return outcome('PASS', 'Verified Australian residence matches the listed remote jurisdiction')
    if place['cities'].intersection(candidate['cities']):
        if place['regions'] and candidate['regions'] and not place['regions'].intersection(candidate['regions']):
            return outcome('UNKNOWN', 'Matching city names have inconsistent region evidence')
        return outcome('PASS', 'Verified city matches a listed work city; no commute distance is inferred')
    if not place['cities'] or not candidate['cities']:
        return outcome('UNKNOWN', 'City-level on-site or hybrid compatibility needs confirmation')
    if verified(profile, 'relocation_preference') is False:
        return outcome('FAIL', 'Different work city and verified relocation preference is no')
    return outcome('UNKNOWN', 'Different work city requires a confirmed role-specific relocation or attendance plan')

def preference_points(job, profile, preferences):
    check = compatibility(job, profile)
    if check['result'] != 'PASS': return 0
    place = geography(job.get('location')); mode = arrangement(job)
    if mode == 'REMOTE' and preferences.get('remote_australia') is False: return 0
    desired = preferences.get('preferred_locations', ['Melbourne', 'Victoria', 'Australia', 'Remote Australia', 'Hybrid Melbourne'])
    if not isinstance(desired, list): return 0
    for value in desired:
        if not isinstance(value, str): continue
        target = geography(value)
        if target['unparsed']: continue
        if target['countries'] and not target['countries'].intersection(place['countries']): continue
        if has(target['text'], 'remote') and mode != 'REMOTE': continue
        if has(target['text'], 'hybrid') and mode != 'HYBRID': continue
        if target['cities']:
            matches = bool(target['cities'].intersection(place['cities']))
        elif target['regions']:
            matches = bool(target['regions'].intersection(place['regions']))
        elif target['countries']:
            matches = bool(target['countries'].intersection(place['countries']))
        else: matches = False
        if matches: return 10
    return 0
