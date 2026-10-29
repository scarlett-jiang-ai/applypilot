"""SQLite transactions reserve submissions before any external side effect."""
import csv
import html
import json
import sqlite3
from pathlib import Path
from .core import now, job_key, canonical, rank, digest

class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite", timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, url TEXT UNIQUE, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS applications (job_id TEXT PRIMARY KEY, status TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT, kind TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS signals (url TEXT PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS networking (url TEXT PRIMARY KEY, data TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS application_identity ON applications(json_extract(data, '$.duplicate_identity'));
        ''')

    def event(self, kind, data):
        with self.db:
            self.db.execute("INSERT INTO events(at,kind,data) VALUES(?,?,?)", (now(),kind,json.dumps(data)))

    def upsert(self, job):
        job = dict(job)
        key, url = job_key(job), canonical(job["official_url"])
        row = self.db.execute("SELECT id,data FROM jobs WHERE id=? OR url=?", (key,url)).fetchone()
        if row:
            key, old = row[0], json.loads(row[1])
            job = {**old, **job}
            job["first_seen_at"] = old["first_seen_at"]
            if old.get("original_posted_at"):
                if job.get("original_posted_at") and job["original_posted_at"] != old["original_posted_at"]:
                    job["last_reposted_at"] = job["original_posted_at"]
                for field in ("original_posted_at", "original_posted_at_verified", "timestamp_source", "timestamp_confidence"):
                    job[field] = old.get(field)
            job["evidence"] = old.get("evidence", []) + [e for e in job.get("evidence", []) if e not in old.get("evidence", [])]
            self.event("duplicate_discovery", {"job_id":key})
        else:
            job["first_seen_at"] = now()
        job["id"] = key
        with self.db:
            self.db.execute("INSERT INTO jobs VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (key,url,json.dumps(job)))
        return key

    def jobs(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM jobs")]

    def record(self, table, record):
        if table not in ("signals", "networking"):
            raise ValueError("Unknown pipeline")
        with self.db:
            self.db.execute(f"INSERT INTO {table} VALUES(?,?) ON CONFLICT(url) DO UPDATE SET data=excluded.data", (record["url"],json.dumps(record)))

    def reserve(self, key, data):
        data = dict(data)
        data["duplicate_identity"] = digest([" ".join(str(data.get(k) or "").casefold().split()) for k in ("company","title","location")]) if data.get("company") and data.get("title") else key
        try:
            with self.db:
                self.db.execute("INSERT INTO applications VALUES(?,?,?)", (key,"In progress",json.dumps({**data,"attempted_at":now()})))
            return True
        except sqlite3.IntegrityError:
            return False

    def finish(self, key, status, data):
        if status not in ("Submitted", "Needs user", "Blocked", "Pending confirmation"):
            raise ValueError("Invalid outcome")
        if status == "Submitted" and not data.get("confirmation_evidence"):
            raise ValueError("Confirmation required")
        with self.db:
            previous = self.db.execute("SELECT status,data FROM applications WHERE job_id=?", (key,)).fetchone()
            if not previous or previous[0] != "In progress":
                raise ValueError("Application is not reserved or is already terminal")
            data = {**json.loads(previous[1]), **data, "updated_at":now()}
            if status == "Submitted":
                data["submitted_at"] = now()
            self.db.execute("UPDATE applications SET status=?,data=? WHERE job_id=?", (status,json.dumps(data),key))

    def dashboard(self, profile):
        jobs = [{**j, **rank(j,profile)} for j in self.jobs()]
        jobs.sort(key=lambda j: (not j["eligible"], j["deprioritized"], -j["rank_score"]))
        apps = [{"job_id":r[0],"status":r[1],**json.loads(r[2])} for r in self.db.execute("SELECT * FROM applications")]
        events = [{"at":r[0],"kind":r[1],**json.loads(r[2])} for r in self.db.execute("SELECT at,kind,data FROM events")]
        by_id = {a["job_id"]:a for a in apps}
        preflight = {e["job_id"]:e for e in events if e["kind"] == "needs_user" and e.get("job_id") not in by_id}
        for job in jobs:
            attempt = by_id.get(job["id"], {})
            job["application_status"] = attempt.get("status", "Needs user" if job["constraint_blockers"] or job["id"] in preflight else "Pending")
            job["selected_resume"] = attempt.get("resume_version", "")
            job["next_action"] = attempt.get("blocker") or preflight.get(job["id"], {}).get("reason") or ("Review constraints" if job["constraint_blockers"] else job.get("next_action", "Review official form"))
        today = now()[:10]
        daily = {"date":today,"new_opportunities":sum(j["first_seen_at"].startswith(today) for j in jobs),"high_priority":sum(j["priority"] in ("P0","P1") for j in jobs),"verified_active":sum(j["verification_status"] == "Verified Active" for j in jobs),"submitted":sum(a.get("submitted_at", "").startswith(today) and a["status"] == "Submitted" for a in apps),"needs_user":sum(a["status"] == "Needs user" for a in apps),"blocked":sum(a["status"] in ("Blocked","Pending confirmation","In progress") for a in apps),"stale":sum(j["verification_status"] == "Likely Stale" for j in jobs),"duplicates":sum(e["kind"] == "duplicate_discovery" and e["at"].startswith(today) for e in events)}
        tables = {"job_pool":jobs,"application_log":apps,"daily_dashboard":[daily],"coverage_and_events":events}
        daily["needs_user"] = sum(j["application_status"] == "Needs user" for j in jobs)
        tables["blocker_queue"] = [{"job_id":j["id"],"company":j["company"],"status":j["application_status"],"next_action":j["next_action"]} for j in jobs if j["application_status"] in ("Needs user","Blocked","Pending confirmation","In progress")]
        for table in ("signals","networking"):
            tables[table] = [json.loads(r[0]) for r in self.db.execute(f"SELECT data FROM {table}")]
        out = self.root / "dashboard"
        out.mkdir(exist_ok=True)
        markup = ['<!doctype html><meta charset="utf-8"><title>ApplyPilot dashboard</title><style>body{font:15px system-ui;margin:32px;color:#182a38}table{border-collapse:collapse;display:block;overflow:auto}td,th{padding:8px;border:1px solid #ccd7df;max-width:420px;min-width:100px;overflow-wrap:anywhere}th{background:#eef4f7;text-align:left}h1{color:#12645b}</style><h1>ApplyPilot · Private dashboard</h1>']
        for name, rows in tables.items():
            keys = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
            def value(v):
                s = json.dumps(v, ensure_ascii=False) if isinstance(v,(list,dict)) else str(v if v is not None else "")
                return "'"+s if s.startswith(("=","+","-","@","\t","\r")) else s
            with (out / f"{name}.csv").open("w",newline="",encoding="utf-8") as f:
                writer = csv.DictWriter(f,fieldnames=keys)
                writer.writeheader()
                writer.writerows({k:value(v) for k,v in row.items()} for row in rows)
            markup.append(f"<h2>{html.escape(name)}</h2><table><tr>"+"".join(f"<th>{html.escape(k)}</th>" for k in keys)+"</tr>")
            for row in rows:
                markup.append("<tr>"+"".join(f"<td>{html.escape(value(row.get(k,'')))}</td>" for k in keys)+"</tr>")
            markup.append("</table>")
        (out / "index.html").write_text("".join(markup),encoding="utf-8")
        return out / "index.html"
