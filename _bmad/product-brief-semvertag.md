---
title: "Product Brief: semvertag"
status: "complete"
created: "2026-05-25"
updated: "2026-05-25"
inputs:
  - "Conversation: 2026-05-25 product-brief session"
  - "Source repo: /Users/kevinsmith/src/pypi/autosemver (current internal raif-autosemver)"
  - "Reference repo: /Users/kevinsmith/src/pypi/modern-di"
  - "Web research: auto-semver tool landscape (2026)"
  - "Review panel: skeptic, opportunity, devtools-adoption-friction (2026-05-25)"
---

# Product Brief: semvertag

> *The semver tagger that speaks both branch-prefix and Conventional Commits — built for teams in the middle of the migration.*

## Executive Summary

**semvertag** is a small, opinionated Python CLI that creates semantic-version git tags on a project's default branch by reading the most recent merge commit. It exists today as a closed-source internal tool (`raif-autosemver`) used in production across our shared CI pipelines at Raiffeisen. We are open-sourcing it on GitHub under a new name to make it useful to a broader community, attract contributors, and reduce single-vendor maintenance risk.

Existing auto-semver tools force teams into a single workflow religion: the `semantic-release` ecosystem speaks only Conventional Commits; `RightBrain-Networks/auto-semver` and GitVersion speak only GitFlow-style branch prefixes. Teams actively migrating from one convention to the other — and there are many — have no tool that meets them where they are. **semvertag's bet is that a single tool supporting both bump strategies, shipped as a tiny modern-Python CLI with GitLab as a first-class provider, is differentiated enough to win a meaningful audience.** That bet is partially de-risked by the fact that `go-semrel-gitlab`, the only purpose-built GitLab-native tagger, has been stagnant since 2022.

This is a hypothesis brief, not a confident forecast. Adoption depends on execution against the first-five-minutes experience and on credible migration paths from incumbent tools.

## The Problem

Teams running CI in GitLab face three concrete pains when automating semver tagging:

1. **Tool selection is a workflow lock-in.** Picking `semantic-release` means committing to Conventional Commits *and* the npm runtime. Picking `RightBrain-Networks/auto-semver` means committing to GitFlow branch prefixes *and* an aging, untyped Python codebase. There is no tool that supports both strategies in one binary, so teams either delay convention migrations or run two parallel toolchains during transition.
2. **GitLab is a second-class citizen.** The dominant `semantic-release` ecosystem requires a `package.json` even in non-JS projects, exposes brittle GitLab config, and is governed by a community oriented around GitHub Actions. `go-semrel-gitlab` — the one GitLab-native alternative — has been effectively abandoned (last commit 2022, multiple personal forks).
3. **Existing tools over-reach.** Most release tools want to own the whole release lifecycle: changelogs, GitHub Releases, npm publish, Slack notifications. Teams whose CI already handles those concerns need *just* a tagger and cannot get one without dragging in the rest.

Internally, `raif-autosemver` solves the GitLab case for our own pipelines — but it is locked behind a private Artifactory, missing CI/CD, docs, and the affordances expected of an open-source library.

## The Solution

semvertag does one thing: **read the latest merge commit on the default branch, infer the right semver bump, and create the tag.** Nothing else.

- **Two bump strategies, one binary.** Branch-prefix mode (`feature/` → minor, `bugfix/` / `hotfix/` → patch) and Conventional Commits mode (`feat:` → minor, `fix:` → patch, `BREAKING CHANGE` → major). Strategy is selectable per-repo via config; the same tool serves both legacy GitFlow repos and modernized Conventional Commits repos in the same org.
- **Zero-install execution.** `uvx semvertag` is the headline invocation — no install step, no virtualenv, no Node runtime. The "install" is one line in `.gitlab-ci.yml`.
- **GitLab-first, multi-provider by design.** Ships with GitLab support at v1.0; GitHub and Bitbucket follow on the v1.x roadmap in the standard install — a shared `httpx2` HTTP client across all providers means no per-provider SDK dependency and no `[github]` / `[bitbucket]` optional-extras packaging. Provider abstraction is a first-class concept, not a plugin retrofit.
- **Auto-detected context.** No `<project_id>` argument required in CI: defaults to `CI_PROJECT_ID` (GitLab) / `GITHUB_REPOSITORY` (GitHub) / git remote URL, override available.
- **Does one job well.** No changelog generation, no GitHub Releases creation, no PyPI publish. Composes with `git-cliff` or whatever release-notes tooling the team already uses.
- **Modern Python, typed throughout.** Python 3.10+ for v1.0 — broad enterprise reach without giving up modern typing. `pydantic-settings` config, `rich` output, type-checked with `ty`.

## What Makes This Different

| Tool | Convention | Provider | Runtime | Status |
|---|---|---|---|---|
| `semantic-release` (npm) | Conventional Commits only | GitHub-first; GitLab via plugin | Node | Active, heavy |
| `python-semantic-release` | Conventional Commits only | GitHub-first | Python | Active, monolithic |
| `RightBrain/auto-semver` | Branch prefix only | Git (provider-agnostic, limited) | Python | Stale |
| `go-semrel-gitlab` | Conventional Commits | GitLab-native | Go | Abandoned |
| `release-please` | Conventional Commits | GitHub only | Node | Active, monorepo-painful |
| **semvertag** | **Both, switchable** | **GitLab first; GH/BB roadmap** | **Python 3.10+ via `uvx`** | **New, lightweight** |

Three legs of differentiation:

1. **Migration-aware** — the only tool supporting teams in transition between branch-prefix and Conventional Commits. Worked-example: a team running branch-prefix on 30 legacy repos can flip Conventional Commits on the 5 new repos with one config change per repo, no toolchain swap.
2. **GitLab-native and alive** — fills the vacant slot left by `go-semrel-gitlab`. Plans to publish as a GitLab CI Catalog component (GitLab 17+) for native discoverability.
3. **Modern and minimal** — typed, `uvx`-runnable, no plugin ecosystem to learn, no Node runtime to drag into Python pipelines.

**Differentiation durability:** Leg 1 is the only true moat. `semantic-release` *could* add branch-prefix mode in a weekend if motivated; we are betting that they won't, because their community is ideologically committed to Conventional Commits. If they do, legs 2 and 3 still stand — but the headline narrative would need to evolve toward GitLab-native and runtime-minimal angles.

## Who This Serves

**Primary user:** A platform / DevOps / SRE engineer at a small-to-midsize company running GitLab (self-hosted or .com), maintaining shared CI templates across multiple downstream repos. They want repeatable, automatic version tagging without standing up a Node toolchain or forcing every team onto new commit conventions overnight. *Aha moment:* "It works on the repo we just migrated to Conventional Commits AND on the repo that still uses GitFlow — same tool, same config schema."

**Secondary users (tag-only audiences underserved by changelog-heavy tools):**
- Terraform module authors tagging on every merge
- Helm chart maintainers
- Python library authors who tag on merge but publish via separate tooling
- GitHub Actions users wanting a smaller alternative to `python-semantic-release`

**Adoption path:** copy-paste a CI snippet, set a token env var, done. No PRs into the repo's history, no new commit conventions required.

## Success Criteria

This is an open-source library; success is measured by adoption signal and contribution health. **These targets are hypotheses to validate, not commitments.**

**6-month signals (by 2026-11):**
- ≥100 PyPI downloads/month (sustained) — sanity-check threshold; well below dominant tools but signals real-world install
- ≥25 GitHub stars
- ≥1 external contributor merged
- ≥1 public mention or write-up (blog, Mastodon, HN comment)
- Open issues answered within 7 days median

**12-month signals (by 2027-05):**
- GitHub provider shipped and used outside Raiffeisen
- Listed in at least one `awesome-gitlab` / `awesome-ci` curated list
- Published as a GitLab CI Catalog component with non-zero usage

**Anti-goals (will *not* measure):**
- Total downloads vs. `semantic-release` — irrelevant; different audience.
- Feature parity with `semantic-release` — explicitly the wrong target.

## Scope

**v1.0 (launch — single MIT-licensed repo):**

*Core CLI:*
- GitLab provider with no regressions on internal pipelines
- Conventional Commits bump strategy alongside branch-prefix; selectable per-repo
- Auto-detect project from CI env (`CI_PROJECT_ID`) or git remote, with override
- `semvertag doctor` subcommand validating token, scopes, project access, protected-tag config
- Documented edge-case behavior: repo with no existing tags, non-semver tags (`release-2024-Q1`), squash-merge vs merge-commit histories, shallow clones

*CI surfaces:*
- GitHub Actions Marketplace action (thin wrapper)
- GitLab CI Catalog component
- Copy-pasteable CI snippets in README hero (GitLab and GitHub)

*Trust surface:*
- Full CI on GitHub Actions (lint + `ty` + pytest matrix)
- Docs on Read the Docs (mkdocs + Material), mirroring `modern-di` structure
- README badges (CI, PyPI version, Python versions, coverage), demo asciicast/gif, `SECURITY.md`, `CONTRIBUTING.md`
- `LICENSE` (MIT), `py.typed`, `context7.json`, `CLAUDE.md`
- Migration docs: `docs/migrating-from-semantic-release.md`, `docs/migrating-from-go-semrel-gitlab.md`, `docs/migrating-from-rightbrain-auto-semver.md`
- Published API stability policy: CLI flags and config keys are SemVer-stable post-1.0; deprecations carry a one-minor-version warning

*Discovery:*
- README H1 and meta description include "GitLab CI", "auto tag", "semver"
- Launch posts: "How we migrated 30 repos from GitFlow to Conventional Commits without picking sides" and "Why we left `semantic-release` for a 400-line Python CLI"
- Reserve handles on PyPI, GitHub org, Read the Docs, GitLab CI Catalog before announcement

**v1.x (post-launch):**
- GitHub provider (shipped in the standard install — no optional-extras dance)
- Bitbucket provider (shipped in the standard install — no optional-extras dance)
- Dry-run / `--explain` output
- Pre-release / RC tag support (`-rc.1`, `-beta.2`)

**Explicitly out of scope:**
- Changelog generation — use `git-cliff` or equivalent
- Release-notes publishing (GitHub/GitLab Releases bodies)
- PyPI / npm / Docker publishing
- Plugin system — every option is a flag, not a plugin
- Monorepo / multi-package versioning — recommend `release-please` for that case; we don't compete there

## Risks

- **Name collision past:** the dormant PyPI `autosemver` and active `RightBrain/auto-semver` necessitated the rename. Mitigation already taken: `semvertag` (PyPI-verified free, 2026-05-25).
- **Differentiation durability:** `semantic-release` could add branch-prefix support and erode leg 1. Mitigation: emphasize GitLab-native and runtime-minimal positioning early; treat dual-mode as headline but not sole moat.
- **Bus factor:** the v1.0 maintainer pool is one team at one bank. Mitigation: actively recruit a non-Raiffeisen co-maintainer in the first 6 months; publish a "we will never add X" list to make contribution scope legible.
- **IP / open-source clearance:** publishing internal code requires legal review at Raiffeisen. Mitigation: include in the launch timeline as a non-negotiable prerequisite; brief assumes clearance is achievable.
- **Internal vendoring path:** Raiffeisen's adoption of the public PyPI package will require security review of an external dep. Not a success metric in this brief, but a real launch-adjacent process. Open question for the PRD: who owns the mirroring / vendoring path?
- **GitLab shipping native auto-tagging:** low-probability but high-impact. Mitigation: monitor GitLab's CI roadmap; if it happens, pivot to migration-aware positioning where the native tool is one of the strategies.

## Vision (2–3 year horizon)

In two to three years, semvertag is the answer when someone asks *"how do I auto-tag in GitLab CI?"* — the way `bump-my-version` is the answer for local bumps. It maintains a deliberately small surface area, an active maintainer pool of 3–5 people including at least one non-Raiffeisen contributor, and a reputation as the *boring, reliable* option in a space dominated by ambitious-but-fragile alternatives. The internal `raif-autosemver` no longer exists as a separate codebase; we run the open-source build like everyone else.

The success state is not "semvertag wins" — it's "semvertag is uncontroversially the right pick for a specific, well-defined use case, and that use case is broad enough to matter."

## Open Questions for the PRD

- **Config surface:** TOML in `pyproject.toml`, separate `.semvertag.toml`, or env-only?
- **Strategy switching granularity:** per-repo only, or per-branch within a repo?
- **Internal mirroring path:** how does Raiffeisen consume the public PyPI package — direct, mirrored to Artifactory, or vendored?
- **GitHub org:** personal user, dedicated org (`semvertag-dev`), or Raiffeisen public org? Affects bus-factor narrative.
- **Sunset signal for the dormant PyPI `autosemver`:** quietly ignore, or proactively contact the maintainer?
