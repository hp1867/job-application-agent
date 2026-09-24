import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from backend.app.agents.deadline_manager import extract_deadlines,upcoming
from backend.app.services.notification_service import notify_deadlines
from backend.app.integrations.database import Database
from tests.test_pipeline import job

class DeadlineReminderTests(unittest.TestCase):
    def test_explicit_aest_interview_time(self):
        d=extract_deadlines('Interview on 18 September 2026 at 2pm AEST','2026-09-07T00:00:00+00:00')[0]
        self.assertEqual(d['due_at'],'2026-09-18T14:00:00+10:00');self.assertEqual(d['review'],'CONFIRMED')
    def test_utc_timestamp_preserved(self):
        d=extract_deadlines('Assessment deadline 2026-09-18T02:00:00Z','2026-09-07T00:00:00+00:00')[0]
        self.assertEqual(d['due_at'],'2026-09-18T02:00:00+00:00')
    def test_interview_booking_and_followup(self):
        self.assertEqual(extract_deadlines('Book your interview by 18 September 2026','2026-09-07T00:00:00+00:00')[0]['kind'],'INTERVIEW_BOOKING')
        self.assertEqual(extract_deadlines('Follow up by 18 September 2026','2026-09-07T00:00:00+00:00')[0]['kind'],'FOLLOW_UP')
    def test_business_days_not_guessed(self):
        d=extract_deadlines('Complete the assessment within 3 business days','2026-09-07T00:00:00+00:00')[0]
        self.assertIsNone(d['due_at']);self.assertEqual(d['review'],'NEEDS_REVIEW')
    def test_reminders_idempotent_and_closed_app_ignored(self):
        with tempfile.TemporaryDirectory(prefix='job-agent-reminder-test-') as temp:
            db=Database(Path(temp)/'test.sqlite3');j=job();db.save_job(j);a=db.ensure_application(j)
            due=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
            db.save_deadline({'deadline_id':'fixture','application_id':a['application_id'],'job_id':j['job_id'],'kind':'ASSESSMENT','due_at':due,'review':'CONFIRMED'})
            notify_deadlines(db);notify_deadlines(db);self.assertEqual(len(db.rows('notifications')),1)
            self.assertEqual(db.rows('notifications')[0]['reminder_window'],'24h')
            db.update_application(a['application_id'],{},'CLOSED','Synthetic test closure')
            self.assertEqual(upcoming(db),[])

if __name__=='__main__':unittest.main()
