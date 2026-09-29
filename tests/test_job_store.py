import os
import tempfile
import unittest

from job_store import JobStore


class JobStoreTest(unittest.TestCase):
    def test_jobs_seen_settings_and_stages_survive_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "jobs.sqlite3")
            store = JobStore(path)
            store.save_jobs([{"event_key": "freelancer:123", "site_type": "freelancer", "detected_at": "2026-09-29T00:00:00Z", "title": "AI Video Creator"}])
            store.add_seen({"freelancer:123"})
            store.set_source("freelancer", False, 180)
            store.set_match_settings(["ComfyUI", "LoRA"], ["unpaid"])
            store.set_stage("freelancer:123", "saved")

            reopened = JobStore(path)
            self.assertEqual(reopened.load_jobs()[0]["title"], "AI Video Creator")
            self.assertIn("freelancer:123", reopened.load_seen())
            self.assertFalse(reopened.source_settings([("freelancer", True, 120)])["freelancer"]["enabled"])
            self.assertEqual(reopened.match_settings()["exclude_keywords"], ["unpaid"])
            self.assertEqual(reopened.stages()["freelancer:123"], "saved")

            reopened.save_jobs([])
            self.assertEqual(reopened.load_jobs(), [])
            self.assertIn("freelancer:123", reopened.load_seen())


if __name__ == "__main__":
    unittest.main()
