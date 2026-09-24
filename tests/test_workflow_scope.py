import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.app.orchestrator import Orchestrator
from backend.app.agents.email_monitor import monitor
from backend.app.utils.config import write_json,settings
from tests.test_pipeline import profile

class WorkflowScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-scope-test-');self.root=Path(self.temp.name)
        self.engine=Orchestrator(self.root)
        write_json(self.root/'data/candidate_profile.json',profile())
    def tearDown(self):self.temp.cleanup()
    def test_post_application_disabled_by_default(self):
        self.assertFalse(settings(self.root)['post_submission_enabled'])
    def test_monitor_never_constructs_mail_reader(self):
        with patch('backend.app.agents.email_monitor.GmailReader',side_effect=AssertionError('User owns Gmail')):
            self.assertEqual(monitor(self.root,self.engine.db,profile())['state'],'USER_MANAGED_POST_APPLICATION')
    def test_normal_and_mail_runs_skip_post_application_hooks(self):
        with patch('backend.app.orchestrator.monitor',side_effect=AssertionError('User owns Gmail')), patch('backend.app.orchestrator.notify_deadlines',side_effect=AssertionError('User owns follow-ups')), patch('backend.app.orchestrator.prepare_interview',side_effect=AssertionError('User owns interviews')):
            normal=self.engine.run(False,False);mail=self.engine.mail_only()
        self.assertEqual(normal['email']['status'],'USER_MANAGED_POST_APPLICATION')
        self.assertEqual(mail['email']['state'],'USER_MANAGED_POST_APPLICATION')
        self.assertEqual(mail['deadlines'],[])
        self.assertEqual(normal['applications_submitted'],0)

if __name__=='__main__':unittest.main()
