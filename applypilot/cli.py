import argparse
import json
import os
from pathlib import Path
from .core import TAXONOMY, digest, now
from .store import Store
from .policy import read, policy_hash, Pause
from .discovery import cycle, hiring_signal

def defaults():
    profile = {"candidate":{"legal_name":"","email":"","phone":""},"capabilities":[],"targets":{"locations":["San Francisco Bay Area"],"seniority":[],"employment_types":["full-time"],"excluded_companies":[],"excluded_roles":[]},"preferred_companies":[],"work_authorization":{"country":"United States","eligible":None,"requires_sponsorship_now":None,"requires_sponsorship_in_future":None},"resumes":[]}
    policy = {"auto_submit_enabled":False,"approved_role_categories":[],"approved_locations":[],"approved_seniority":[],"approved_employment_types":["full-time"],"excluded_companies":[],"approved_resume_versions":[],"approved_answer_bank_version":"","permitted_browser_account_scope":["isolated:no-account"],"allowed_hosts":[],"salary":{"min":None,"max":None,"currency":"USD","period":"annual"},"profile_sha256":"","answer_bank_sha256":"","approved_manifest_hashes":[],"approval":{"approved_by":"","approved_at":None,"policy_sha256":""},"revoked_at":None}
    return {"candidate_profile":profile,"auto_submit_policy":policy,"answer_bank":{"version":"draft-1","answers":{}},"watchlist":{"companies":[],"manual_sources":["LinkedIn public jobs/posts","X public hiring posts","YC Work at a Startup","HN Who is Hiring","Reddit","VC portfolio careers","accelerators","AI communities"]}}

def main(argv=None):
    parser = argparse.ArgumentParser(description="ApplyPilot: private discovery and gated official applications")
    parser.add_argument("--state",default=os.environ.get("APPLYPILOT_HOME",str(Path.home()/".applypilot")))
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init")
    sub.add_parser("dashboard")
    sub.add_parser("revoke")
    sub.add_parser("review-policy")
    monitor = sub.add_parser("cycle")
    monitor.add_argument("--kind",choices=["breaking","daily","weekly"],default="daily")
    ingest = sub.add_parser("import")
    ingest.add_argument("kind",choices=["jobs","signals","networking"])
    ingest.add_argument("file")
    apply = sub.add_parser("apply")
    apply.add_argument("job_id")
    apply.add_argument("--manifest",required=True)
    apply.add_argument("--live",action="store_true",help="Click submit only with fully approved policy; default is dry run")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("job_id")
    reconcile.add_argument("--verified-not-submitted",required=True,help="User-reviewed evidence explaining why a retry is safe")
    args = parser.parse_args(argv)
    store = Store(args.state)
    root = store.root
    if args.command == "init":
        for name,data in defaults().items():
            path = root/f"{name}.json"
            if not path.exists():
                path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
        print(f"Private state initialized at {root}. Auto-submit disabled. Monitoring not installed.")
        return
    if args.command == "revoke":
        path = root/"auto_submit_policy.json"
        policy = read(path)
        policy.update(auto_submit_enabled=False,revoked_at=now())
        path.write_text(json.dumps(policy,indent=2),encoding="utf-8")
        store.event("revoked",{})
        print("Auto-submit revoked")
        return
    profile = read(root/"candidate_profile.json")
    if args.command == "review-policy":
        policy = read(root/"auto_submit_policy.json")
        print(json.dumps({"policy":policy,"current_policy_sha256":policy_hash(policy),"current_profile_sha256":digest(profile),"current_answer_bank_sha256":digest(read(root/"answer_bank.json")),"instruction":"Review completed configuration with user. This command does not approve or enable it."},indent=2))
    elif args.command == "import":
        records = read(args.file)
        if not isinstance(records,list):
            raise ValueError("Import must be a JSON array")
        for record in records:
            if args.kind == "jobs":
                # Imported evidence is untrusted until separately reviewed by the operator.
                record["evidence"] = [{**e,"kind":"unverified_import"} for e in record.get("evidence", [])]
                record["original_posted_at_verified"] = False
                record["last_hiring_signal_at_verified"] = False
                store.upsert(record)
            else:
                store.record(args.kind,hiring_signal(record) if args.kind == "signals" else record)
        print(store.dashboard(profile))
    elif args.command == "cycle":
        summary = cycle(store,read(root/"watchlist.json"),profile=profile)
        store.event("cycle",{"kind":args.kind,"new":summary["new"]})
        # All cycles refresh evidence; weekly also emits outcome review for operator action.
        if args.kind == "weekly":
            summary["review"] = {"instruction":"Review watchlist, reposts, stale jobs and outcome trends; never auto-change approval policy", "outcomes":dict(store.db.execute("SELECT status,COUNT(*) FROM applications GROUP BY status").fetchall())}
        print(json.dumps(summary,indent=2))
        print(store.dashboard(profile))
    elif args.command == "apply":
        from .browser import launch
        job = next((j for j in store.jobs() if j["id"] == args.job_id),None)
        if not job:
            raise ValueError("Job not found")
        try:
            print(json.dumps(launch(store,job,root,args.manifest,args.live),indent=2))
        except Pause as exc:
            store.event("needs_user",{"job_id":args.job_id,"reason":str(exc)})
            print("Needs user: " + str(exc))
        finally:
            store.dashboard(profile)
    elif args.command == "reconcile":
        row = store.db.execute("SELECT status,data FROM applications WHERE job_id=?",(args.job_id,)).fetchone()
        if not row or row[0] == "Submitted":
            raise ValueError("No retryable attempt; confirmed submissions cannot be cleared")
        store.event("manual_reconciliation",{"job_id":args.job_id,"previous_status":row[0],"previous_attempt":json.loads(row[1]),"evidence":args.verified_not_submitted})
        with store.db:
            store.db.execute("DELETE FROM applications WHERE job_id=?",(args.job_id,))
        print("Attempt archived. Retry reservation released following user verification.")
    else:
        print(store.dashboard(profile))

if __name__ == "__main__":
    main()
