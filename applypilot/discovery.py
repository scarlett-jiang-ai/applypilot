"""Public read-only ATS feeds. Missing source access is recorded, never invented."""
import json
import re
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import quote, urlsplit, urljoin
from html.parser import HTMLParser
from .core import now, date, canonical, freshness, match

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect needs review: " + newurl)

def public_url(url):
    import ipaddress
    import socket
    u = urlsplit(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None,443):
        raise ValueError("Only public HTTPS URLs allowed")
    for entry in socket.getaddrinfo(u.hostname,443):
        if not ipaddress.ip_address(entry[4][0]).is_global:
            raise ValueError("Private network address blocked")
    return url

def fetch(url):
    public_url(url)
    request = Request(url,headers={"User-Agent":"ApplyPilot/2.0 (public job discovery)","Accept":"application/json,text/html"})
    with build_opener(NoRedirect).open(request,timeout=20) as response:
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError("Response size limit exceeded")
        return data.decode("utf-8")

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links += [v for k,v in attrs if k == "href" and v]

def employer_linked(company, reader=fetch):
    """Require a public employer careers page linking to this specific board."""
    careers, board_url = company["careers_url"], company["board_url"]
    expected = {"greenhouse":("boards.greenhouse.io","job-boards.greenhouse.io"),"ashby":("jobs.ashbyhq.com",),"lever":("jobs.lever.co",)}
    u = urlsplit(board_url)
    if u.scheme != "https" or u.hostname not in expected.get(company["source"], ()) or u.path.strip("/") != company["board"]:
        raise ValueError("Board URL does not match source and board")
    parser = Links()
    parser.feed(reader(careers))
    if not any(canonical(urljoin(careers, link)) == canonical(board_url) or canonical(urljoin(careers, link)).startswith(canonical(board_url)+"/") for link in parser.links):
        raise ValueError("Employer-to-ATS link not verified; inspect careers page manually")

def discover(company, reader=fetch):
    employer_linked(company,reader)
    source, board = company["source"], company["board"]
    slug = quote(board,safe="")
    endpoints = {"greenhouse":f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", "ashby":f"https://api.ashbyhq.com/posting-api/job-board/{slug}", "lever":f"https://api.lever.co/v0/postings/{slug}?mode=json"}
    payload = json.loads(reader(endpoints[source]))
    entries = payload if source == "lever" else payload["jobs"]
    if not isinstance(entries,list):
        raise ValueError("Invalid jobs response")
    jobs = []
    for entry in entries:
        if source == "ashby" and entry.get("isListed") is not True:
            continue
        if source == "greenhouse":
            title, url, description, location = entry["title"], entry["absolute_url"], entry.get("content", ""), entry.get("location", {}).get("name")
        elif source == "ashby":
            title, url, description, location = entry["title"], entry["applyUrl"], entry.get("descriptionPlain", ""), entry.get("location")
        else:
            title, url, description, location = entry["text"], entry["applyUrl"], entry.get("descriptionPlain", "") + " " + " ".join(x.get("content", "") for x in entry.get("lists", [])), entry.get("categories", {}).get("location")
        # Greenhouse updated_at and Lever createdAt are NOT original publication dates.
        published = entry.get("publishedAt") if source == "ashby" else None
        stamp = now()
        jobs.append({"company":company["company"],"title":title,"source":source,"board":board,"ats_id":str(entry.get("id",url)),"official_url":url,"description":description,"location":location,"seniority":None,"country":None,"employment_type": {"FullTime":"full-time","PartTime":"part-time","Contract":"contract","Intern":"internship"}.get(entry.get("employmentType")),"original_posted_at":published,"original_posted_at_verified":bool(date(published)),"first_seen_at":stamp,"last_reposted_at":None,"last_hiring_signal_at":None,"verified_at":stamp,"timestamp_source":"ATS publishedAt" if published else "unknown","timestamp_confidence":"medium" if published else "unknown","evidence":[{"kind":"official_open","url":endpoints[source],"at":stamp},{"kind":"employer_link","url":company["careers_url"],"at":stamp}],"next_action":"Review constraints and official form"})
    return jobs

def cycle(store, watchlist, reader=fetch, profile=None):
    summary = {"new":0,"coverage":[],"notifications":[]}
    for company in watchlist.get("companies", []):
        try:
            jobs = discover(company,reader)
            before = {j["id"] for j in store.jobs()}
            observed = set()
            for job in jobs:
                key = store.upsert(job)
                observed.add(key)
                if key not in before:
                    summary["new"] += 1
                    if freshness(job)["priority"] in ("P0","P1") and profile and match(job,profile)["score"] >= 60:
                        summary["notifications"].append({"company":job["company"],"title":job["title"],"url":job["official_url"]})
            # Absence is evidence only after a complete successful board response.
            for old in store.jobs():
                if old.get("board") == company["board"] and old.get("source") == company["source"] and old["id"] not in observed:
                    old.setdefault("evidence", []).append({"kind":"closed","url":company["board_url"],"at":now()})
                    store.upsert(old)
            coverage = {"source":company["source"],"company":company["company"],"status":"searched","count":len(jobs)}
        except Exception as exc:
            coverage = {"source":company.get("source"),"company":company.get("company"),"status":"unavailable","reason":str(exc)}
        summary["coverage"].append(coverage)
        store.event("coverage",coverage)
        if reader is fetch:
            time.sleep(1)
    for source in watchlist.get("manual_sources", []):
        coverage = {"source":source,"status":"not searched","reason":"Requires authorized public search/browser or manual evidence import"}
        summary["coverage"].append(coverage)
        store.event("coverage",coverage)
    if summary["notifications"]:
        store.event("opportunity_notification", {"opportunities":summary["notifications"]})
    return summary

def hiring_signal(record):
    required = ("company", "person", "person_role", "platform", "url", "text")
    if any(not record.get(k) for k in required):
        raise ValueError("Signal needs company, person, person_role, platform, URL, original text")
    record = dict(record)
    record["verification_status"] = "Unverified"
    record["first_seen_at"] = now()
    record["posted_at"] = record.get("posted_at") if date(record.get("posted_at")) else None
    record["suggested_action"] = "Verify official application" if record.get("official_url") else "Investigate or draft founder outreach; never auto-message"
    return record
