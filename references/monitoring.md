# Monitoring

Monitoring is not active until installed. Configure private watchlist and verify a manual cycle first. Schedules discover only; they never submit applications or approve policies.

```text
python -m applypilot --state /absolute/private/path cycle --kind breaking
python -m applypilot --state /absolute/private/path cycle --kind daily
python -m applypilot --state /absolute/private/path cycle --kind weekly
```

Breaking cycles every three hours persist notifications for new P0/P1 opportunities once. Daily refreshes boards/evidence. Weekly additionally reports outcome counts and review instructions for watchlist/stale/reposted jobs. Rules are never automatically changed. All cycles regenerate the dashboard. Notifications are local events and scheduler output; email/Slack/push delivery requires an authorized notifier. Notify only on meaningful changes or failures.

## Windows

Install package into a venv. Run scripts/install-monitoring.ps1 with -Python pointing to its python.exe and -State to the private directory. -WhatIf previews registration. The installer refuses an empty watchlist, creates three per-user tasks and reads their schedules back. Machine must be awake and user logged in.

Check `Get-ScheduledTask -TaskName 'ApplyPilot-*'` and `Get-ScheduledTaskInfo -TaskName ApplyPilot-Breaking`. Remove with `Unregister-ScheduledTask -TaskName ApplyPilot-Breaking` (and Daily/Weekly). This repository does not automatically install user tasks.

## Unix cron

Use absolute interpreter/state paths and private logs; machine local timezone:

```cron
0 */3 * * * /absolute/venv/bin/python -m applypilot --state /absolute/private/path cycle --kind breaking >> /absolute/private/path/monitor.log 2>&1
15 8 * * * /absolute/venv/bin/python -m applypilot --state /absolute/private/path cycle --kind daily >> /absolute/private/path/monitor.log 2>&1
30 9 * * 0 /absolute/venv/bin/python -m applypilot --state /absolute/private/path cycle --kind weekly >> /absolute/private/path/monitor.log 2>&1
```

Verify with crontab -l and a manual run. CI validates fictional workflows, not live monitoring or applications.
