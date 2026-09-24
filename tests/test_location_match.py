import tempfile, unittest
from pathlib import Path
from tests.test_pipeline import profile, job
from tests import test_hardening as hardening
from backend.app.models.candidate import verify
from backend.app.utils.location_match import compatibility, preference_points
from backend.app.agents.eligibility_checker import evaluate
from backend.app.agents.application_agent import gates
from backend.app.orchestrator import Orchestrator
from backend.app.services.job_service import ingest
from backend.app.services.application_service import approve
from backend.app.integrations.browser import packet_hash
from backend.app.utils.config import write_json, now

class LocationTests(unittest.TestCase):
    def test_matching_verified_city_passes(self):
        self.assertEqual(compatibility(job(),profile())['result'],'PASS')
    def test_unknown_candidate_location_never_earns_points(self):
        p=profile();verify(p,'location',None,'synthetic')
        self.assertEqual(evaluate(job(),p,{})['status'],'NEEDS_REVIEW')
        self.assertEqual(preference_points(job(),p,{}),0)
    def test_remote_is_not_worldwide(self):
        p=profile();verify(p,'location','London, United Kingdom','synthetic')
        self.assertEqual(compatibility(job(location='Australia',remote_type='REMOTE'),p)['result'],'UNKNOWN')
        # An unsupported locality stays reviewable; an explicit country-only
        # residence supplies enough evidence for the country mismatch check.
        verify(p,'location','United Kingdom','synthetic')
        verify(p,'relocation_preference',False,'synthetic')
        self.assertEqual(compatibility(job(location='Australia',remote_type='REMOTE'),p)['result'],'FAIL')
    def test_remote_au_requires_known_jurisdiction(self):
        for value in ('Remote','Anywhere','Melbourne','Australia / New Zealand'):
            self.assertEqual(compatibility(job(location=value,remote_type='REMOTE'),profile())['result'],'UNKNOWN',value)
        self.assertEqual(compatibility(job(location='Australia',remote_type='REMOTE'),profile())['result'],'PASS')
    def test_foreign_city_name_does_not_match_australian_city(self):
        self.assertEqual(compatibility(job(location='Melbourne, Florida, USA'),profile())['result'],'UNKNOWN')
    def test_unrecognised_jurisdiction_is_not_ignored(self):
        self.assertEqual(compatibility(job(location='Melbourne, VIC, France'),profile())['result'],'UNKNOWN')
        self.assertEqual(preference_points(job(),profile(),{'preferred_locations':['Melbourne France']}),0)
    def test_long_region_names_and_postcode_preserve_location_match(self):
        p=profile();verify(p,'location','Adelaide, South Australia 5000','synthetic')
        self.assertEqual(compatibility(job(location='Adelaide, SA, Australia'),p)['result'],'PASS')
    def test_relocation_boolean_is_not_a_role_specific_plan(self):
        p=profile();j=job(location='Sydney, NSW, Australia',remote_type='HYBRID')
        for value in (None,True):
            verify(p,'relocation_preference',value,'synthetic')
            self.assertEqual(evaluate(j,p,{})['status'],'NEEDS_REVIEW')
        verify(p,'relocation_preference',False,'synthetic')
        self.assertEqual(evaluate(j,p,{})['status'],'NOT_ELIGIBLE')
    def test_same_state_does_not_establish_commute(self):
        self.assertEqual(compatibility(job(location='Victoria, Australia',remote_type='HYBRID'),profile())['result'],'UNKNOWN')
    def test_qualified_remote_restriction_requires_review(self):
        for value in ('Australia excluding Victoria','Australia - NSW residents only','Australia within 20km of office'):
            self.assertEqual(compatibility(job(location=value,remote_type='REMOTE'),profile())['result'],'UNKNOWN')
    def test_remote_region_mismatch_requires_review(self):
        self.assertEqual(compatibility(job(location='NSW, Australia',remote_type='REMOTE'),profile())['result'],'UNKNOWN')
    def test_conflicting_arrangement_requires_review(self):
        self.assertEqual(compatibility(job(location='Hybrid Melbourne, VIC, Australia',remote_type='REMOTE'),profile())['result'],'UNKNOWN')
    def test_preferences_are_editable_not_hardcoded(self):
        p=profile();verify(p,'location','Sydney, NSW, Australia','synthetic');j=job(location='Sydney, NSW, Australia')
        self.assertEqual(preference_points(j,p,{'preferred_locations':['Sydney']}),10)
        self.assertEqual(preference_points(j,p,{'preferred_locations':['Melbourne']}),0)
        self.assertEqual(evaluate(j,p,{})['status'],'ELIGIBLE')
    def test_arrangement_and_foreign_preferences_are_respected(self):
        p=profile();j=job(remote_type='HYBRID')
        self.assertEqual(preference_points(j,p,{'preferred_locations':['Remote Australia']}),0)
        self.assertEqual(preference_points(j,p,{'preferred_locations':['Hybrid Melbourne']}),10)
        self.assertEqual(preference_points(j,p,{'preferred_locations':['Melbourne USA']}),0)
        self.assertEqual(preference_points(job(location='Australia',remote_type='REMOTE'),p,{'remote_australia':False}),0)
    def test_no_location_preferences_earns_no_preference_points(self):
        self.assertEqual(preference_points(job(),profile(),{'preferred_locations':[]}),0)
    def test_pipeline_keeps_location_blocked_job_out_of_readiness(self):
        with tempfile.TemporaryDirectory(prefix='job-location-test-') as folder:
            root=Path(folder);p=profile();verify(p,'relocation_preference',False,'synthetic')
            write_json(root/'data/candidate_profile.json',p)
            write_json(root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'preferred_locations':['Australia'],'application_threshold':70})
            write_json(root/'data/inbox/jobs/test.json',[job(location='Sydney, NSW, Australia',remote_type='HYBRID')])
            engine=Orchestrator(root);result=engine.run(False,False)
            self.assertEqual(result['applications_prepared'],0)
            self.assertEqual(engine.db.rows('applications')[0]['status'],'ANALYSED')
            self.assertEqual(engine.db.rows('applications')[0]['eligibility']['status'],'NOT_ELIGIBLE')
    def test_location_change_revokes_approval_and_fresh_gate_blocks(self):
        fixture=hardening.HardeningTests();fixture.setUp()
        try:
            app=fixture.ready();approve(fixture.db,app['application_id'],packet_hash(app['packet']))
            changed={**fixture.j,'location':'Sydney, NSW, Australia','remote_type':'HYBRID','is_official':True,'listing_verified_at':now()}
            ingest(fixture.db,[changed]);current=fixture.db.application(app['application_id'])
            self.assertIsNone(current['packet'])
            with fixture.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM approvals').fetchone()[0],0)
            result=gates(fixture.config,fixture.p,fixture.db.job(changed['job_id']),current,fixture.db)
            self.assertIn('FRESH_ELIGIBILITY_CHECK_FAILED',result['blockers'])
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
