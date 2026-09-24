import unittest
from backend.app.integrations.greenhouse_observer import map_snapshot
from backend.app.integrations.form_steps import resolve_control

class GreenhouseObserverTests(unittest.TestCase):
    def map(self,**control):return map_snapshot({'url':'https://job-boards.greenhouse.io/example/jobs/42',
        'interactive_elements':[{'tag':'input','type':'text','selector':'#field',**control}]})
    def test_exact_contact_label_maps_but_permission_remains_unknown(self):
        result=self.map(label='Email')
        self.assertEqual(result['fields'][0]['candidate_field'],'email')
        self.assertIsNone(result['website_permits_automation']);self.assertFalse(result['form_reviewed'])
    def test_first_name_not_guessed_from_full_name(self):
        self.assertIsNone(self.map(label='First Name')['fields'][0]['candidate_field'])
    def test_combobox_requires_manual_confirmation(self):
        field=self.map(label='Email',role='combobox')['fields'][0]
        self.assertTrue(field['requires_manual_confirmation']);self.assertIsNone(field['candidate_field'])
        self.assertEqual(resolve_control(field,{}, {},[{'question':'Email','answer':'test@example.test','verified':True}])['action'],'MANUAL')
    def test_unknown_question_not_guessed(self):
        self.assertIsNone(self.map(label='Why this company?')['fields'][0]['candidate_field'])
    def test_resume_only_maps_observed_file_control(self):
        self.assertEqual(self.map(type='file',id='resume')['upload_controls'],{'resume':{'selector':'#field'}})
    def test_other_host_is_refused(self):
        with self.assertRaises(ValueError):map_snapshot({'url':'https://other.test/jobs/42'})
