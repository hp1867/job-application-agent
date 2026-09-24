import tempfile,unittest
from pathlib import Path
from backend.app.services.resume_parser import parse_resume_text
from backend.app.services.resume_service import extract_resume
from backend.app.utils.config import read_json,write_json

TEXT='Name: Test Candidate\nEmail: candidate@example.test\n\nEDUCATION\nQualification: Bachelor of Software Engineering\nInstitution: Example University\nDates: 2024 – present\n\nPROJECTS\nProject name: Example App\nTechnologies: Python, React\nBuilt a synthetic validation tool.\n\nTechnical Skills: Python, C++, React\nLanguages\nEnglish; Hindi\n\nUnknown original content stays here.\n'

class ResumeParserTests(unittest.TestCase):
    def test_lossless_lines_sections_and_spans(self):
        parsed=parse_resume_text(TEXT)
        self.assertEqual(''.join(line['text'] for line in parsed['lines']),TEXT)
        self.assertEqual(''.join(section['source_text'] for section in parsed['sections']),TEXT)
        for proposal in parsed['proposals']:
            source=proposal['source'];self.assertEqual(TEXT[source['start']:source['end']],proposal['value'])
            self.assertFalse(proposal['verified'])
    def test_structured_entries_keep_exact_labels_without_inference(self):
        parsed=parse_resume_text(TEXT);education=next(s for s in parsed['sections'] if s['category']=='education')
        self.assertEqual(education['entries'][0]['labelled_values']['institution'][0]['value'],'Example University')
        self.assertNotIn('graduation_date',[p['field'] for p in parsed['proposals']])
    def test_skills_are_not_inferred_from_experience_prose(self):
        parsed=parse_resume_text('EXPERIENCE\nUsed Python to build a tool.\n')
        self.assertFalse(any(p['field']=='technical_skills' for p in parsed['proposals']))
    def test_prose_after_languages_is_preserved_not_proposed(self):
        parsed=parse_resume_text(TEXT)
        self.assertFalse(any(p['value']=='Unknown original content stays here.' for p in parsed['proposals']))
        self.assertIn('Unknown original content stays here.',parsed['source_text'])
    def test_other_sections_do_not_become_skill_values(self):
        parsed=parse_resume_text('Skills\nPython, C++\nReferences\nAvailable upon request\n')
        self.assertEqual([p['value'] for p in parsed['proposals']],['Python','C++'])
    def test_conflicting_contacts_require_review(self):
        parsed=parse_resume_text('Email: one@example.test\nEmail: two@example.test\n')
        self.assertIn('email',parsed['conflicting_fields'])
    def test_reference_email_is_not_candidate_contact(self):
        parsed=parse_resume_text('References\nEmail: referee@example.test\n')
        self.assertFalse(any(p['field']=='email' for p in parsed['proposals']))
    def test_project_name_is_not_candidate_identity(self):
        parsed=parse_resume_text('Projects\nName: Synthetic App\nTechnologies: Python\n')
        self.assertFalse(any(p['field']=='full_name' for p in parsed['proposals']))
        self.assertEqual(parsed['sections'][0]['entries'][0]['labelled_values']['name'][0]['value'],'Synthetic App')
    def test_unlabelled_identity_and_legal_values_are_not_verified(self):
        parsed=parse_resume_text('Someone Example\nWork rights: Student visa\nGraduation date: June 2027\n')
        self.assertFalse(any(p['field']=='full_name' for p in parsed['proposals']))
        self.assertTrue(all(p['verified'] is False for p in parsed['proposals']))
        self.assertEqual(next(p['value'] for p in parsed['proposals'] if p['field']=='graduation_date'),'June 2027')
    def test_import_preserves_original_and_does_not_touch_active_profile(self):
        with tempfile.TemporaryDirectory(prefix='job-resume-parser-') as folder:
            root=Path(folder);source=root/'synthetic.txt';source.write_text(TEXT,encoding='utf-8')
            profile={'identity_confirmed':False,'intake_deferred':True,'VERIFIED_INFORMATION':[]}
            write_json(root/'data/candidate_profile.json',profile)
            result=extract_resume(source,root)
            self.assertEqual(Path(result['preserved_path']).read_bytes(),source.read_bytes())
            self.assertEqual(read_json(root/'data/candidate_profile.json'),profile)
            proposal=read_json(root/'data/candidate_import_proposal.json')
            self.assertEqual(proposal['VERIFIED_INFORMATION'],[]);self.assertIsNone(proposal['email'])
            self.assertTrue(Path(result['structured_path']).is_file())

if __name__=='__main__':unittest.main()
