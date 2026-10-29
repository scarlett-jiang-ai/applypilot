"""Optional real Chromium test using route interception; no external requests."""
import importlib.util
import os
import unittest
from applypilot.browser import BrowserForm, run_application
import test_workflow

FORM = '''<!doctype html><h1>Fictional Labs</h1><h2>Strategic Programs Associate</h2>
<form onsubmit="event.preventDefault();document.querySelector('#confirmation').hidden=false">
<label>Full name<input type="text" required></label>
<label>Resume<input type="file" required onchange="document.querySelector('#upload-ack').textContent=this.files[0].name"></label>
<p id="upload-ack"></p><button>Submit application</button></form>
<p id="confirmation" hidden>Application submitted. Thank you for applying.</p>'''

@unittest.skipUnless(importlib.util.find_spec("playwright") and os.environ.get("APPLYPILOT_BROWSER_TESTS") == "1", "Set APPLYPILOT_BROWSER_TESTS=1 and install Chromium for local browser tests")
class BrowserTests(unittest.TestCase):
    setUp = test_workflow.WorkflowTests.setUp
    run_form = test_workflow.WorkflowTests.run_form

    def run_html(self, html):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.route("**/*",lambda route: route.fulfill(status=200,content_type="text/html",body=html))
                return self.run_form(BrowserForm(context.new_page(),self.manifest))
            finally:
                browser.close()

    def test_browser_captcha_handoff(self):
        self.assertEqual(self.run_html(FORM+'<p>Verify you are human: CAPTCHA</p>')["status"],"Needs user")

    def test_browser_login_handoff(self):
        self.assertEqual(self.run_html(FORM+'<input type="password">')["status"],"Needs user")

    def test_browser_submit_without_confirmation(self):
        html = FORM.replace("document.querySelector('#confirmation').hidden=false", "document.querySelector('button').textContent='Sent?'")
        self.assertEqual(self.run_html(html)["status"],"Pending confirmation")

    def test_browser_upload_not_acknowledged(self):
        html = FORM.replace("this.files[0].name", "'Upload failed'")
        self.assertEqual(self.run_html(html)["status"],"Needs user")
    # Reuse fixture setup only; runner below uses an actual browser, never a live ATS.
    def test_browser_confirmed_submission(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.route("**/*",lambda route: route.fulfill(status=200,content_type="text/html",body=FORM))
                page = context.new_page()
                form = BrowserForm(page,self.manifest)
                result = self.run_form(form)
                self.assertEqual(result["status"],"Submitted",result)
            finally: browser.close()

    def test_browser_unknown_field_blocks(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.route("**/*",lambda route: route.fulfill(status=200,content_type="text/html",body=FORM.replace("</form>",'<label>Future sponsorship<select><option>Yes</option></select></label></form>')))
                result = self.run_form(BrowserForm(context.new_page(),self.manifest))
                self.assertEqual(result["status"],"Needs user")
            finally: browser.close()
