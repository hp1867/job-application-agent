"""Bind only answers relevant to the reviewed form, without exposing answer values."""
from .validators import digest,normal

def revisions(answers):
    grouped={}
    for answer in answers:
        question=normal(answer.get('normalised_question') or answer['question'])
        value={key:answer.get(key) for key in ('answer','verified','requires_manual_confirmation')}
        grouped.setdefault(question,set()).add(digest(value))
    return {question:digest(sorted(values)) for question,values in grouped.items()}

def review_hash(answer_revisions,questions):
    names={normal(question['question']) for question in questions}
    return digest({name:answer_revisions.get(name) for name in sorted(names)})
