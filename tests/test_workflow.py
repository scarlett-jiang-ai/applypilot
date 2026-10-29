import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from applypilot.core import freshness, match, rank, now, digest, verification
from applypilot.store import Store
from applypilot.policy import gate, answer, Pause, policy_hash
from applypilot.discovery import discover, cycle, hiring_signal
from applypilot.browser import run_application
from applypilot.cli import defaults

def fixture(root):
    pdf = Path(root)/"fictional.pdf"
    pdf.write_bytes(b"%PDF-1.4\nFictional test resume only\n%%EOF")
    profile = defaults()["candidate_profile"]
    profile.update(capabilities=["founder","community","partnerships","gtm","events","ecosystem"])
    profile["targets"].update(locations=["San Francisco Bay Area"],seniority=["associate"])
    profile["work_authorization"].update(eligible=True,requires_sponsorship_now=False,requires_sponsorship_in_future=False)
    profile["resumes"] = [{"path":str(pdf),"version":"fictional-1","sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),"role_families":["Ecosystem / Community"]}]
    job = {"company":"Fictional Labs","title":"Strategic Programs Associate","description":"Build ecosystem community, partnerships and events with founder GTM teams.","location":"San Francisco Bay Area","country":"United States","seniority":"associate","employment_type":"full-time","official_url":"https://jobs.example.com/fictional/123","original_posted_at":(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),"original_posted_at_verified":True,"evidence":[{"kind":"official_open","url":"https://jobs.example.com/fictional/123","at":now()}]}
    manifest = {"url":job["official_url"],"company":job["company"],"title":job["title"],"employer_careers_url":"https://fictional.example/careers","employer_link_verified_at":now(),"fields":[{"label":"Full name","kind":"text"},{"label":"Resume","kind":"file"}],"upload_ack_selector":"#upload-ack","submit_label":"Submit application","confirmation_selector":"#confirmation"}
    bank = {"version":"fictional-1","answers":{"Full name":{"value":"Alex Example","approved":True,"kind":"ordinary"}}}
    policy = defaults()["auto_submit_policy"]
    policy.update(auto_submit_enabled=True,approved_role_categories=["Ecosystem / Community"],approved_locations=[job["location"]],approved_seniority=["associate"],approved_resume_versions=["fictional-1"],approved_answer_bank_version=bank["version"],allowed_hosts=["jobs.example.com"],profile_sha256=digest(profile),answer_bank_sha256=digest(bank),approved_manifest_hashes=[digest(manifest)])
    approve(policy)
    return job,profile,bank,policy,manifest

def approve(policy):
    policy["approval"] = {"approved_by":"fictional test user","approved_at":now(),"policy_sha256":policy_hash(policy)}

class FakeForm:
    def __init__(self, blocker=None, confirmed=True):
        self.blocker,self.confirmed,self.clicked = blocker,confirmed,False
    def open(self):
        if self.blocker:
            raise Pause(self.blocker)
    def validate_inventory(self): pass
    def fill(self,field,value): pass
    def upload(self,field,resume): pass
    def validate(self): pass
    def submit(self): self.clicked = True
    def confirmation(self): return {"text":"Application submitted","url":"https://jobs.example.com/fictional/123","observed_at":now()} if self.confirmed else None

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.addCleanup(self.store.db.close)
        self.job,self.profile,self.bank,self.policy,self.manifest = fixture(self.tmp.name)
        self.job["id"] = self.store.upsert(self.job)

    def run_form(self, form=None, **kw):
        return run_application(self.store,self.job,lambda:(self.profile,self.bank,self.policy,self.manifest),form or FakeForm(),dry_run=False,**kw)

    def test_genuine_two_hour_job(self):
        self.assertEqual(freshness(self.job)["priority"],"P0")
        self.assertEqual(verification(self.job),"Verified Active")

    def test_repost_does_not_reset_original(self):
        self.job["original_posted_at"] = (datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
        # Separate vacancy initially seen weeks ago.
        self.job["official_url"] += "old"
        self.store.upsert(self.job)
        self.job["original_posted_at"] = now()
        key = self.store.upsert(self.job)
        saved = next(j for j in self.store.jobs() if j["id"] == key)
        self.assertEqual(freshness(saved)["priority"],"Older")
        self.assertTrue(saved["last_reposted_at"])

    def test_first_seen_is_not_publication(self):
        self.job.pop("original_posted_at")
        self.job["first_seen_at"] = now()
        self.assertEqual(freshness(self.job)["priority"],"Unknown")

    def test_boundaries_and_future_dates(self):
        at = datetime(2026,10,28,tzinfo=timezone.utc)
        for hours,priority in [(0,"P0"),(6,"P1"),(24,"P2"),(48,"P3"),(168,"Older"),(-1,"Unknown")]:
            self.job["original_posted_at"] = (at-timedelta(hours=hours)).isoformat()
            self.assertEqual(freshness(self.job,at)["priority"],priority)

    def test_founder_signal_without_jd(self):
        signal = hiring_signal({"company":"Fictional Labs","person":"Taylor Example","person_role":"Founder","platform":"X","url":"https://example.com/post/1","text":"Hiring our first GTM person"})
        self.assertEqual(signal["verification_status"],"Unverified")
        self.assertIn("outreach",signal["suggested_action"])
        self.assertIsNone(signal["posted_at"])

    def test_unconventional_title_matches_responsibilities(self):
        result = match(self.job,self.profile)
        self.assertEqual(result["role_family"],"Ecosystem / Community")
        self.assertEqual(result["score"],100)
        self.job.update(title="AI Product Manager",description="")
        self.assertEqual(match(self.job,self.profile)["score"],0)

    def test_closed_vacancy_pauses(self):
        self.job["evidence"].append({"kind":"closed","url":self.job["official_url"],"at":now()})
        self.assertEqual(self.run_form()["status"],"Needs user")

    def test_safe_application_and_duplicate(self):
        self.assertEqual(self.run_form()["status"],"Submitted")
        form = FakeForm()
        self.assertEqual(self.run_form(form)["status"],"Blocked")
        self.assertFalse(form.clicked)

    def test_unknown_future_sponsorship_question(self):
        self.manifest["fields"].append({"label":"Will you ever require sponsorship in the future?","kind":"select"})
        self.policy["approved_manifest_hashes"] = [digest(self.manifest)]
        approve(self.policy)
        form = FakeForm()
        self.assertEqual(self.run_form(form)["status"],"Needs user")
        self.assertFalse(form.clicked)

    def test_captcha_and_login(self):
        for blocker in ("CAPTCHA", "Login required"):
            with self.subTest(blocker=blocker):
                self.store.db.execute("DELETE FROM applications")
                self.store.db.commit()
                form = FakeForm(blocker)
                self.assertEqual(self.run_form(form)["status"],"Needs user")
                self.assertFalse(form.clicked)

    def test_click_without_confirmation(self):
        form = FakeForm(confirmed=False)
        self.assertEqual(self.run_form(form)["status"],"Pending confirmation")
        self.assertTrue(form.clicked)
        self.assertEqual(self.run_form()["status"],"Blocked")

    def test_disabled_policy(self):
        self.policy["auto_submit_enabled"] = False
        self.assertEqual(self.run_form()["status"],"Needs user")

    def test_changed_approval_inputs(self):
        for field in ("profile","bank","policy","manifest"):
            with self.subTest(field=field):
                target = getattr(self,field)
                target["tampered"] = True
                self.assertEqual(self.run_form()["status"],"Needs user")
                target.pop("tampered")

    def test_resume_changed(self):
        Path(self.profile["resumes"][0]["path"]).write_bytes(b"%PDF-changed")
        self.assertEqual(self.run_form()["status"],"Needs user")

    def test_revocation_during_form(self):
        outer = self
        class RevokingForm(FakeForm):
            def validate(self): outer.policy["revoked_at"] = now()
        form = RevokingForm()
        self.assertEqual(self.run_form(form)["status"],"Needs user")
        self.assertFalse(form.clicked)

    def test_salary_and_sensitive_questions(self):
        for label in ("Salary expectations", "Background check consent", "References"):
            self.bank["answers"][label] = {"approved":True,"kind":"ordinary","value":"100000"}
            with self.assertRaises(Pause):
                answer({"label":label},self.profile,self.bank,self.policy)

    def test_concurrent_reservation(self):
        other = Store(self.tmp.name)
        self.addCleanup(other.db.close)
        self.assertTrue(self.store.reserve(self.job["id"],{}))
        self.assertFalse(other.reserve(self.job["id"],{}))

    def test_duplicate_across_different_urls(self):
        self.assertEqual(self.run_form()["status"],"Submitted")
        self.job["official_url"] += "-mirror"
        self.job["id"] = self.store.upsert(self.job)
        self.manifest["url"] = self.job["official_url"]
        self.policy["approved_manifest_hashes"] = [digest(self.manifest)]
        approve(self.policy)
        self.assertEqual(self.run_form()["status"],"Blocked")

    def test_reopened_job_uses_latest_evidence(self):
        earlier = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.job["evidence"].insert(0,{"kind":"closed","url":self.job["official_url"],"at":earlier})
        self.assertEqual(verification(self.job),"Verified Active")

    def test_disabled_preflight_visible_in_dashboard(self):
        self.policy["auto_submit_enabled"] = False
        self.run_form()
        path = self.store.dashboard(self.profile)
        self.assertIn("Auto-submit disabled",path.read_text())

    def test_dry_run_never_clicks(self):
        form = FakeForm()
        result = run_application(self.store,self.job,lambda:(self.profile,self.bank,self.policy,self.manifest),form)
        self.assertFalse(form.clicked)
        self.assertEqual(result["status"],"Needs user")

    def test_csv_injection_and_html_escape(self):
        self.job.update(company="=HYPERLINK(1)",title="<script>alert(1)</script>")
        self.store.upsert(self.job)
        path = self.store.dashboard(self.profile)
        self.assertNotIn("<script>",path.read_text())
        self.assertIn("'=HYPERLINK",(path.parent/"job_pool.csv").read_text())

    def test_no_fabricated_confirmation(self):
        self.store.reserve(self.job["id"],{})
        with self.assertRaises(ValueError):
            self.store.finish(self.job["id"],"Submitted",{})

    def test_missing_legal_facts_are_blockers(self):
        self.profile["work_authorization"]["requires_sponsorship_in_future"] = None
        self.assertFalse(rank(self.job,self.profile)["eligible"])

class DiscoveryTests(unittest.TestCase):
    def company(self, source):
        host = {"greenhouse":"boards.greenhouse.io","ashby":"jobs.ashbyhq.com","lever":"jobs.lever.co"}[source]
        return {"company":"Fictional Labs","source":source,"board":"fictional","board_url":f"https://{host}/fictional","careers_url":"https://fictional.example/careers"}

    def test_public_adapters(self):
        for source in ("greenhouse","ashby","lever"):
            company = self.company(source)
            item = {"id":"123","title":"Programs Associate","text":"Programs Associate","absolute_url":company["board_url"]+"/123","applyUrl":company["board_url"]+"/123","location":{"name":"SF"} if source == "greenhouse" else "SF","isListed":True,"publishedAt":now(),"updated_at":now(),"createdAt":1234}
            def reader(url):
                return f'<a href="{company["board_url"]}">Careers</a>' if url == company["careers_url"] else json.dumps([item] if source == "lever" else {"jobs":[item]})
            jobs = discover(company,reader)
            self.assertEqual(len(jobs),1)
            self.assertEqual(bool(jobs[0]["original_posted_at"]),source == "ashby")

    def test_inaccessible_source_is_coverage_limitation(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            try:
                def failure(url): raise ValueError("403 access denied")
                result = cycle(store,{"companies":[self.company("ashby")],"manual_sources":["LinkedIn"]},failure)
                self.assertEqual(result["coverage"][0]["status"],"unavailable")
                self.assertEqual(result["coverage"][1]["status"],"not searched")
            finally: store.db.close()

if __name__ == "__main__":
    unittest.main()
