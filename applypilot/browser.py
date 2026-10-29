"""Conservative Playwright adapter for reviewed, single-page official ATS forms.

Custom widgets, multi-page forms and account flows are handed to the user. The
same runner works with reviewed Greenhouse, Ashby, Lever and employer manifests.
Workday requires a site-specific reviewed manifest and no authentication barrier.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit
from .core import canonical, now
from .policy import Pause, gate, answer, read

BLOCKERS = re.compile(r"captcha|verify (?:you are|you're) human|cloudflare|sign in to apply|log in to apply|create (?:an? )?account|two.factor|verification code|payment required|credit card|social security|passport number|background check|non.compete|references required", re.I)
CONFIRMATION = re.compile(r"application (?:has been )?(?:submitted|received|sent)|thank you for applying", re.I)

class BrowserForm:
    def __init__(self, page, manifest):
        self.page, self.manifest = page, manifest
        self.dialog_seen = False
        self.entered = []
        self.attached = None
        page.on("dialog", self._dialog)

    def _dialog(self, dialog):
        self.dialog_seen = True
        dialog.dismiss()

    def open(self):
        self.page.goto(self.manifest["url"], wait_until="domcontentloaded",timeout=30000)
        self.check()
        if canonical(self.page.url) != canonical(self.manifest["url"]):
            raise Pause("Unexpected redirect: review official destination")
        text = self.page.locator("body").inner_text()
        if self.manifest["company"].casefold() not in text.casefold() or self.manifest["title"].casefold() not in text.casefold():
            raise Pause("Visible employer/job identity could not be verified")
        if CONFIRMATION.search(text):
            raise Pause("Pre-existing confirmation: reconcile application history")

    def check(self):
        text = self.page.locator("body").inner_text()
        if self.dialog_seen or BLOCKERS.search(text):
            raise Pause("Authentication, sensitive question, challenge, or permission dialog requires user")
        if self.page.locator('input[type=password], iframe[src*="captcha"], iframe[src*="challenges.cloudflare"], [data-sitekey]').count():
            raise Pause("Login or anti-bot control present; user assistance required")
        if urlsplit(self.page.url).netloc != urlsplit(self.manifest["url"]).netloc:
            raise Pause("Application navigated outside approved host")

    def fields(self):
        fields = []
        for control in self.page.locator("input,select,textarea,[contenteditable=true],[role=combobox],[role=checkbox],[role=radio]").all():
            if not control.is_visible() or control.is_disabled():
                continue
            kind = control.get_attribute("type") or control.evaluate("e=>e.tagName.toLowerCase()")
            if kind in ("submit","button","reset","hidden"):
                continue
            label = control.evaluate("e => e.labels && e.labels.length ? Array.from(e.labels).map(x=>x.innerText.trim()).join(' ') : (e.getAttribute('aria-label') || '')")
            fields.append({"label":label,"kind":kind})
        return fields

    def validate_inventory(self):
        found = self.fields()
        expected = [{"label":f["label"],"kind":f["kind"]} for f in self.manifest["fields"]]
        if sorted(found,key=lambda x:(x["label"],x["kind"])) != sorted(expected,key=lambda x:(x["label"],x["kind"])):
            raise Pause("Form fields changed or include unreviewed controls; review manifest")

    def fill(self, field, value):
        control = self.page.get_by_label(field["label"], exact=True)
        if control.count() != 1:
            raise Pause("Ambiguous form control: " + field["label"])
        kind = field["kind"]
        if kind == "select":
            control.select_option(label=str(value))
            if control.locator("option:checked").inner_text().strip() != str(value):
                raise Pause("Dropdown value did not persist")
        elif kind == "checkbox":
            if not isinstance(value,bool):
                raise Pause("Checkbox answer must be boolean")
            control.set_checked(value)
            if control.is_checked() != value:
                raise Pause("Checkbox value did not persist")
        elif kind in ("text","email","tel","url","number","textarea","input","date"):
            control.fill(str(value))
            if control.input_value() != str(value):
                raise Pause("Field value did not persist")
        else:
            raise Pause("Custom widget needs user assistance: " + kind)
        self.entered.append((field,value))
        self.check()

    def upload(self, field, resume):
        control = self.page.get_by_label(field["label"],exact=True)
        control.set_input_files(resume["path"])
        files = control.evaluate("e=>Array.from(e.files||[]).map(f=>({name:f.name,size:f.size}))")
        path = Path(resume["path"])
        if files != [{"name":path.name,"size":path.stat().st_size}]:
            raise Pause("Resume attachment mismatch")
        # Site-specific rendered acknowledgement must also show exact filename.
        acknowledged = self.page.locator(self.manifest["upload_ack_selector"])
        acknowledged.wait_for(state="visible",timeout=10000)
        if path.name not in acknowledged.inner_text():
            raise Pause("Site has not acknowledged the selected resume")
        self.attached = (field,resume)
        self.check()

    def validate(self):
        self.check()
        self.validate_inventory()
        for field,value in self.entered:
            control = self.page.get_by_label(field["label"],exact=True)
            actual = control.is_checked() if field["kind"] == "checkbox" else control.locator("option:checked").inner_text().strip() if field["kind"] == "select" else control.input_value()
            if actual != (value if isinstance(value,bool) else str(value)):
                raise Pause("Previously entered answer changed: " + field["label"])
        if not self.attached:
            raise Pause("No verified resume attachment")
        field,resume = self.attached
        control = self.page.get_by_label(field["label"],exact=True)
        path = Path(resume["path"])
        if control.evaluate("e=>Array.from(e.files||[]).map(f=>({name:f.name,size:f.size}))") != [{"name":path.name,"size":path.stat().st_size}] or path.name not in self.page.locator(self.manifest["upload_ack_selector"]).inner_text():
            raise Pause("Resume attachment changed before submission")
        invalid = self.page.locator("input:invalid,select:invalid,textarea:invalid,[aria-invalid=true]")
        if any(control.is_visible() for control in invalid.all()):
            raise Pause("Required fields invalid or incomplete")
        if CONFIRMATION.search(self.page.locator("body").inner_text()):
            raise Pause("Unexpected pre-submit confirmation; reconcile")

    def submit(self):
        button = self.page.get_by_role("button",name=self.manifest["submit_label"],exact=True)
        if button.count() != 1:
            raise Pause("Submit button ambiguous")
        button.click(timeout=15000)

    def confirmation(self):
        try:
            element = self.page.locator(self.manifest["confirmation_selector"])
            element.wait_for(state="visible",timeout=15000)
            text = element.inner_text()
            if CONFIRMATION.search(text) and urlsplit(self.page.url).netloc == urlsplit(self.manifest["url"]).netloc:
                return {"text":text,"url":self.page.url,"observed_at":now(),"job_url":self.manifest["url"]}
        except Exception:
            pass
        return None

def run_application(store, job, config_loader, form, scope="isolated:no-account", dry_run=True):
    """Reserve once, recheck all approval content just before submit; never retry clicks."""
    profile, bank, policy, manifest = config_loader()
    try:
        resume = gate(job,profile,bank,policy,manifest,scope)
    except Pause as exc:
        store.event("needs_user",{"job_id":job["id"],"reason":str(exc)})
        return {"status":"Needs user","blocker":str(exc)}
    details = {"company":job["company"],"title":job["title"],"location":job.get("location"),"official_url":job["official_url"],"resume_version":resume["version"],"resume_sha256":resume["sha256"],"answer_bank_version":bank["version"],"dry_run":dry_run}
    if not store.reserve(job["id"],details):
        return {"status":"Blocked","blocker":"Duplicate or previous attempt unresolved; do not resubmit"}
    clicked = False
    try:
        form.open()
        form.validate_inventory()
        uploads = [f for f in manifest["fields"] if f["kind"] == "file"]
        if len(uploads) != 1:
            raise Pause("Exactly one reviewed resume upload required")
        # Resolve every question before entering personal data.
        answers = [(f,answer(f,profile,bank,policy)) for f in manifest["fields"] if f["kind"] != "file" and f.get("skip") is not True]
        for field,value in answers:
            form.fill(field,value)
        form.upload(uploads[0],resume)
        form.validate()
        latest = config_loader()
        gate(job,*latest,scope)
        if latest != (profile,bank,policy,manifest):
            raise Pause("Configuration changed during application")
        if dry_run:
            raise Pause("Dry run completed; no submit click. Review and reconcile before a live run")
        clicked = True  # Persisted reservation survives process crash or ambiguous click.
        form.submit()
        evidence = form.confirmation()
        if not evidence:
            status, data = "Pending confirmation", {"blocker":"Submit attempted without reliable confirmation; inspect manually, never auto-retry"}
        else:
            status, data = "Submitted", {"confirmation_evidence":evidence}
    except Pause as exc:
        status, data = ("Pending confirmation" if clicked else "Needs user"), {"blocker":str(exc)}
    except Exception as exc:
        status, data = ("Pending confirmation" if clicked else "Blocked"), {"blocker":f"{type(exc).__name__}: {exc}"}
    store.finish(job["id"],status,data)
    return {"status":status,**data}

def launch(store, job, root, manifest_path, live=False):
    from playwright.sync_api import sync_playwright
    root = Path(root)
    def loader():
        return (read(root/"candidate_profile.json"),read(root/"answer_bank.json"),read(root/"auto_submit_policy.json"),read(manifest_path))
    manifest = read(manifest_path)
    # Fail before browser launch, and before transmitting anything, if not approved.
    gate(job,*loader(),"isolated:no-account")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(permissions=[], accept_downloads=False)
        page = context.new_page()
        page.set_default_timeout(10000)
        # No stored sessions, cookies, credentials, permission grants or code retrieval.
        result = run_application(store,job,loader,BrowserForm(page,manifest),dry_run=not live)
        browser.close()
        return result
