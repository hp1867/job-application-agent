import re
def classify(message):
    subject=message.get("subject","")
    text=(subject+"\n"+message.get("body","")).casefold()
    # A snippet is not enough evidence for autonomous status updates.
    if not message.get("body"):
        return {"classification":"UNKNOWN","confidence":0.0,"review":"NEEDS_REVIEW","reason":"Full message body required"}
    if re.search(r"(job alert|recommended jobs|jobs you may|daily jobs|new jobs for you)",subject.casefold()):
        return {"classification":"UNKNOWN","confidence":0.1,"review":"NEEDS_REVIEW","reason":"Job alert, not an application response"}
    if re.search(r"not (?:an? |yet an? |a formal )?(?:job )?offer|does not constitute.{0,25}offer|not (?:a )?rejection",text):
        return {"classification":"UNKNOWN","confidence":0.3,"review":"NEEDS_REVIEW","reason":"Negated recruitment outcome requires full contextual review"}
    rules=[
    ("REJECTION",r"(not (?:be )?(?:progressing|progress|proceeding|proceed|moving forward|successful)|unsuccessful|regret to inform|decided to (?:proceed|move forward) with other candidates)",
        r"(application|position|role|candidate|interview)"),
    ("OFFER",r"(pleased|delighted|happy).{0,60}(offer)|offer of employment|formal (?:job )?offer",
        r"(employment|position|role|contract|start date|salary)"),
    ("INTERVIEW",r"(invite|invitation|schedule|arrange|book).{0,90}interview|interview.{0,60}(scheduled|confirmed)",
        r"(availability|time|date|meet|video|teams|zoom|calendar|booking)"),
    ("PHONE_SCREEN",r"(phone|telephone|screening).{0,40}(call|screen|conversation)",
        r"(schedule|invite|available|availability|book|discuss)"),
    ("ASSESSMENT",r"(complete|invited|invite|take).{0,100}(assessment|coding challenge|aptitude test)",
        r"(deadline|link|by |within|hours|days|portal|complete)"),
    ("INFORMATION_REQUEST",r"(provide|send|upload|confirm).{0,80}(information|document|transcript|availability|work rights)",
        r"(application|role|position|recruitment)"),
    ("APPLICATION_CONFIRMATION",r"(thank you for applying|application.{0,35}(received|submitted)|received your application)",
        r"(position|role|application|review|recruitment)"),
    ("GENERAL_UPDATE",r"still (?:reviewing|considering)|application (?:is|remains) under review|recruitment process.{0,50}ongoing",
        r"(application|position|role|recruitment)")
    ]
    hits=[kind for kind,a,b in rules if re.search(a,text,re.S) and re.search(b,text,re.S)]
    if len(hits)>1:
        return {"classification":"UNKNOWN","confidence":0.5,"review":"NEEDS_REVIEW","reason":"Multiple response types detected; interpret complete thread","candidates":hits}
    if hits:
        return {"classification":hits[0],"confidence":0.88,"review":"CONFIDENT","reason":"Multiple contextual phrases agree"}
    return {"classification":"UNKNOWN","confidence":0.2,"review":"NEEDS_REVIEW","reason":"No confident multi-signal classification"}
