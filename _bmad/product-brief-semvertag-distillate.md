---
title: "Product Brief Distillate: semvertag"
type: llm-distillate
source: "product-brief-semvertag.md"
created: "2026-05-25"
purpose: "Token-efficient context for downstream PRD creation"
---

# semvertag — PRD Detail Pack

Dense bullets, grouped by theme. Each bullet stands alone so an LLM consuming this without the full brief still has enough context.

## Identity & naming

- Product name: `semvertag`. PyPI-verified free on 2026-05-25.
- Previous internal name: `raif-autosemver`, published to a private Raiffeisen Artifactory.
- Renamed to escape two collisions: dormant PyPI `autosemver` (david-caro, last release 2020) and `RightBrain-Networks/auto-semver` (active Python tool with near-identical branch-prefix-driven behavior).
- Names verified-free at decision time: `tagwright`, `semvertag` (chosen), `ci-semver`, `mergesem`, `branchver`, `semvertagger`, `semvr`. Names verified-taken: `gitsemver` (Allen Lawrence, active), `git-semver` (Romain Dorgueil, active), `autotagger`, `semverctl`.
- License: MIT.
- GitHub org: open question — personal user vs dedicated `semvertag-dev` org vs Raiffeisen public org.

## Current code state (transferable from autosemver/)

- Python 3.13 in `pyproject.toml`. Will need to expand to 3.10+ for v1.0 per brief.
- Module name `autosemver` (will be renamed to `semvertag` in code).
- Dependencies: `typer`, `python-gitlab`, `rich`, `semver`, `modern-di-typer`, `pydantic-settings`.
- Lint stack: `ruff`, `ty`, `auto-typing-final`, `eof-fixer`.
- Test stack: `pytest`, `pytest-cov`, `pytest-xdist`, `pytest-randomly`, `requests-mock`.
- Build: `uv_build`.
- Internal CI uses Justfile (`lock`, `install`, `lint`, `test` recipes).
- Settings: `pydantic_settings.BaseSettings` with `AUTOSEMVER_` env prefix. Settings keys: `gitlab_endpoint`, `merge_mark_text` ("Merge branch"), `gitlab_token`. Defaults to Raiffeisen GitLab URL — must be removed before open-sourcing.
- DI: `modern-di` Groups (`GitLabGroup`, `ConsoleGroup`, `UseCasesGroup`) wired in `ioc.py`.
- Use case: `AutosemverUseCase` is a frozen dataclass; takes `gitlab_client`, `console_handler`, `error_handler`.
- Current bump logic (`autosemver_use_case.py`):
  - Fetch latest commit on default branch.
  - If commit message lacks `Merge branch` (configurable), no-op.
  - Fetch latest tag. If no tags, error.
  - If latest tag is on the same commit, no-op.
  - Branch-prefix matching: `bugfix/` or `hotfix/` → `bump_patch()`; `feature/` → `bump_minor()`; else error "cannot bump version."
  - No `major` bump in current code — must be added for v1.0 (likely via Conventional Commits `BREAKING CHANGE` only).
- Test coverage exists for: no commits, non-merge commit, no tags, already-tagged commit, minor bump, patch bump, wrong-prefix.
- Existing Dockerfile is Raiffeisen-Artifactory-specific; must be replaced with public-image-based one (likely drop entirely; users use `uvx`).

## Rejected ideas (with rationale)

- **Keep name `autosemver`** — rejected; PyPI taken (dormant) and confusion risk with RightBrain `auto-semver` is too high. Rejected even with rename to distribution name `autosemver-cli` because the cognitive collision remains.
- **Rename to `gitsemver`** — rejected after the user picked it; PyPI verification showed Allen Lawrence's active `gitsemver` package does adjacent semver-from-git work. Worse than the original collision.
- **Multi-repo family pattern (modern-di style)** — rejected for v1; chose a single repo with all providers shipped in the standard install (shared `httpx2` HTTP client across providers — no per-provider SDK gating, no optional-extras packaging). Family pattern reconsidered post-v1 if scope grows.
- **Monorepo with sub-packages** — rejected; adds workspace tooling complexity for limited benefit at this scale.
- **Keep DI framework as public-positioning point** — rejected after skeptic review; DI stays internally if useful, but is no longer name-dropped as a feature. Reduces apparent over-engineering of a one-verb CLI.
- **Drop the internal-deprecation success metric** — was originally a 12-month signal; removed because it depends on Raiffeisen security review, which is circular and gameable.
- **Python 3.13+ floor** — rejected; chose 3.10+ to match `modern-di` and broaden enterprise reach.
- **Monorepo / multi-package versioning support** — explicitly out of scope; recommend `release-please` for that case.
- **Changelog generation, release-notes publishing, PyPI/npm/Docker publishing** — explicitly out of scope. Composes with `git-cliff` and other tools.

## Differentiation thesis (what to emphasize in the README)

- **Headline:** "The semver tagger that speaks both branch-prefix and Conventional Commits — built for teams in the middle of the migration."
- **Three differentiation legs**, ranked by durability:
  1. Migration-aware dual-mode (only true moat; `semantic-release` could erode this with a weekend's work if motivated, but their community is ideologically opposed to GitFlow).
  2. GitLab-native and alive (fills the vacancy from abandoned `go-semrel-gitlab`).
  3. Modern, minimal, `uvx`-runnable (no Node runtime, no plugin sprawl).
- **`uvx semvertag` is the headline invocation.** Zero install, no virtualenv, one CI line. This is the single biggest narrative differentiator vs. Node-based competitors and should be prominent in the README hero.
- **Worked example to write in docs:** team with 30 legacy repos on branch-prefix flips Conventional Commits on 5 pilot repos with one config change per repo, same toolchain throughout.

## Competitive intelligence

- `semantic-release` (npm, 1.34M weekly dl, 20.5k stars) — Conventional Commits only; GitLab via plugin (fiddly); requires `package.json`.
- `python-semantic-release` v10.x — Conventional Commits only; couples bump with PyPI publish + changelog; opinionated about `pyproject.toml` layout.
- `commitizen` (Python, 827k weekly dl) — commit-message helper that grew a bump command. Not a CI tagger first.
- `release-please` (Google) — generates a release-PR rather than tagging; GitHub-only in practice; monorepo UX is a sustained complaint.
- `standard-version` — deprecated by maintainers.
- `changesets` — manual intent capture; great for monorepos but not auto-inferred.
- `GitVersion` (.NET) — GitFlow-aware; closest conceptual sibling but .NET-toolchain-bound.
- `auto` (intuit/auto) — PR-label-driven; GitHub-first; weak GitLab story.
- `release-drafter` — drafts notes only; doesn't tag or bump.
- `bumpversion` / `bump-my-version` — local string bumpers; no commit/branch inference, no CI tagging.
- `go-semrel-gitlab` (Juhani Ränkimies, Go) — the GitLab-native player; stagnant with personal forks (Rosenögger, Gettys). This is the vacancy semvertag fills.
- `RightBrain-Networks/auto-semver` (Python) — direct functional twin; aging codebase, no DI/types, no Conventional Commits. Migration doc target.

## Pain points users complain about (to avoid)

- `semantic-release`: `feat!:` breaking-change syntax inconsistent (GH issues 3757, 2339); silently ignores non-conforming commits (commit-analyzer #278); requires `package.json` even in non-JS repos; opaque dry-run/CI detection (#2382).
- `release-please`: monorepo root-PR noise; releases page unusable with 40+ packages; `releases_created` output bug causing unintended deploys.
- General: plugin sprawl, heavy YAML, Node runtime dragged into non-JS pipelines.

## Reference structural model: modern-di

- Repo: github.com/modern-python/modern-di. Path: /Users/kevinsmith/src/pypi/modern-di.
- Layout to mirror: `.github/workflows/{ci.yml,publish.yml}`, `docs/` + `mkdocs.yml` + `.readthedocs.yaml`, `Justfile`, `pyproject.toml`, `LICENSE`, `README.md`, `CLAUDE.md`, `context7.json`.
- CI in modern-di: lint job (Python 3.10) + pytest matrix (3.10–3.14) on Ubuntu, uses `astral-sh/setup-uv@v3`.
- Publish: triggers on GitHub release published, calls `just publish` which does `uv build` + `uv publish --token $PYPI_TOKEN`.
- Docs theme: Material with code copy, edit buttons, dark mode, instant nav.
- Pytest config: `addopts = "--cov=. --cov-report term-missing"`, `pythonpath = ["."]`.
- modern-di ships zero runtime deps and uses `uv_build` backend.
- modern-di's family pattern is *separate repos* under one GitHub org. semvertag chose single-repo-with-extras instead — but the family pattern is the v2.x escape hatch if provider count grows.

## v1.0 deliverables checklist (from brief — for sprint planning)

Core:
- [ ] Rename module `autosemver` → `semvertag`
- [ ] Remove Raiffeisen-specific defaults from settings
- [ ] Conventional Commits bump strategy alongside branch-prefix
- [ ] Per-repo strategy selection via config
- [ ] Auto-detect project from `CI_PROJECT_ID` / `GITHUB_REPOSITORY` / git remote; argument is override only
- [ ] `semvertag doctor` subcommand (validate token, scopes, project access, protected-tag config)
- [ ] Handle edge cases: no existing tags, non-semver tags, squash-merge, shallow clones
- [ ] Major-bump support (currently missing in code; needs `BREAKING CHANGE` parsing)

CI/distribution:
- [ ] `.github/workflows/ci.yml` mirroring modern-di
- [ ] `.github/workflows/publish.yml` on release published
- [ ] PyPI publish via trusted publishing or token
- [ ] GitHub Actions Marketplace action (thin wrapper)
- [ ] GitLab CI Catalog component
- [ ] Copy-pasteable GitLab CI snippet in README hero
- [ ] Copy-pasteable GitHub Actions snippet in README hero

Docs / trust:
- [ ] `docs/` + `mkdocs.yml` Material + `.readthedocs.yaml`
- [ ] `LICENSE` MIT
- [ ] `py.typed`, `context7.json`, `CLAUDE.md`
- [ ] README badges: CI, PyPI version, Python versions, coverage
- [ ] Demo asciicast/gif
- [ ] `SECURITY.md`, `CONTRIBUTING.md`
- [ ] `docs/migrating-from-semantic-release.md`
- [ ] `docs/migrating-from-go-semrel-gitlab.md`
- [ ] `docs/migrating-from-rightbrain-auto-semver.md`
- [ ] Published API stability policy (CLI flags / config keys SemVer-stable post-1.0)

Discovery:
- [ ] README H1 + meta with "GitLab CI", "auto tag", "semver"
- [ ] Launch post #1: "How we migrated 30 repos from GitFlow to Conventional Commits without picking sides"
- [ ] Launch post #2: "Why we left `semantic-release` for a 400-line Python CLI"
- [ ] Reserve handles: PyPI, GitHub org, Read the Docs, GitLab CI Catalog

## v1.x roadmap (not v1.0)

- GitHub provider (shipped in the standard install — no optional-extras dance)
- Bitbucket provider (shipped in the standard install — no optional-extras dance)
- Dry-run / `--explain` output
- Pre-release / RC tag support (`-rc.1`, `-beta.2`)
- `mise` / `asdf` plugin for polyglot DevOps audiences
- Pre-commit hook integration

## Token / credential UX requirements

- GitLab: support `CI_JOB_TOKEN` (GitLab 16.0+ for protected tags), `GITLAB_TOKEN` env var, and explicit `SEMVERTAG_TOKEN`. Document the minimum scopes (`api`, `write_repository`).
- GitHub (v1.x): use `GITHUB_TOKEN` from Actions context by default.
- Local dry-run: support `~/.netrc` or `glab` config reading.
- Errors should be specific: tell the user *which* scope is missing, not a generic 403.

## Edge cases to document & test

- Repo with zero existing tags.
- Tags that are non-semver (`release-2024-Q1`, `v1.2.3-internal`, `prod-2026.05.25`).
- Squash-merge vs merge-commit histories — branch-prefix mode depends on merge commit message format.
- Shallow CI clones (`GIT_DEPTH=1`) — must fetch tags or use API.
- Default branch is not `main` (often `master`, `develop`, `trunk`).
- Empty default branch.
- Detached merge commits / fast-forward merges with no commit message.

## Open questions for the PRD

- Config surface: TOML in `pyproject.toml`, separate `.semvertag.toml`, or env-only?
- Strategy switching granularity: per-repo only, or per-branch within a repo?
- Internal mirroring path: how does Raiffeisen consume the public PyPI package — direct, mirrored to Artifactory, or vendored? Who owns the handoff?
- GitHub org: personal user, dedicated org, or Raiffeisen public org? Affects bus-factor narrative.
- Sunset signal for the dormant PyPI `autosemver`: quietly ignore, or proactively contact maintainer?
- Should the brief's "Used in production at Raiffeisen since [date]" line appear in the README, given IP-clearance review?

## Risks tracked

- Differentiation durability if `semantic-release` adds branch-prefix mode (low probability, high impact).
- Bus factor: v1.0 maintainer pool is one team at one bank. Mitigation: actively recruit a non-Raiffeisen co-maintainer in first 6 months; publish "we will never add X" list.
- IP / open-source clearance from Raiffeisen legal — launch dependency.
- Internal vendoring loop — security review of external dep is a months-long process, not modeled in success metrics.
- GitLab shipping native auto-tagging — low probability, high impact.

## Anti-goals (will not measure or pursue)

- Total downloads vs. `semantic-release`.
- Feature parity with `semantic-release`.
- Monorepo / multi-package versioning support.
- Changelog generation.
- Release-notes publishing.
- PyPI / npm / Docker publishing.
- Plugin system.
