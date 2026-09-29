import unittest

from sources import guru, himalayas, jobicy, virtualstaff, weworkremotely


class MoreJobSourcesTest(unittest.TestCase):
    def test_rss_sources_keep_non_niche_jobs_and_source_fields(self):
        wwr = b'<rss><channel><item><title>Acme: Virtual Assistant</title><link>https://weworkremotely.com/remote-jobs/acme-va</link><pubDate>Tue, 29 Sep 2026 01:00:00 GMT</pubDate><region>Anywhere</region><type>Full-Time</type></item></channel></rss>'
        item = next(iter(weworkremotely.parse(wwr).values()))
        self.assertEqual((item["title"], item["company"], item["type_of_work"]), ("Virtual Assistant", "Acme", "Full-Time"))

        jobicy_feed = b'<rss><channel><item xmlns:j="https://jobicy.com"><id>12</id><title>Bookkeeper</title><link>https://jobicy.com/jobs/12-bookkeeper</link><j:company>Books Co</j:company><j:job_type>Part Time</j:job_type></item></channel></rss>'
        item = jobicy.parse(jobicy_feed)["12"]
        self.assertEqual((item["company"], item["type_of_work"]), ("Books Co", "Part Time"))

        himalayas_feed = b'<rss><channel><item xmlns:h="https://himalayas.app/ns/jobs"><title>Support</title><link>https://himalayas.app/companies/acme/jobs/support</link><h:companyName>Acme</h:companyName><h:locationRestriction>Philippines</h:locationRestriction></item></channel></rss>'
        item = next(iter(himalayas.parse(himalayas_feed).values()))
        self.assertEqual((item["company"], item["location"]), ("Acme", "Philippines"))

    def test_public_card_sources_use_listed_budget_only(self):
        guru_html = '<div class="jobRecord" data-gid="55"><h2 class="jobRecord__title"><a href="/jobs/logo-project/55">Logo project</a></h2><div class="jobRecord__budget"><strong>Fixed Price</strong><strong>$250-$500</strong></div></div>'
        self.assertEqual(guru.parse(guru_html)["55"]["wage_salary"], "$250-$500")

        staff_html = '<a href="/jobs-in-philippines/6ab9dc6f4d8b66006bd79bec/assistant"><div class="text-right"><div>Sep 29, 2026</div></div><h6>Assistant</h6><button>Part Time</button><span class="text-sm">PHP 25,000/mo</span></a>'
        job = virtualstaff.parse(staff_html)["6ab9dc6f4d8b66006bd79bec"]
        self.assertEqual((job["title"], job["wage_salary"]), ("Assistant", "PHP 25,000/mo"))


if __name__ == "__main__":
    unittest.main()
