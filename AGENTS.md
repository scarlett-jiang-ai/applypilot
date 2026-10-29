# Agent instructions

Read SKILL.md and the workflow/safety references before changing or running ApplyPilot. Preserve MIT attribution, agent-led onboarding, evidence, blocker and follow-up workflows.

- Official company or employer-linked ATS applications only. No LinkedIn Easy Apply or third-party one-click services.
- Existing resumes only: no editing, generation or tailoring.
- Never infer identity, legal, sponsorship, salary, employment or immigration facts.
- Private records stay outside Git (default ~/.applypilot; ignored .private is an alternative).
- Auto-submit defaults false. Agents may prepare but never self-approve policies. Obtain explicit approval after showing the completed configuration.
- Pause on CAPTCHA, authentication, permissions, uncertain fields, failed uploads and sensitive requests. No bypasses, credentials or cookies.
- Count only confirmed submissions. Never retry uncertain clicks.
- Never send networking messages automatically.

Python 3.11+. Run `python -m unittest discover -s tests -v`. Optional browser tests require Playwright/Chromium and APPLYPILOT_BROWSER_TESTS=1; all responses are fictional and intercepted. No real applications in tests. Public examples must be fictional. Work in the user's fork; do not auto-merge.
