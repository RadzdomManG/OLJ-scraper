import unittest

from sources.freelancer import fetch as fetch_freelancer_jobs
from sources.remotive import fetch as fetch_remotive_jobs
from sources.wellfound import parse_job_posting


class Response:
    def __init__(self, text="", payload=None):
        self.text = text
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
    def test_freelancer_uses_current_card_and_skips_unrelated_jobs(self):
        html = '''<div class="JobSearchCard-item"><a class="JobSearchCard-primary-heading-link" href="/projects/ai-video/comfyui-flux-film-123">ComfyUI FLUX filmmaker</a><p class="JobSearchCard-primary-description">Create AI video with LoRA.</p></div>
        <div class="JobSearchCard-item"><a class="JobSearchCard-primary-heading-link" href="/projects/data-entry/typing-456">Data entry clerk</a></div>'''
        jobs = fetch_freelancer_jobs(Http(Response(text=html)), ["https://www.freelancer.com/jobs/ai-video/"])
        self.assertEqual(len(jobs), 1)
        job = next(iter(jobs.values()))
        self.assertEqual(job["title"], "ComfyUI FLUX filmmaker")
        self.assertEqual(job["wage_salary"], "")
        self.assertTrue(job["url"].startswith("https://www.freelancer.com/projects/"))

    def test_remotive_uses_only_source_salary_and_posting_date(self):
        payload = {"jobs": [
            {"id": 42, "title": "AI Video Creator", "url": "https://remotive.com/remote-jobs/ai-video-42", "description": "<p>Build films in ComfyUI.</p>", "publication_date": "2026-09-28T10:00:00", "salary": "$50k-$70k", "job_type": "contract"},
            {"id": 43, "title": "Customer Support", "url": "https://remotive.com/remote-jobs/support-43", "description": "<p>Answer email.</p>"},
        ]}
        jobs = fetch_remotive_jobs(Http(Response(payload=payload)))
        self.assertEqual(list(jobs), ["42"])
        self.assertEqual(jobs["42"]["wage_salary"], "$50k-$70k")
        self.assertEqual(jobs["42"]["posted_at"], "2026-09-28T10:00:00")

    def test_wellfound_reads_source_jobposting_fields(self):
        html = '''<script type="application/ld+json">{"@type":"JobPosting","title":"AI Video Filmmaker","identifier":{"value":"77"},"description":"<p>Build ComfyUI films</p>","datePosted":"2026-09-29T01:00:00Z","employmentType":"CONTRACT","hiringOrganization":{"name":"Film Studio"},"baseSalary":{"currency":"USD","value":{"minValue":50000,"maxValue":70000,"unitText":"YEAR"}},"jobLocationType":"TELECOMMUTE"}</script>'''
        job_id, job = parse_job_posting(html, "https://wellfound.com/jobs/77-ai-video-filmmaker")
        self.assertEqual(job_id, "77")
        self.assertEqual(job["company"], "Film Studio")
        self.assertEqual(job["wage_salary"], "USD 50000–70000 / year")
        self.assertTrue(job["remote"])


if __name__ == "__main__":
    unittest.main()
