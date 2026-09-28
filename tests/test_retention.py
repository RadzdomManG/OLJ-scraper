import unittest
from datetime import datetime, timedelta, timezone

import watcher


class RollingJobRetentionTest(unittest.TestCase):
    def test_new_discovery_replaces_oldest_even_if_its_post_is_old(self):
        base = datetime(2026, 9, 20, tzinfo=timezone.utc)
        events = [
            {
                "event_key": f"job-{number}",
                "title": f"Job {number}",
                "detected_at": (base + timedelta(seconds=number)).isoformat(),
                "posted_at_iso": (base - timedelta(days=3)).isoformat() if number == 5000 else (base + timedelta(seconds=number)).isoformat(),
            }
            for number in range(5001)
        ]
        kept, keys = watcher.retain_newest_events(events)
        self.assertEqual(len(kept), 5000)
        self.assertNotIn("job-0", keys)
        self.assertIn("job-5000", keys)
        self.assertEqual(kept[0]["event_key"], "job-5000")

    def test_jobs_api_pages_all_stored_jobs_without_age_filter(self):
        old_jobs = watcher.state["events"]
        try:
            with watcher.state_lock:
                watcher.state["events"] = [
                    {
                        "event_key": f"job-{number}",
                        "title": f"Job {number}",
                        "detected_at": (datetime.now(timezone.utc) - timedelta(days=number)).isoformat(),
                        "posted_at_iso": (datetime.now(timezone.utc) - timedelta(days=number)).isoformat(),
                        "priority": "medium",
                    }
                    for number in range(3)
                ]
            response = watcher.app.test_client().get("/api/jobs?limit=2&offset=2")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["total"], 3)
            self.assertEqual(payload["filtered_count"], 3)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["jobs"][0]["event_key"], "job-2")
        finally:
            with watcher.state_lock:
                watcher.state["events"] = old_jobs


if __name__ == "__main__":
    unittest.main()
