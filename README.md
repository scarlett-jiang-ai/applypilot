# Scarlett ApplyPilot v2

[中文](README.zh-CN.md)

A private, freshness-first discovery and official ATS application workflow, built from ApplyPilot with its MIT attribution and agent-led setup preserved.

**Discover → verify → match responsibilities → select an existing PDF → fill an official form → conditionally submit → confirm → track.**

Auto-submit is disabled until the user approves a completed private policy. Tests and discovery cycles never submit real applications.

## Quick start

Python 3.11+:

```sh
git clone https://github.com/scarlett-jiang-ai/applypilot.git
cd applypilot
python -m venv .venv
# Activate the venv for your shell, then:
python -m pip install -e ".[browser]"
python -m playwright install chromium
python -m applypilot init
python -m applypilot review-policy
python -m applypilot cycle --kind daily
python -m applypilot dashboard
```

Default private state: ~/.applypilot. Override with --state /absolute/private/path before the command. Configure the watchlist and candidate files first; an empty watchlist performs no searches. Dashboard is local HTML with CSV exports, not a public service.

## Implemented

- Six extensible families: AI product; founder/strategy/operations; GTM/growth/partnerships; ecosystem/community/DevRel; VC/investment; AI adoption/customer strategy. Scores use responsibilities, not title equality.
- Separate publication, first-seen, repost, signal and verification times; P0/P1/P2/P3 windows; unknown dates remain unknown.
- Public Greenhouse/Ashby/Lever feeds with employer-board link checks, evidence, persistent IDs and coverage gaps. Social hiring-signal and networking import workflows.
- Hard-constraint blockers, explainable 30/25/20/15/10 ranking and Verified Active/Likely Active/Unverified/Likely Stale classifications.
- SQLite duplicate protection, transactional reservations and manual reconciliation for uncertain attempts.
- Existing-PDF routing/checksums, exact approved answers, configuration-bound policy, revocation and a real conservative Playwright form runner.
- Private job pool, application log, signals, networking, daily dashboard and coverage/events.
- Breaking/daily/weekly discovery commands, optional Windows task installer, Unix scheduling instructions, fictional tests and CI.

## Application execution

Read [setup](references/setup-workflow.md) and [ATS playbook](references/application-playbook.md). Inspect the official form, create a private manifest from observed controls, complete candidate/answer/resume configuration, and obtain explicit approval. The runner never generates approval or resume content.

```sh
python -m applypilot apply JOB_ID --manifest /private/form.json
# After review/reconciliation of the dry run, under approved policy:
python -m applypilot apply JOB_ID --manifest /private/form.json --live
python -m applypilot revoke
```

No LinkedIn Easy Apply, LinkedIn credentials, resume editing, automatic outreach, CAPTCHA bypass, account creation or automatic login. Unknown sensitive facts and changed forms pause.

## Validation

```sh
python -m unittest discover -s tests -v
# Bash, with browser dependencies installed:
APPLYPILOT_BROWSER_TESTS=1 python -m unittest discover -s tests -v
```

PowerShell: set `$env:APPLYPILOT_BROWSER_TESTS='1'` before the test command. Browser tests intercept all requests with fictional HTML; no employer is contacted.

## Limits and remaining setup

- Add real PDFs/contact/authorization facts and approval privately; none are bundled.
- Matching is lexical and explainable, not a trained semantic model. Review nuance, required experience, location and seniority; unknown constraints block execution.
- Browser support covers reviewed single-page native forms. Site-specific Greenhouse/Ashby/Lever/employer compatibility depends on the manifest. Workday login, custom widgets, multi-step and embedded forms need handoff or another tested adapter. Live ATS compatibility is not certified.
- Public LinkedIn, X, YC, HN, Reddit and portfolio/community sources need authorized search/browser work or imports. Executable feeds cover configured ATS boards only.
- Monitoring and push notifications are not active by default. [Install and verify schedules](references/monitoring.md); notifications are local events until a notifier is connected.
- Hashes track reviewed content, not signed identity. Protect private state with OS permissions.

[Audit](references/audit.md) · [Discovery/evidence](references/discovery-workflows.md) · [Safety](references/safety-and-boundaries.md) · [Fictional examples](examples/fake-demo-example) · [Templates](templates)
