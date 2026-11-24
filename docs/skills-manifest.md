# Skill research and installation report · 2026-11-24
Codex Work Mode runs PowerShell on Windows. The project directory was empty. Git 2.39.1, Node 24.19, npm 11.17, Python 3.13, FastAPI, SQLAlchemy and Playwright are present. Docker CLI was not found. Project .agents and .codex are read-only under the session permissions.

| Candidate repository | GitHub display | Decision |
|---|---:|---|
| https://github.com/obra/superpowers | 325.5k | Shortlist writing-plans, systematic-debugging, test-driven-development and verification-before-completion. Repository lists MIT. |
| https://github.com/anthropics/skills | 199.7k | Shortlist frontend-design and webapp-testing. Per-skill licenses and helper scripts need pinned review. |
| https://github.com/vercel-labs/agent-skills | 34.8k | Defer React guidance for the server-rendered implementation. Repository lists MIT. |
| https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 153.5k | Defer the overlapping design workflow and its CLI dependencies. |

Counts are rounded numbers displayed by GitHub. Source inspection through web search worked. The terminal command `git ls-remote https://github.com/obra/superpowers.git HEAD` failed to connect on port 443. No pinned local trees could be audited, so no candidate passed the installation gate. No installer executed, no scripts ran, and no external skill was installed, registered, invoked or verified. Commit date, SHA, dependency inventory and individual license eligibility are unverified. No lockfile or installation path is claimed.
