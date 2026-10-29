# Setup workflow

Run `python -m applypilot init`. Default private state is ~/.applypilot; use --state or APPLYPILOT_HOME to override. Use encrypted local storage with user-only permissions. Ignored .private is an alternative. Never publish private files or CI artifacts.

Init preserves existing files and creates candidate_profile.json, answer_bank.json, auto_submit_policy.json, watchlist.json and state.sqlite.

## Minimum onboarding

Draft only user-provided facts. Confirm legal name/contact before use. Record capabilities using templates/capability_taxonomy.json; extend when needed. Record locations, seniority, employment types, excluded roles/employers, country-specific authorization and current/future sponsorship separately. Unknowns remain null. Do not infer technical skills, years of experience or immigration facts.

Add existing PDFs with absolute paths, approved versions, role families and lowercase SHA-256 hashes (Get-FileHash on Windows or sha256sum on Unix). Never modify PDFs. Suggested routes: AI Product; Founder / Strategy; GTM / Ecosystem (GTM / Growth, Ecosystem / Community, AI Adoption); VC / Investment. No matching PDF means Needs user.

Answer Bank keys are exact complete questions. Each entry has value, kind and approved=true only after user approval. Salary also requires currency and period. Unknown optional self-ID stays blank. The runner never invents or paraphrases answers.

## Watchlist

Record company, source (greenhouse/ashby/lever), board, board_url and employer careers_url. The careers page must link to the specified ATS board. Keep stage, funding evidence, team expansion and introduction opportunities as notes. Funding alone is not an opening. Public social searching follows discovery-workflows.md; unsupported sources are recorded as not searched.

## Approval ceremony

1. Complete profile, exact Answer Bank, existing-resume routing and a private manifest from observed form controls. Verify employer linkage and all questions.
2. Configure allowed categories, locations, seniority, employment types, exclusions, hosts, resume versions, Answer Bank version, account scope and salary range.
3. Compute canonical hashes with applypilot.core.digest for profile, bank and manifests. Set profile_sha256, answer_bank_sha256 and approved_manifest_hashes. `python -m applypilot review-policy` displays hashes/policy; it does not approve it.
4. Show the entire completed configuration to the user and obtain explicit approval. Only then record approval.approved_by and ISO UTC approved_at, set approval.policy_sha256 to policy_hash(policy), auto_submit_enabled=true and revoked_at=null. Do not infer approval from a build request.
5. Changed configuration needs renewed review. `python -m applypilot revoke` prevents future clicks; an already dispatched click cannot be recalled.

Hashes are local content checks, not identity signatures. Protect state with OS permissions. First run discovery only. No real applications during development. Monitoring is opt-in; see monitoring.md.
