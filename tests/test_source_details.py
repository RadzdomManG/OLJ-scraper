import unittest
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

import watcher


class SourceDetailsTest(unittest.TestCase):
    def test_metadata_is_read_from_post_labels(self):
        html = """<h3>TYPE OF WORK</h3><div>Full Time</div>
        <h3>WAGE / SALARY</h3><div>6-8 Euros per hour</div>
        <h3>HOURS PER WEEK</h3><div>40</div>"""
        details = watcher.parse_detail_kv_fields(BeautifulSoup(html, "lxml"))
        self.assertEqual(details["type_of_work"], "Full Time")
        self.assertEqual(details["wage_salary"], "6-8 Euros per hour")
        self.assertEqual(details["hours_per_week"], "40")

    def test_empty_listing_fields_never_erase_source_values(self):
        job = {"type_of_work": "Full Time", "wage_salary": "$500/month"}
        watcher.merge_source_details(job, {"type_of_work": "", "wage_salary": ""})
        self.assertEqual(job["type_of_work"], "Full Time")
        self.assertEqual(job["wage_salary"], "$500/month")

    def test_incomplete_job_is_retried_after_an_hour(self):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.assertFalse(watcher.source_detail_due({"type_of_work": "", "wage_salary": "", "detail_checked_at": recent}))
        self.assertTrue(watcher.source_detail_due({"type_of_work": "", "wage_salary": "", "detail_checked_at": old}))


if __name__ == "__main__":
    unittest.main()
