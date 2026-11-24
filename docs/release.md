# Implementation report

## Available
FastAPI and Persian server-rendered pages, SQLAlchemy schema versions 1–3, PostgreSQL Compose deployment, optional SQLite local mode, a scheduled worker, same-origin link discovery with manual approval, robots checks and pinned-address HTTPS requests. Reviewers can publish or reject extracted notices. The public directory uses persisted records, field evidence, search, filters, pagination, sorting and Jalali dates. Repeated fetches of the same source update one record. Changes retain prior field values. Job failures leave published records available. The optional structured-output model proposes a city and organization with verbatim supporting evidence.

## Verification
The unit and API suite runs against an isolated SQLite database. It covers date conversion, contradictory dates, missing fields, AI quote validation, private destination refusal, authentication, registration, extraction, review, publication, normalized search, repeats and failure retention. Browser smoke covers search and administrative source submission. Local Edge inspection covers 360, 430, 768 and 1440 pixel widths. The application started under Uvicorn. See README for reproduction.

## Live dependencies and remaining acceptance criteria
The Windows sandbox refused the outbound socket during a real worker attempt. The two historical article seeds are public references, with zero verified successful live crawls in this environment. Published count starts at zero. The prior project archive could not be transferred to this machine. This implementation was built in the provided project directory. No Docker CLI was available. A separate native PostgreSQL 17 initialization attempt failed because Windows could not create the restricted process token. PostgreSQL migrations, Compose startup, and production concurrency still need a run against the deployment database. Live model inference was not validated.

The collector handles ordinary UTF-8 HTML and exact label/value fields. It does not yet cover feeds, PDF, browser-rendered portals, Persian month-name deadlines, or all real-world wording. The seed set falls short of 10–20 independent sources. Identical published content across sources appears once with multiple references. Fuzzy merging of edited reposts and matching admission rounds are pending. Review states are pending, published and rejected; official-source and independent verification tiers, editable review fields, detailed extraction metrics, saved items, application-link validation and full filter/sort coverage are outstanding. These limits prevent production sign-off.

## Release checks
Run Compose with persistent PostgreSQL and network access. Approve current official announcement indexes and measure accepted field accuracy, missed notices and duplicate rates on representative pages. Validate retries, migrated data, same-origin discovery and approval throughput against those sources before a public launch.

