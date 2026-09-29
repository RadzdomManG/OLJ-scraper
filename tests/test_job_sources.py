import unittest

from sources.freelancer import fetch as fetch_freelancer_jobs
from sources.remotive import fetch as fetch_remotive_jobs
from sources.wellfound import parse_job_posting


class Response:
    def __init__(self, text="", payload=None):
        self.text = text
        self.content = text.encode('utf-8')
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Http:
    def __init__(self, response):
        self.response = response

    def get(self, url, timeout):
        return self.response


class JobSourceTest(unittest.TestCase):
    def test_freelancer_uses_current_card_and_keeps_all_jobs(self):
        html = '''<div class="JobSearchCard-item"><a class="JobSearchCard-primary-heading-link" href="/projects/ai-video/comfyui-flux-film-123">ComfyUI FLUX filmmaker</a><p class="JobSearchCard-primary-description">Create AI video with LoRA.</p></div>
        <div class="JobSearchCard-item"><a class="JobSearchCard-primary-heading-link" href="/projects/data-entry/typing-456">Data entry clerk</a></div>'''
        jobs = fetch_freelancer_jobs(Http(Response(text=html)), ["https://www.freelancer.com/jobs/ai-video/"])
        self.assertEqual(len(jobs), 2)
        job = next(job for job in jobs.values() if "ComfyUI" in job["title"])
        self.assertEqual(job["title"], "ComfyUI FLUX filmmaker")
        self.assertEqual(job["wage_salary"], "")
        self.assertTrue(job["url"].startswith("https://www.freelancer.com/projects/"))

    def test_remotive_rss_keeps_all_jobs_and_source_fields(self):
        from sources.remotive import parse_feed
        feed = b'''<rss><channel><item><jobId>42</jobId><title>AI Video Creator</title><link>https://remotive.com/remote-jobs/ai-video-42</link><description>&lt;p&gt;Build films in ComfyUI.&lt;/p&gt;</description><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate><salary>$50k-$70k</salary><type>contract</type></item><item><jobId>43</jobId><title>Customer Support</title><link>https://remotive.com/remote-jobs/support-43</link></item></channel></rss>'''
        jobs = parse_feed(feed)
        self.assertEqual(set(jobs), {"42", "43"})
        self.assertEqual(jobs["42"]["wage_salary"], "$50k-$70k")
        self.assertTrue(jobs["42"]["posted_at"].startswith("2026-09-28T10:00:00"))

    def test_wellfound_reads_source_jobposting_fields(self):
        html = '''<script type="application/ld+json">{"@type":"JobPosting","title":"AI Video Filmmaker","identifier":{"value":"77"},"description":"<p>Build ComfyUI films</p>","datePosted":"2026-09-29T01:00:00Z","employmentType":"CONTRACT","hiringOrganization":{"name":"Film Studio"},"baseSalary":{"currency":"USD","value":{"minValue":50000,"maxValue":70000,"unitText":"YEAR"}},"jobLocationType":"TELECOMMUTE"}</script>'''
        job_id, job = parse_job_posting(html, "https://wellfound.com/jobs/77-ai-video-filmmaker")
        self.assertEqual(job_id, "77")
        self.assertEqual(job["company"], "Film Studio")
        self.assertEqual(job["wage_salary"], "USD 50000–70000 / year")
        self.assertTrue(job["remote"])


if __name__ == "__main__":
    unittest.main()
