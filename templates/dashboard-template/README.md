# Private dashboard schema

SQLite is the source of truth. `python -m applypilot dashboard` exports local HTML and CSV snapshots under the private state directory. No public hosting/account required.

Job pool: employer/role/family/location, official URL/source, separate timestamps/confidence/evidence, priority/ranking/blockers, resume and next action.
Application log: attempt/submission times, URL, resume/Answer Bank versions, confirmation, status/blocker.
Signals/networking: public evidence and follow-up opportunities.
Daily: new/high-priority/verified/submitted/needs-user/blocked/stale/duplicate counts.
Coverage/events: source gaps and audit history.

Retained follow_up, resume_rules and automation_rules templates are manual companion worksheets. Never infer submissions from those sheets. Dry runs are not submitted. Pending confirmation and In progress require manual reconciliation. Never commit private exports.
