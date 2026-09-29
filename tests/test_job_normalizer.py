import unittest

from job_normalizer import readable_text, salary_parts, source_posted


class JobNormalizerTest(unittest.TestCase):
    def test_repairs_utf8_currency_decoded_as_latin1(self):
        broken = bytes([0xE2, 0x82, 0xB9]).decode('latin1') + '100-400 INR'
        self.assertEqual(readable_text(broken), '₹100-400 INR')
        self.assertEqual(salary_parts(broken)['salary_currency'], 'INR')

    def test_relative_label_does_not_become_exact_posted_time(self):
        self.assertIsNone(source_posted('1 minute ago', 'freelancer'))
        self.assertEqual(source_posted('2026-09-29T11:34:55+00:00', 'jobicy'), '2026-09-29T11:34:55+00:00')


if __name__ == '__main__':
    unittest.main()
