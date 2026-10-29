"""Deterministic, explainable screening. Scores are heuristics, not probabilities."""
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TAXONOMY = {
    "AI Product": ["product strategy", "user research", "product roadmap", "product operations", "product design", "ux", "product development", "ai solutions"],
    "Founder / Strategy": ["founder", "business operations", "strategic initiatives", "special projects", "cross-functional", "strategy and operations", "chief of staff"],
    "GTM / Growth": ["go-to-market", "gtm", "customer acquisition", "product marketing", "business development", "partnerships", "revenue operations"],
    "Ecosystem / Community": ["community", "developer relations", "devrel", "developer advocate", "ecosystem", "founder programs", "events", "startup programs"],
    "VC / Investment": ["investment", "market research", "due diligence", "deal sourcing", "portfolio operations", "venture", "accelerator", "founder interviews"],
    "AI Adoption": ["ai transformation", "implementation", "solutions consultant", "customer strategy", "strategic accounts", "customer success", "b2b customer"]
}

def now():
    return datetime.now(timezone.utc).isoformat()

def date(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d if d.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

def canonical(url):
    u = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k not in ("source", "ref")]
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), urlencode(sorted(query)), ""))

def job_key(job):
    if job.get("ats_id") and job.get("board"):
        return digest([job.get("source"), job["board"], str(job["ats_id"])])
    return digest(canonical(job["official_url"]))

def freshness(job, at=None):
    at = at or datetime.now(timezone.utc)
    candidates = []
    for field in ("original_posted_at", "last_hiring_signal_at"):
        d = date(job.get(field))
        if d and d <= at and job.get(field + "_verified", False):
            candidates.append(((at-d).total_seconds()/3600, field))
    if not candidates:
        return {"priority": "Unknown", "basis": "No verified publication or hiring signal", "score": 0}
    hours, basis = min(candidates)
    priority, score = next(((p, s) for limit, p, s in [(6,"P0",100),(24,"P1",80),(48,"P2",60),(168,"P3",30)] if hours < limit), ("Older", 0))
    return {"priority": priority, "basis": basis, "age_hours": round(hours, 2), "score": score}

def verification(job, at=None):
    at = at or datetime.now(timezone.utc)
    evidence = job.get("evidence", [])
    recent = [e for e in evidence if e.get("url") and date(e.get("at")) and 0 <= (at-date(e["at"])).total_seconds() <= 86400]
    official = [e for e in recent if e.get("kind") in ("official_open", "closed", "broken")]
    latest = max(official, key=lambda e: date(e["at"]), default=None)
    if any(e.get("kind") == "contradiction" for e in recent) or (latest and latest["kind"] in ("closed", "broken")):
        return "Likely Stale"
    if latest and latest["kind"] == "official_open":
        return "Verified Active"
    if any(e.get("kind") == "hiring_confirmation" for e in recent):
        return "Likely Active"
    d = date(job.get("original_posted_at"))
    return "Likely Stale" if d and (at-d).days > 30 else "Unverified"

def match(job, profile):
    # Responsibilities only: titles never add points. Exact evidence stays visible.
    text = re.sub("<[^>]+>", " ", job.get("description", "")).lower()
    allowed = profile.get("capabilities", [])
    hits = {family: [term for term in terms if term in text and term in allowed] for family, terms in TAXONOMY.items()}
    family = max(hits, key=lambda key: len(hits[key]))
    terms = sorted(set(t for values in hits.values() for t in values))
    return {"role_family": family if terms else "Unclassified", "matched_capabilities": terms, "score": min(100, len(terms)*20)}

def constraints(job, profile):
    reasons = []
    targets = profile.get("targets", {})
    for field, target in [("location","locations"),("seniority","seniority"),("employment_type","employment_types")]:
        if not job.get(field) or job[field] not in targets.get(target, []):
            reasons.append(f"Review {field}: {job.get(field, 'unknown')}")
    if job.get("company", "").casefold() in [s.casefold() for s in targets.get("excluded_companies", [])]:
        reasons.append("Excluded company")
    if any(term.casefold() in job.get("title", "").casefold() for term in targets.get("excluded_roles", [])):
        reasons.append("Excluded role")
    auth = profile.get("work_authorization", {})
    if auth.get("eligible") is not True or auth.get("country") != job.get("country"):
        reasons.append("Work authorization eligibility requires review")
    for key in ("requires_sponsorship_now", "requires_sponsorship_in_future"):
        if not isinstance(auth.get(key), bool):
            reasons.append(f"Unknown {key}")
        elif auth[key] and job.get("sponsorship_available") is not True:
            reasons.append("Sponsorship availability requires review")
    return reasons

def rank(job, profile, at=None):
    fit, fresh, active = match(job, profile), freshness(job, at), verification(job, at)
    components = {"capability": fit["score"], "freshness": fresh["score"], "hiring": {"Verified Active":100,"Likely Active":60,"Unverified":0,"Likely Stale":0}[active], "company": 100 if job.get("company") in profile.get("preferred_companies", []) else 0, "network": 100 if job.get("introduction_evidence_url") else 0}
    reasons = constraints(job, profile)
    score = sum(components[k]*w for k,w in zip(components, [.30,.25,.20,.15,.10]))
    return {**fit, **fresh, "verification_status": active, "components": components, "rank_score": round(score,1), "constraint_blockers": reasons, "eligible": not reasons, "deprioritized": fresh["priority"] in ("Older","Unknown") or (fresh["priority"] == "P3" and fit["score"] < 80)}
