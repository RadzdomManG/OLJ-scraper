import os
import tempfile
import unittest
from unittest.mock import patch

import watcher
from job_store import JobStore


class MultiSourceApiTest(unittest.TestCase):
    def test_source_stage_date_filters_and_persistent_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(os.path.join(directory, "jobs.sqlite3"))
            old_events = watcher.state.get("events", [])
            old_keys = watcher.state.get("event_keys", set())
            old_stages = watcher.state.get("job_stages", {})
            try:
                with patch.object(watcher, "JOB_STORE", store):
                    with watcher.state_lock:
                        watcher.state["events"] = [
                            {"event_key": "freelancer:1", "site": "Freelancer", "site_type": "freelancer", "title": "ComfyUI job", "detected_at": "2026-09-29T10:00:00Z", "posted_at_iso": "", "notification_sent": True},
                            {"event_key": "onlinejobsph:2", "site": "OnlineJobsPH", "site_type": "onlinejobsph", "title": "Other job", "detected_at": "2026-09-28T10:00:00Z", "posted_at_iso": "", "notification_sent": False},
                        ]
                        watcher.state["event_keys"] = {"freelancer:1", "onlinejobsph:2"}
                        watcher.state["job_stages"] = {}
                    client = watcher.app.test_client()
                    response = client.post("/api/jobs/freelancer:1/stage", json={"stage": "saved"})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(store.stages()["freelancer:1"], "saved")
                    response = client.get("/api/jobs?source=freelancer&stage=saved&date_from=2026-09-29&notified=sent")
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["filtered_count"], 1)
                    self.assertEqual(payload["jobs"][0]["stage"], "saved")
            finally:
                with watcher.state_lock:
                    watcher.state["events"] = old_events
                    watcher.state["event_keys"] = old_keys
                    watcher.state["job_stages"] = old_stages


if __name__ == "__main__":
    unittest.main()
