# Discovery and evidence

Automated feeds: Greenhouse, Ashby and Lever public boards. Configure an employer careers URL linking to the exact board. Redirects, access errors (including 403/429) and parsing failures are recorded without bypass retries. Reads are spaced by one second. Board absence marks closure only after a complete successful response.

Greenhouse updated_at is not publication. Lever's public posting API lacks a reliable documented original publication field. Both remain unknown. Ashby publishedAt is medium-confidence provider publication and may reflect republication; subsequent changes are stored as repost dates, preserving the original observation. First seen is local discovery. Dates need timezones. Evidence includes source URL and observation time.

P0 [0,6h), P1 [6,24h), P2 [24,48h), P3 [48h,7d); older/unknown deprioritized. P3 requires strong responsibility fit. A verified recent hiring signal can elevate an old vacancy, explicitly identifying the signal as the basis. Reposting alone neither proves fraud nor resets freshness.

Hard constraints precede ranking: capabilities 30%, freshness 25%, active evidence 20%, preferred company 15%, documented introduction 10%. Explanations include matched terms, timestamp basis, components and blockers. This lexical heuristic is not an LLM semantic model or hiring probability. Review negative requirements, years of experience, country, location and seniority before applications.

## Public-source workflow

- Company/VC portfolio careers: identify exact employer, role and official link.
- LinkedIn public jobs/founder posts: search responsibilities and time windows; never log in. Distinguish original publication and reposts.
- X: capture original post URL, author/role, text and verifiable time.
- YC Work at a Startup, HN Who is Hiring, Reddit, accelerators and AI communities: search founder, GTM, product, ecosystem, investment and adoption responsibilities. Resolve to an official form before execution.
- Use available authorized tools. Blocked access means unavailable/not searched, never successful coverage.

Import arrays via `python -m applypilot import jobs FILE`, `import signals FILE`, or `import networking FILE`. Imports are not automatically trusted. Signals require company, person, person_role, platform, original url and text, with posted_at/relevant_capabilities/official_url when available. Missing formal applications lead to investigation or draft outreach, never automatic messaging. Networking tracks company/person/public URL/introduction/outreach/follow-up status.

To verify an imported job, inspect it through authorized tools, record evidence kind/source URL/UTC observation, and update private state using Store.upsert. This is an operator review boundary. Never manufacture dates. Preserve funding/team-change/watchlist notes; funding alone is not an opening.

Primary references: [Greenhouse](https://docs.greenhouse.io/job-board), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api), [Lever](https://github.com/lever/postings-api), [Playwright](https://playwright.dev/python/docs/input).
