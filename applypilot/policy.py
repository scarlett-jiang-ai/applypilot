"""Fail-closed approval and existing-resume routing."""
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from .core import digest, date, rank, canonical

class Pause(Exception):
    pass

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def policy_hash(policy):
    return digest({k:v for k,v in policy.items() if k not in ("approval", "auto_submit_enabled", "revoked_at")})

def resume_for(job, profile):
    family = rank(job,profile)["role_family"]
    for resume in profile.get("resumes", []):
        if family in resume.get("role_families", []):
            path = Path(resume["path"]).expanduser()
            if not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".pdf":
                raise Pause("Provide the approved existing PDF at an absolute accessible path")
            raw = path.read_bytes()
            if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != resume.get("sha256"):
                raise Pause("Resume content differs from approved SHA-256")
            return resume
    raise Pause("No approved existing resume matches responsibilities")

def gate(job, profile, bank, policy, manifest, browser_scope):
    approval = policy.get("approval", {})
    timestamp = date(approval.get("approved_at"))
    if policy.get("auto_submit_enabled") is not True or policy.get("revoked_at"):
        raise Pause("Auto-submit disabled or revoked; completed configuration needs explicit user approval")
    if not timestamp or timestamp > datetime.now(timezone.utc) or not approval.get("approved_by") or approval.get("policy_sha256") != policy_hash(policy):
        raise Pause("Missing or invalid approval for this exact policy")
    for name, config in (("profile",profile),("answer_bank",bank),("manifest",manifest)):
        expected = policy.get(name + "_sha256") if name != "manifest" else policy.get("approved_manifest_hashes", [])
        if (digest(config) not in expected) if isinstance(expected,list) else (digest(config) != expected):
            raise Pause(f"Unapproved {name} content")
    if bank.get("version") != policy.get("approved_answer_bank_version") or not bank.get("version"):
        raise Pause("Unapproved Answer Bank version")
    result = rank(job, profile)
    if result["constraint_blockers"]:
        raise Pause("; ".join(result["constraint_blockers"]))
    if result["verification_status"] != "Verified Active":
        raise Pause("Fresh official active-hiring evidence required")
    for value, key in ((result["role_family"],"approved_role_categories"),(job.get("location"),"approved_locations"),(job.get("seniority"),"approved_seniority"),(job.get("employment_type"),"approved_employment_types")):
        if value not in policy.get(key, []):
            raise Pause(f"Outside policy: {key}")
    if job["company"].casefold() in [x.casefold() for x in policy.get("excluded_companies", [])]:
        raise Pause("Excluded employer")
    if browser_scope not in policy.get("permitted_browser_account_scope", []):
        raise Pause("Browser/account scope not approved")
    url = urlsplit(job["official_url"])
    if url.scheme != "https" or url.hostname not in policy.get("allowed_hosts", []) or url.username or url.password:
        raise Pause("Unapproved official host")
    if any(word in (url.hostname or "") for word in ("linkedin", "simplify")):
        raise Pause("Only employer official applications are supported")
    if canonical(manifest.get("url", "")) != canonical(job["official_url"]) or manifest.get("company") != job["company"] or manifest.get("title") != job["title"]:
        raise Pause("Manifest employer/job mismatch")
    if not manifest.get("employer_link_verified_at") or not date(manifest["employer_link_verified_at"]) or not manifest.get("employer_careers_url"):
        raise Pause("Record verified employer-to-application link in reviewed manifest")
    resume = resume_for(job,profile)
    if resume["version"] not in policy.get("approved_resume_versions", []):
        raise Pause("Unapproved resume version")
    return resume

def answer(question, profile, bank, policy):
    label = question["label"]
    if re.search(r"background check|reference|non.compete|passport|social security|credit card|payment",label,re.I):
        raise Pause("Sensitive question requires user review: " + label)
    # Exact full question text is the key. No fuzzy sponsorship matching.
    entry = bank.get("answers", {}).get(label)
    if not entry or entry.get("approved") is not True or "value" not in entry:
        raise Pause("Exact approved answer needed: " + label)
    if entry.get("kind") in ("background_check","reference","non_compete","identity_document","payment"):
        raise Pause("Sensitive question requires user review: " + label)
    if entry.get("kind") == "salary" or re.search(r"salary|compensation|pay expectation",label,re.I):
        salary = policy.get("salary", {})
        if entry.get("currency") != salary.get("currency") or entry.get("period") != salary.get("period"):
            raise Pause("Salary currency/period requires review")
        try:
            valid = salary["min"] <= float(entry["value"]) <= salary["max"]
        except (KeyError,ValueError,TypeError):
            valid = False
        if not valid:
            raise Pause("Salary outside approved range")
    return entry["value"]
