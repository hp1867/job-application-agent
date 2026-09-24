"""Observed multi-step forms; no arbitrary click primitive or guessed navigation."""
from datetime import datetime, timezone, timedelta
from ..models.candidate import verified
from ..agents.application_agent import answer_question, LEGAL_MARKERS
from ..services.application_service import record_form_review
from ..utils.validators import normal
from ..utils.config import now
from ..utils.answer_memory import revisions, review_hash
from .browser import packet_hash, record_blocker


def resolve_control(control, profile, packet, answers):
    question = control['question']
    if control.get('requires_manual_confirmation') is True:
        return {'action':'MANUAL','reason':'Observed control requires manual confirmation'}
    if any(marker in normal(question) for marker in LEGAL_MARKERS):
        return {'action': 'MANUAL', 'reason': 'Sensitive or legal declaration'}
    path = control.get('candidate_path')
    if path is not None:
        if not isinstance(path, list) or not path or not isinstance(path[0], str):
            return {'action': 'ASK', 'reason': 'Invalid candidate source path'}
        field = path[0]
    else:
        field = control.get('candidate_field'); path = [field] if field else None
    if path:
        value = packet.get('verified_fields', {}).get(field)
        if value is None or value != verified(profile, field):
            return {'action': 'ASK', 'reason': 'Mapped source field is not verified in this packet'}
        try:
            for key in path[1:]:
                if isinstance(value, list) and type(key) is int and key >= 0: value = value[key]
                elif isinstance(value, dict) and isinstance(key, str): value = value[key]
                else: raise ValueError('Invalid source path')
        except (IndexError, KeyError, ValueError):
            return {'action': 'ASK', 'reason': 'Mapped source path has no verified value'}
        if type(value) not in (str, int, float, bool) or value == '' or value == 'UNKNOWN':
            return {'action': 'ASK', 'reason': 'A scalar verified answer is required for this control'}
        return {'action': 'AUTOFILL', 'answer': value, 'candidate_path': path}
    return answer_question(question, answers)


def validate_advance(control, step_id):
    if not isinstance(control, dict) or control.get('kind') != 'CONTINUE' or control.get('submits_application') is not False:
        raise ValueError('Observed non-submission continuation evidence required')
    if not all(control.get(key) for key in ('locator', 'label', 'evidence', 'next_step_id')):
        raise ValueError('Observed continuation locator, label, evidence and next step required')
    if not isinstance(control['next_step_id'], str) or control['next_step_id'] == step_id:
        raise ValueError('Continuation must identify a different observed next step')
    # Evidence cannot turn an explicitly submitting/declarative label into Next.
    if any(term in normal(control['label']) for term in ('submit', 'apply', 'accept', 'agree', 'certify', 'finish', 'send')):
        raise ValueError('Potential submission or declaration is not a continuation action')
    return control


class FormSteps:
    def __init__(self, db, driver, max_steps=10):
        self.db = db; self.driver = driver; self.max_steps = max_steps

    def fill(self, profile, job, application, answers, page, progress=None):
        aid = application['application_id']; packet = application['packet']
        progress = progress or {'current_step_id': page.get('step_id'), 'completed_steps': [], 'questions': [], 'uploaded_kinds': [], 'awaiting_transition': False}
        completed = list(progress['completed_steps']); questions = list(progress['questions']); uploaded = set(progress['uploaded_kinds'])

        def save(current, awaiting=False):
            state = {'packet_hash': packet_hash(packet), 'current_step_id': current, 'completed_steps': completed,
                     'questions': questions, 'uploaded_kinds': sorted(uploaded), 'awaiting_transition': awaiting,
                     'completed_answer_hash': review_hash(revisions(answers), [q for q in questions if q.get('step_id') in completed]), 'observed_at': now()}
            self.db.update_application(aid, {'form_progress': state})
            return state

        def block(code, detail):
            record_blocker(self.db, aid, code, detail)
            return {'status': 'BLOCKED', 'reason': code, 'submitted': False}

        def guard(observation):
            for flag, code in (('captcha','CAPTCHA'), ('mfa','MFA'), ('login_required','LOGIN_REQUIRED')):
                if observation.get(flag): return block(code, 'Complete the manual step, then re-inspect the same form')
            if observation.get('website_permits_automation') is not True or not observation.get('website_policy_evidence'):
                return block('AUTOMATION_PROHIBITED', 'Website automation permission must be confirmed on every step')
            if observation.get('application_identity_verified') is not True or not observation.get('application_identity_evidence'):
                return block('FORM_STATE_CHANGED', 'Verify the employer and exact role on this application step')
            if not isinstance(observation.get('step_id'), str) or not observation['step_id'] or type(observation.get('is_final_step')) is not bool:
                return block('FORM_STATE_CHANGED', 'Observed step identity and final-step state are required')
            return None

        def review(observation, unresolved, final_step):
            nonlocal packet
            evidence = {'expected_packet_hash': packet_hash(packet), 'observation_source': observation.get('observation_source'),
                        'observed_at': now(), 'questions': questions, 'answer_memory_hash': review_hash(revisions(answers), questions),
                        'form_reviewed': final_step and observation.get('form_reviewed') is True,
                        'fields_filled': not unresolved and observation.get('fields_filled') is True,
                        'uploads_confirmed': final_step and observation.get('uploads_confirmed') is True and required_uploads.issubset(uploaded),
                        'legal_review_complete': observation.get('legal_review_complete') is True,
                        'website_permits_automation': observation.get('website_permits_automation') is True,
                        'website_policy_evidence': observation.get('website_policy_evidence'),
                        **{flag: observation.get(flag) is True for flag in ('captcha','mfa','login_required')}}
            updated = record_form_review(self.db, aid, evidence); packet = updated['packet']
            save(observation['step_id'])
            if unresolved: record_blocker(self.db, aid, 'UNKNOWN_QUESTION', 'Verified or manual answers required: ' + '; '.join(unresolved))
            return {'status': updated['status'], 'unresolved_questions': unresolved, 'submitted': False, 'completed_steps': completed}

        required_uploads = {kind for kind, path in packet.get('documents', {}).items() if path}
        if progress.get('packet_hash'):
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(progress['observed_at'])
                if age < timedelta(minutes=-5) or age > timedelta(hours=2): raise ValueError('Expired progress')
            except (ValueError, TypeError, KeyError): return block('FORM_STATE_CHANGED', 'Saved form progress expired; a fresh form review is required')
            used = [q for q in questions if q.get('step_id') in completed]
            if progress.get('completed_answer_hash') != review_hash(revisions(answers), used):
                return block('FORM_STATE_CHANGED', 'Previously completed step answers changed; review those steps again')
        if page.get('step_id') != progress['current_step_id']:
            return block('FORM_STATE_CHANGED', 'The current browser step does not match saved progress; do not replay a continuation')
        for _ in range(self.max_steps):
            stopped = guard(page)
            if stopped: return stopped
            step_id = page['step_id']
            if step_id in completed: return block('FORM_STEP_LIMIT', 'Repeated form step detected; inspect the workflow before continuing')
            if len(completed) >= self.max_steps: return block('FORM_STEP_LIMIT', 'Maximum observed form steps reached')
            save(step_id)
            questions[:] = [q for q in questions if q.get('step_id') != step_id]
            unresolved = []
            for control in page.get('fields', []):
                answer = resolve_control(control, profile, packet, answers)
                question = {'question': control['question'], 'step_id': step_id, 'answer': answer.get('answer'),
                            'verified': answer['action'] == 'AUTOFILL', 'requires_manual_confirmation': answer['action'] != 'AUTOFILL'}
                if answer.get('candidate_path'): question['candidate_path'] = answer['candidate_path']
                questions.append(question)
                if answer['action'] == 'AUTOFILL': self.driver.fill(control['locator'], answer['answer'])
                else: unresolved.append(control['question'])
            uploaded_here = set()
            for kind, locator in page.get('upload_controls', {}).items():
                path = packet.get('documents', {}).get(kind)
                if path:
                    self.driver.upload(locator, path); uploaded_here.add(kind)
            final = self.driver.observe()
            stopped = guard(final)
            if stopped: return stopped
            if final['step_id'] != step_id: return block('FORM_STATE_CHANGED', 'Filling unexpectedly changed the application step')
            if page.get('is_final_step') != final.get('is_final_step') or page.get('next_control') != final.get('next_control'):
                return block('FORM_STATE_CHANGED', 'Navigation controls changed during filling; inspect again')
            seen = {normal(control['question']) for control in page.get('fields', [])}
            for control in final.get('fields', []):
                if normal(control['question']) not in seen:
                    questions.append({'question': control['question'], 'step_id': step_id, 'answer': None, 'verified': False, 'requires_manual_confirmation': True})
                    unresolved.append(control['question'])
            if not uploaded_here.issubset(set(final.get('confirmed_uploads', []))):
                return block('RESUME_UPLOAD_FAILURE', 'File selection was not confirmed on this step')
            uploaded.update(uploaded_here)
            if unresolved: return review(final, unresolved, False)
            if final.get('fields_filled') is not True or final.get('legal_review_complete') is not True:
                return review(final, [], False)
            if final['is_final_step']:
                if final.get('next_control'): return block('FORM_STATE_CHANGED', 'Final step unexpectedly has a continuation control')
                return review(final, [], True)
            try: control = validate_advance(final.get('next_control'), step_id)
            except ValueError as exc: return block('FORM_STATE_CHANGED', str(exc))
            if control['next_step_id'] in completed or len(completed) + 1 >= self.max_steps:
                return block('FORM_STEP_LIMIT', 'Continuation would loop or exceed the configured step bound')
            completed.append(step_id)
            # Persist the expected destination BEFORE clicking. An interrupted or
            # uncertain Next must never be clicked again on the old step.
            save(control['next_step_id'], awaiting=True)
            self.driver.advance(control, step_id)
            page = self.driver.observe()
            if page.get('step_id') != control['next_step_id']:
                return block('FORM_STATE_CHANGED', 'Continuation outcome differs from its observed destination; do not retry')
        return block('FORM_STEP_LIMIT', 'Maximum observed form steps reached')
