---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
status: complete
completedAt: '2026-05-26'
inputDocuments:
  - "product-brief-semvertag.md"
  - "product-brief-semvertag-distillate.md"
workflowType: 'prd'
documentCounts:
  briefs: 2
  research: 0
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: cli_tool
  domain: general
  complexity: low
  projectContext: greenfield-with-transferable-code
releaseMode: phased
---

# Product Requirements Document - semvertag

**Author:** Artur Shiriev
**Date:** 2026-05-25

## Executive Summary

semvertag is a Python CLI that automates semantic-version git tagging for GitLab repositories by reading the most recent merge commit and inferring the correct bump. v1.0 ships GitLab support; GitHub and Bitbucket follow on the v1.x roadmap in the standard install (no optional-extras dance). The product replaces and open-sources an internal Raiffeisen tool (`raif-autosemver`) currently used in shared CI pipelines, with the strategic goal of de-risking maintenance, attracting external contributors, and filling a vacant slot in the open-source landscape.

Primary user: platform / DevOps / SRE engineers running GitLab who maintain shared CI templates across multiple repos and need automatic tagging without committing to a Node toolchain or forcing every team onto a single commit convention. Secondary users: Terraform module authors, Helm chart maintainers, and Python library authors who tag on merge but publish via separate tooling.

The product problem is dual: (1) existing auto-semver tools force a single commit-convention religion — `semantic-release` and derivatives speak only Conventional Commits; `RightBrain-Networks/auto-semver` speaks only GitFlow branch prefixes — leaving teams mid-migration without a tool that supports both; (2) GitLab is a second-class citizen across the ecosystem, with the one purpose-built native option (`go-semrel-gitlab`) abandoned since 2022.

### What Makes This Special

Three differentiation legs, ordered by durability:

1. **Migration-aware dual-mode (primary moat).** The only auto-semver tool that supports both branch-prefix (GitFlow) and Conventional Commits in a single binary, switchable per-repo. Teams running 30 legacy GitFlow repos can flip Conventional Commits on 5 pilot repos with one config change per repo, using the same toolchain throughout.
2. **GitLab-native and alive.** Fills the vacancy left by abandoned `go-semrel-gitlab`. Planned distribution as a GitLab CI Catalog component for native discovery, alongside a GitHub Actions Marketplace wrapper.
3. **Zero-install, runtime-minimal.** `uvx semvertag` is one line in `.gitlab-ci.yml`. No Node runtime, no `package.json` requirement, no plugin system, no virtualenv. Stark contrast to the `semantic-release` ecosystem's plugin sprawl.

**Core insight:** teams aren't statically committed to a commit convention — they're migrating between them. Existing tools force a religious choice, so teams delay migration or run parallel toolchains. semvertag meets them where they are.

**Aha moment:** "It works on the repo we just migrated to Conventional Commits AND on the repo that still uses GitFlow — same tool, same config schema."

**Brand voice:** deliberately *boring and reliable* — the uncontroversial pick for a well-defined use case. Not a marketing tool; a maintenance tool that does one thing and doesn't change underneath you.

## Project Classification

- **Project Type:** CLI tool (`cli_tool`) — single-verb command (`semvertag`) primarily invoked from CI environments via `uvx`. Secondary classification as `developer_tool` (pip-distributable library) is acknowledged but the CLI is the primary user surface.
- **Domain:** General developer tooling — no regulated industry, no compliance overlay, no novel research domain. Standard software practices apply.
- **Complexity:** Low (technical) with elevated *strategic* complexity. The product's technical surface is small (one CLI verb, a handful of providers, two bump strategies). The strategic complexity — escaped name collision, dual-mode positioning, multi-provider roadmap, GitLab/CI Catalog distribution path, Raiffeisen IP-clearance dependency — sits primarily in product/launch planning, not in the codebase itself.
- **Project Context:** Greenfield from a public-OSS perspective (no public repository yet); ~80% of the v1.0 GitLab-provider code already exists internally at `autosemver/` (frozen-dataclass use case, modern-di-based IoC, pydantic-settings config) and will be transferred under the new name with Raiffeisen-specific defaults stripped. (Test fixtures are migrated from `requests-mock` to `httpx2.MockTransport` as part of the transfer.)

## Success Criteria

### User Success

- **First-tag time:** time from `uvx semvertag --help` to a first successful auto-tag in CI is under 5 minutes median for a new user with a copy-pasted snippet.
- **Strategy switching:** a user can flip a repo from branch-prefix to Conventional Commits mode with a single config change, no tool replacement.
- **Doctor passes on first run:** `semvertag doctor` passes for ≥80% of new users without further configuration.
- **Specific error feedback:** authentication, scope, and protected-tag errors surface a named, actionable cause (e.g., "GitLab token missing `write_repository` scope") rather than a generic 4xx.
- **Aha-moment confirmation:** at least one external user publicly documents that "one tool, two strategies" was the deciding factor in choosing semvertag over alternatives.

### Business Success (open-source adoption — hypotheses to validate)

**6-month signals (by 2026-11-25):**
- ≥100 PyPI downloads/month, sustained over 30 days
- ≥25 GitHub stars
- ≥1 external contributor PR merged
- ≥1 public mention (blog post, Hacker News comment, Mastodon thread, conference reference)
- Open-issue first-response time: ≤7 days median

**12-month signals (by 2027-05-25):**
- GitHub provider shipped with ≥1 production user outside Raiffeisen
- Listed in ≥1 `awesome-gitlab` or `awesome-ci` curated list
- Published as a GitLab CI Catalog component with non-zero unique-project usage
- ≥1 non-Raiffeisen co-maintainer onboarded with merge rights

### Technical Success

- Zero regressions on internal Raiffeisen `pypelines` shared-CI usage across the rename and config-default cleanup.
- Test coverage ≥85% overall; bump-strategy logic at 100% branch coverage.
- `ty` type check passes on the full codebase; `ruff check --fix` clean.
- All edge cases documented in scope (no tags, non-semver tags, squash vs merge, shallow clones, non-`main` default branch, empty default branch) covered by tests.
- API stability: no breaking CLI flag or config-key changes post-1.0 except via published one-minor-version deprecation cycle.
- CI matrix green on Python 3.10–3.13, Ubuntu latest.

### Measurable Outcomes

| Outcome | Target | Window |
|---|---|---|
| First-tag time (median, new user) | <5 min | At launch |
| PyPI downloads / month | ≥100 sustained | 6 months |
| GitHub stars | ≥25 | 6 months |
| External contributor PRs merged | ≥1 | 6 months |
| Documented migration case studies | ≥3 | 12 months |
| Supported providers | ≥2 (GitLab + GitHub) | 12 months |
| Non-Raiffeisen co-maintainers | ≥1 | 12 months |

### Anti-Goals

- **Total downloads vs. `semantic-release`** — irrelevant; different audience and runtime.
- **Feature parity with `semantic-release`** — explicitly the wrong target; over-reach is what we differentiate against.
- **Internal `raif-autosemver` deprecation** — not measured as a success signal; it depends on Raiffeisen security review of an external PyPI dep, which is gameable and out of community-adoption scope.
- **Paid promotion / developer-advocacy spend** — growth must be content-driven and organic; if it doesn't work organically, the positioning is wrong.

## Product Scope

### MVP — v1.0 (single MIT-licensed repo)

**Core CLI:**
- GitLab provider with no regressions on internal Raiffeisen pipelines
- Conventional Commits bump strategy alongside branch-prefix; selectable per-repo via config
- Auto-detect project from `CI_PROJECT_ID` (GitLab) / `GITHUB_REPOSITORY` (GitHub Actions) / git remote URL; explicit argument as override only
- Major-bump support via Conventional Commits `BREAKING CHANGE` / `!:` (currently absent in internal code; must be added)
- `semvertag doctor` subcommand validating token, scopes, project access, protected-tag config
- Documented and tested behavior on: zero existing tags, non-semver tags (`release-2024-Q1`), squash-merge vs merge-commit histories, shallow clones (`GIT_DEPTH=1`), non-`main` default branches, empty default branch, fast-forward merges

**CI surfaces:**
- GitHub Actions Marketplace action (thin wrapper, official semvertag namespace)
- GitLab CI Catalog component
- Copy-pasteable GitLab CI snippet in README hero, using `CI_JOB_TOKEN` where supported
- Copy-pasteable GitHub Actions snippet in README hero

**Trust surface:**
- Full CI on GitHub Actions: `eof-fixer`, `ruff format`, `ruff check`, `ty` type-check, `pytest` matrix on Python 3.10–3.13, Ubuntu
- Publish workflow on GitHub release: `uv build` + `uv publish` (trusted-publishing preferred over token)
- Docs site on Read the Docs (mkdocs + Material), structure mirroring `modern-di`
- README badges: CI status, PyPI version, supported Python versions, coverage, license
- Demo asciicast/gif of a real run
- `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (intentionally minimal — modern-di skips most of these; semvertag adds them to lower the contributor-trust bar)
- `py.typed` marker, `context7.json`, `CLAUDE.md`
- Migration docs: `docs/migrating-from-semantic-release.md`, `docs/migrating-from-go-semrel-gitlab.md`, `docs/migrating-from-rightbrain-auto-semver.md`
- Published API stability policy: CLI flags and config keys SemVer-stable post-1.0; deprecations carry one-minor-version warning

**Discovery:**
- README H1 and meta description include "GitLab CI", "auto tag", "semver"
- Two launch posts (engineering blog or dev.to): the migration story and the "we left semantic-release" story
- Handle reservation across PyPI, GitHub org, Read the Docs, GitLab CI Catalog namespace before announcement

### Growth Features (Post-MVP, v1.x)

- GitHub provider (shipped in the standard install — no optional-extras dance)
- Bitbucket provider (shipped in the standard install — no optional-extras dance)
- File-based configuration (FR23, FR24): `[tool.semvertag]` in `pyproject.toml` and standalone `.semvertag.toml`, enabling per-repo overrides of strategy-internal collection mappings (FR13, FR16)
- Dry-run mode and `--explain` output for debugging bump decisions
- Pre-release / RC tag support (`-rc.1`, `-beta.2`)
- `mise` / `asdf` plugin for polyglot DevOps audiences
- Pre-commit hook integration (local pre-push variant)
- Per-branch strategy switching (v1.0 supports per-repo only)
- Onboard a second non-Raiffeisen maintainer with merge rights

### Vision (Future, 2–3 years)

- semvertag is the uncontroversial default answer to "how do I auto-tag in GitLab CI?"
- Active maintainer pool of 3–5 including ≥1 non-Raiffeisen contributor; bus factor mitigated
- Internal `raif-autosemver` retired; Raiffeisen runs the public OSS build via vendoring or mirroring
- GitLab CI Catalog component with broad cross-org usage
- Optional v2.0 family-of-repos pattern (`semvertag-gitlab`, `semvertag-github`, etc.) if provider count grows beyond ~4
- Reputation as the *boring, reliable* option in a space dominated by ambitious-but-fragile alternatives

## User Journeys

### Journey 1: Primary user, success path — First-time GitLab CI adoption

**Persona:** Petr, SRE at a midsize fintech company running self-hosted GitLab 17. Maintains shared CI templates used by 15 product repos. Has been hand-tagging releases for two years and is tired of the manual toil. Already migrated their CI from Jenkins to GitLab CI six months ago; team uses GitFlow branch prefixes (`feature/`, `bugfix/`, `hotfix/`) consistently.

**Opening:** Petr is on his third coffee, looking at a thread of Slack messages asking "why didn't you tag the release yesterday?" He decides to spend the morning automating this. He searches "gitlab ci auto tag semver" — `go-semrel-gitlab` looks abandoned, `semantic-release` wants him to add `package.json` to a Python repo, `python-semantic-release` requires he migrate every team to Conventional Commits this week. The third result down is `semvertag`. README hero shows a 4-line `.gitlab-ci.yml` snippet. *He cautiously believes it.*

**Rising action:** Petr copies the snippet into one repo. Sets `SEMVERTAG_TOKEN` from his existing GitLab PAT. Runs `uvx semvertag doctor` locally first — it reports: token OK, `api` scope OK, `write_repository` scope OK, project access OK, protected-tag rule allows the bot. Commits the CI change. Merges a `bugfix/` branch to test. CI runs in 18 seconds. A tag `1.4.3` appears.

**Climax:** Petr stares at the tag. *That actually worked on the first try.* He runs the same recipe on three more repos that afternoon. All pass `doctor`. All tag correctly.

**Resolution:** End of day, ten of his fifteen repos are now self-tagging. The Slack thread goes silent. He drafts a one-paragraph announcement to his team and considers writing a blog post.

**Capabilities this journey requires:**
- README hero with copy-pasteable CI snippet, no scrolling
- `semvertag doctor` subcommand with named, actionable validation output
- Auto-detect project from `CI_PROJECT_ID` — no `<project_id>` argument needed in CI
- Branch-prefix bump strategy as the default for the CI snippet
- Friendly error messages that name the missing token scope, not a generic 403
- Sub-30-second CI runtime so users don't feel the cost

### Journey 2: Primary user, edge case — Mid-migration team lead

**Persona:** Marina, staff platform engineer at a series-B SaaS company. Six months ago she announced a migration from GitFlow to Conventional Commits. Five new repos use `feat:` / `fix:`; thirty legacy repos still use `feature/` / `bugfix/`. She's already running `semvertag` on the legacy repos via Petr's recipe (different company, same hero). Today she's flipping the first pilot repo to Conventional Commits.

**Opening:** Marina drafts the migration RFC. The hardest section was "tooling." The previous platform engineer evaluated `semantic-release` last quarter and concluded it would force a flag-day migration. Marina found `semvertag` two weeks ago and pinned it to the RFC: "we can migrate one repo at a time without changing tools." Today's the test.

**Rising action:** She opens the pilot repo's GitLab CI settings → CI/CD variables. The legacy repos run semvertag with branch-prefix as the default strategy. For the pilot, she adds one project variable: `SEMVERTAG_STRATEGY=conventional-commits`. No code change, no config-file commit — the variable is scoped to the pilot project only. She then commits her first Conventional Commits change with `feat: switch to conventional commits strategy`. Merges to main.

**Climax:** semvertag tags `2.1.0`. She inspects the CI log: `Detected strategy: conventional-commits. Bump: minor (feat: switch to conventional commits strategy). Created tag 2.1.0.` The next day, a teammate merges a `fix:` PR. It tags `2.1.1`. The day after, a teammate accidentally writes `Fixed thing`. semvertag logs `No conforming commit found. Skipping.` and exits 0 — no tag, no failure. Marina nods.

**Resolution:** Over the next three weeks, she flips four more repos by adding the same project-level CI variable each time — five clicks per repo, no toolchain change, no config file to commit. By end of quarter, she has both strategies running across the org with no toolchain divergence. She writes the migration post the brief promised — and tags semvertag in it.

**Capabilities this journey requires:**
- Per-repo strategy selection via the `SEMVERTAG_STRATEGY` environment variable, settable as a project-level CI variable in GitLab CI (and equivalents in GitHub Actions / Bitbucket Pipelines) — no file edit, no commit
- Conventional Commits parser supporting `feat:`, `fix:`, `BREAKING CHANGE`, and `!` suffix
- `--explain`-style log output even without the flag at default verbosity ("Detected strategy: ..., Bump: ...")
- Graceful skip-on-no-conforming-commit (exit 0, log a reason, do not error)
- No conflicting / overlapping bump rules between strategies

*(File-based per-repo configuration via `.semvertag.toml` / `[tool.semvertag]` arrives in v1.x and will support the same journey via a single-key file edit; in v1.0 the equivalent is the CI variable.)*

### Journey 3: Secondary user — Terraform module maintainer

**Persona:** Dani, infra engineer maintaining a public Terraform module on GitHub. Pushes a couple of releases a month. Currently runs a hand-cobbled bash script that increments a version file and pushes a tag. The script broke last month when she renamed the default branch from `master` to `main`. She wants to retire it.

**Opening:** Dani searches "github actions auto semver python" — most results are heavy (`python-semantic-release` wants to write a changelog, publish to PyPI). She doesn't need any of that; she only needs a tag. She finds `semvertag` listed in `awesome-ci` under "tag-only." Reads the GitHub Actions Marketplace listing. Single input: `strategy`. Done.

**Rising action:** Adds a 7-line workflow file using the marketplace action. Pushes. The workflow fails: `Token missing 'contents: write' permission.` She adds `permissions: contents: write` to the workflow. Reruns. Tag `0.4.2` lands.

**Climax:** *That's all it does.* She deletes her bash script with prejudice.

**Resolution:** She comments on a recurring "how do you auto-tag" question in the Terraform community Slack with a link to the workflow file. Three replies follow asking how it handles `BREAKING CHANGE`. The thread becomes the seed of an external blog post she writes the following weekend.

**Capabilities this journey requires:**
- GitHub Actions Marketplace action published in v1.0
- Auto-detect from `GITHUB_REPOSITORY` env var; no repo-ID argument required
- Honor the GitHub Actions default token (`GITHUB_TOKEN`) with `contents: write`
- Error message naming the exact missing GitHub permission, not a generic 403
- Listing in `awesome-ci` (discovery commitment from the brief)
- Tool that does *only* tagging — no changelog, no publish, no release notes — so secondary users can adopt without unwanted scope

### Journey 4: Contributor — Adding Bitbucket provider

**Persona:** Sasha, freelance DevOps consultant. One of her clients runs Bitbucket Cloud. She uses semvertag on her other clients' GitLab and GitHub repos and wants the same tool on Bitbucket. semvertag's v1.x roadmap lists Bitbucket but it's not shipped. She files an issue, gets a response from a maintainer in 4 days: "We'd take a PR — follow the GitLab provider as the model."

**Opening:** Sasha clones the repo. Reads `CONTRIBUTING.md`: dev setup in 4 commands (`uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check`). Reads the GitLab provider source — single file, ~200 lines, frozen dataclass, clear seam where the provider abstraction lives.

**Rising action:** Sasha sketches a `BitbucketProvider` mirroring `GitLabProvider`. Writes tests with `httpx2.MockTransport`. Pushes a draft PR after a weekend. A maintainer leaves three review comments. She addresses them. CI matrix turns green.

**Climax:** PR merges. The Bitbucket provider ships in the next release as part of the standard install — no separate extras package to coordinate. Sasha gets credited in the changelog.

**Resolution:** She rolls out Bitbucket support to her client the same week. Files two follow-up issues for edge cases she's discovered. One gets resolved, the other is labeled "good first issue" and picked up by another contributor a month later.

**Capabilities this journey requires:**
- Provider abstraction that's *legible to a new contributor* — one file per provider, no spreading logic across modules
- `CONTRIBUTING.md` with a working 4-command dev-setup recipe
- Tests use `httpx2.MockTransport` (no live API calls); contributor can run the full suite offline
- New providers ship in the standard install — no `[github]` / `[bitbucket]` extras to wire up in `pyproject.toml`
- CI matrix runs on PRs from forks, not only on `main` pushes
- Issue templates that funnel "new provider request" toward a known acceptance path

### Journey Requirements Summary

Aggregating the capabilities surfaced across the four journeys:

**First-five-minutes path (Journeys 1, 3):**
- Copy-pasteable CI snippets (GitLab + GitHub) in README hero
- `semvertag doctor` for one-shot pre-flight validation
- Auto-detected project context from CI env / git remote
- Named, actionable error messages on auth/scope/permission failures
- Sub-30-second CI runtime

**Migration-aware operation (Journey 2):**
- Per-repo strategy selection via the `SEMVERTAG_STRATEGY` env var (settable as a project-level CI variable) in v1.0; file-based per-repo config (TOML) arrives in v1.x
- Conventional Commits parser with `feat:`, `fix:`, `BREAKING CHANGE`, `!` support
- Default verbose-enough log output (`Detected strategy: ..., Bump: ..., Created tag ...`)
- Graceful skip with exit 0 + reason when no conforming commit found

**Tag-only audience (Journey 3):**
- GitHub Actions Marketplace action in v1.0
- Strict scope discipline: no changelog, no publish, no release notes
- Listing in `awesome-ci` / `awesome-gitlab` as a discovery commitment

**Contributor enablement (Journey 4):**
- Provider abstraction as one-file-per-provider
- `CONTRIBUTING.md` with executable 4-command dev setup
- Offline-runnable test suite via `httpx2.MockTransport`
- Optional-extras packaging pattern
- CI on fork PRs
- Issue templates funneling provider-request contributions

**Cross-cutting non-functionals revealed:**
- Specific, named error messages (named token scope, named permission) instead of generic HTTP codes
- API stability: configs and CLI flags don't change underneath users post-1.0
- Discoverability via README SEO, `awesome-*` listings, and marketplace presences

## CLI Tool Specific Requirements

### Project-Type Overview

semvertag is a non-interactive, scriptable CLI optimized for execution from CI environments (GitLab CI, GitHub Actions, Bitbucket Pipelines) and shell pipelines. Single verb (`semvertag`) with one supporting subcommand (`semvertag doctor`). No TTY assumptions, no interactive prompts, no progress spinners that break CI logs. Local-developer use is supported but secondary.

The CLI is the primary user surface; the underlying Python package is also pip-installable for advanced users who want to embed the provider abstraction in their own scripts, but the API surface for that use case is *not* covered by the v1.0 stability policy.

Architecture-level concerns (DI framework choice, provider seam shape, module renames, removed-before-publish items) are captured separately in the **Architecture Notes** section below, so this section can focus on the user-facing CLI contract.

### Command Structure

**Primary invocation (no required arguments in CI):**
```
semvertag                                # auto-detect project + provider + strategy
semvertag --project-id 12345             # explicit project override
semvertag --strategy conventional-commits # explicit strategy override
semvertag --dry-run                      # post-v1.0 — preview without creating a tag
```

**Subcommands:**
```
semvertag doctor                         # validate token, scopes, project access, tag rules
semvertag --version                      # version banner
semvertag --help                         # help (typer default)
semvertag --install-completion           # install shell completion (bash/zsh/fish/powershell)
```

**Flag precedence (highest wins):**
1. CLI flags (`--project-id`, `--strategy`, `--token`, ...)
2. Environment variables (`SEMVERTAG_<KEY>`, plus provider-native fallbacks like `CI_PROJECT_ID`, `GITHUB_REPOSITORY`)
3. Built-in defaults

*(File-based config — `.semvertag.toml` or `[tool.semvertag]` in `pyproject.toml` — is a v1.x feature; when added, it slots between env vars and built-in defaults per FR27.)*

**Explicitly NOT in v1.0 command surface:**
- No `init`, no `migrate`, no `lint` subcommands — every option is a flag, not a verb
- No subcommand nesting (no `semvertag config get foo`); the tool is one verb
- No interactive `setup` wizard — `semvertag doctor` is the only diagnostic surface

### Output Formats

**Default (human, stdout):** `rich`-formatted, single-line per event:
```
Detected strategy: conventional-commits
Bump: minor (feat: switch to conventional commits strategy)
Created tag 2.1.0 on commit a2b4d12
```

**`--json` (machine, stdout):**
```json
{"strategy": "conventional-commits", "bump": "minor", "tag": "2.1.0", "commit": "a2b4d12", "status": "created"}
```

**`--quiet`:** suppress non-error informational output during the run. The final result is still emitted in the chosen output format — so `--quiet --json` produces a single-line JSON envelope on stdout with no progress chatter. Exit code remains meaningful.

**Stream discipline:**
- All informational output → **stdout**
- All errors → **stderr**
- No mixing — pipelines piping stdout to a parser must not encounter error chatter.

**Exit codes (stable post-1.0):**
| Code | Meaning |
|---|---|
| 0 | Success (tag created) OR intentional no-op (no merge commit, no conforming commit, already tagged) — distinguishable via stdout |
| 1 | Generic failure (unexpected error) |
| 2 | Configuration error (invalid strategy, malformed config, missing required env var) |
| 3 | Authentication or permission error (bad token, missing scope, protected-tag rule blocks) |
| 4 | Provider API error (network failure, rate limit, 5xx) |

The choice of "intentional no-op = exit 0" is deliberate — CI jobs should not fail because a non-merge commit was pushed.

### Config Schema

**Configuration sources (v1.0):**

v1.0 is configured exclusively via CLI flags and environment variables. There is no configuration-file layer; file-based config via `[tool.semvertag]` in `pyproject.toml` and standalone `.semvertag.toml` is a v1.x growth feature (see FR23, FR24). The forward-compatibility constraints for that layer are codified in FR28.

**Environment variables (all prefixed `SEMVERTAG_`):**
| Variable | Maps to |
|---|---|
| `SEMVERTAG_TOKEN` | provider API token (highest precedence for credential) |
| `SEMVERTAG_STRATEGY` | `branch-prefix` or `conventional-commits` |
| `SEMVERTAG_PROVIDER` | `gitlab`, `github` (v1.x), `bitbucket` (v1.x) |
| `SEMVERTAG_GITLAB_ENDPOINT` | self-hosted GitLab URL (overrides default `https://gitlab.com`) |
| `SEMVERTAG_DEFAULT_BRANCH` | override auto-detected default branch |

**Provider-native credential fallbacks (no `SEMVERTAG_` prefix):**
- GitLab: `CI_JOB_TOKEN` (GitLab 16.0+, used by default in GitLab CI), `GITLAB_TOKEN`
- GitHub: `GITHUB_TOKEN` (default in GitHub Actions)
- Bitbucket (v1.x): `BITBUCKET_TOKEN`

If `SEMVERTAG_TOKEN` is unset, the appropriate provider-native variable is consulted automatically — no extra config needed in standard CI.

**Strategy-internal collection overrides (deferred):**

Strategy selection in v1.0 is a single-value setting (`SEMVERTAG_STRATEGY=branch-prefix|conventional-commits`); strategy-internal mappings (which branch prefix produces which bump, which Conventional Commits type counts as minor, etc.) use built-in defaults. Per-repo override of those collection-shaped mappings (FR13, FR16) is not expressible as flat env vars and arrives with file-based config in v1.x.

### Scripting Support

- **Non-interactive everywhere.** No prompts, no `input()`, no TTY detection that changes behavior beyond color output.
- **Stable exit codes** documented above; covered by API stability policy.
- **Stable JSON schema** for `--json` output, versioned via a top-level `"schema_version": "1.0"` key. Schema changes go through the deprecation cycle.
- **Composable:** designed for use inside shell pipelines, GitLab CI `script:` blocks, GitHub Actions `run:` blocks. Example:
  ```bash
  semvertag --json | jq -r '.tag' | xargs -I {} echo "Tagged: {}"
  ```
- **Doctor output** is also JSON-capable (`semvertag doctor --json`) so CI dashboards can scrape pre-flight status.
- **Idempotent reruns:** running `semvertag` on the same commit twice is safe — the second run detects the existing tag and exits 0 with `"already_tagged"`.
- **Shell completion** for bash, zsh, fish, and PowerShell via Typer's built-in `--install-completion`.

## Architecture Notes

This section captures architecture-level decisions and implementation guidance that inform downstream design but are not user-facing requirements. Downstream architecture work should treat these as input rather than as binding requirements — they describe HOW the system is built, not WHAT it must do.

### Technical Architecture Considerations

- **Built on Typer** (currently `modern-di-typer` for DI wiring; the DI framework is an internal detail, not part of the public CLI contract).
- **Provider abstraction** lives behind a `Provider` protocol; v1.0 ships one implementation (`GitLabProvider`), v1.x adds `GitHubProvider` and `BitbucketProvider` in the standard install.
- **Settings layer:** `pydantic-settings` for env-var-driven configuration. (File-based configuration via TOML is a v1.x feature — see FR23, FR24.)
- **Output layer:** `rich` for human output; `json.dumps` for machine output. No third-party JSON library.
- **Distribution:** `uvx`-runnable (zero-install) is the headline CI path. `pip install semvertag` is the canonical install path for local dev and pinned CI.

### Implementation Considerations

- **Module renames:** existing internal `autosemver/` package → `semvertag/`. Existing `AUTOSEMVER_` env prefix → `SEMVERTAG_`. Both must be migrated in lockstep with the internal Raiffeisen pipelines.
- **Provider seam:** factor the current monolithic `AutosemverUseCase` into a `Provider` protocol + a `BumpStrategy` protocol. GitLabProvider stays as the v1.0 implementation; the seam is what makes Journey 4 (Bitbucket contributor) feasible.
- **Major-bump support:** absent from current code; required for v1.0 Conventional Commits compliance. Add parsing for `!` suffix and `BREAKING CHANGE:` footer.
- **Default-branch detection:** current code uses GitLab's `default_branch` field from the project API. Same approach for GitHub (`default_branch` from repo API). Explicit override via `SEMVERTAG_DEFAULT_BRANCH` covers self-hosted edge cases. (`git symbolic-ref refs/remotes/origin/HEAD` as a local-dev fallback is deferred to a v1.x `--offline` mode — see FR9.)
- **Shared HTTP client across providers:** all providers use `httpx2` directly against each provider's REST API — no per-provider SDK dependency, no `[github]` / `[bitbucket]` optional extras. This keeps the dependency surface minimal and the standard install complete.
- **Removed before publish:** the Raiffeisen-specific Dockerfile, the hardcoded `https://gitlabci.raiffeisen.ru` default in settings, and the internal Artifactory `[[tool.uv.index]]` blocks in `pyproject.toml`.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach: Trust-and-Adoption MVP.**

The conventional "problem-solving MVP" framing doesn't fit here — a working tagger already exists internally as `raif-autosemver`. The minimum viable thing for the *public* version isn't "code that creates tags"; it's *"code that creates tags PLUS enough trust signals that a stranger will adopt it over an established alternative."*

The implication: v1.0 must over-invest (relative to the small codebase) in trust artifacts — CI badges, docs, migration guides, marketplace listings, demo gif, security policy — because a 1-author repo with none of those loses to `python-semantic-release` in 10 seconds, no matter how clean the code is. The journeys (especially Journey 3: Dani the Terraform maintainer) confirm this is the binding constraint.

**Validated learning loop:**
- Ship v1.0 with one provider (GitLab), dual strategy, and full trust surface
- Listen for the *aha-moment confirmation* metric — does anyone publicly write that dual-mode was the reason?
- If yes within 6 months: continue investing in v1.x providers (GitHub, Bitbucket) per the brief's roadmap
- If no within 6 months: the dual-mode positioning is wrong — pivot the narrative toward GitLab-native + runtime-minimal angles before adding providers

**Resource requirements:**
- v1.0 implementation: ~2 weeks of focused work for a single senior Python engineer familiar with the existing codebase (Artur). Bulk is trust surface (docs, CI, marketplace listings), not code.
- v1.0 governance: 1 additional reviewer to land the API stability policy and act as bus-factor partner
- Ongoing: 1–2 hours/week of maintenance + community management until the second co-maintainer is recruited

### MVP Feature Set (Phase 1 — v1.0)

The full v1.0 capability list is enumerated in **Product Scope → MVP — v1.0** above. This section adds the journey-priority ordering that informs sequencing during implementation:

**Core user journeys supported (in priority order):**
1. **Journey 1 — First-time GitLab CI adoption** (Petr): the primary success path; everything else flows from this working
2. **Journey 2 — Mid-migration team lead** (Marina): the differentiation moment; without this, there's no story to tell
3. **Journey 3 — Tag-only secondary user** (Dani via GitHub Actions Marketplace): broadens addressable audience beyond GitLab
4. **Journey 4 — Contributor adding Bitbucket provider**: the bus-factor mitigation path; v1.0 must make this *possible* even if Bitbucket itself doesn't ship until v1.x

### Post-MVP Features

v1.x and Vision-horizon items are enumerated in **Product Scope → Growth Features** and **Product Scope → Vision** above. No additional scope is introduced in this section; the contents there are the authoritative roadmap.

### Risk Mitigation Strategy

**Technical risks:**

| Risk | Mitigation |
|---|---|
| Provider seam refactor regressing internal pipelines | Port the existing test suite to `httpx2.MockTransport` as part of the seam refactor; add coverage for the refactored seam before module rename; run the new build against `pypelines`' shared CI in shadow mode before flipping the canonical dependency |
| Major-bump parser ambiguity in Conventional Commits | Pin to the standard's published grammar; ship reference cases as snapshot tests; document the precedence rules explicitly in `docs/conventional-commits.md` |
| Default-branch detection failures on weirdly-configured repos | Two-layer resolution: provider API → explicit `SEMVERTAG_DEFAULT_BRANCH` override; `semvertag doctor` surfaces which layer was used |
| Python 3.10+ floor breaking on enterprise stuck on 3.9 | `uvx` in CI removes the host Python dep entirely; local-dev users on 3.9 get a clear error pointing to `uvx` as the workaround |

**Market risks:**

| Risk | Mitigation |
|---|---|
| Differentiation collapse if `semantic-release` adds branch-prefix mode | Lead the brand on GitLab-native + runtime-minimal angles in parallel with dual-mode; monitor `semantic-release` GH issues quarterly; have a "leg 2/3 fallback narrative" ready |
| Adoption fails to clear the 6-month threshold | Validated-learning loop above triggers a positioning pivot at the 6-month mark, not a quiet death |
| GitLab ships native auto-tagging | Monitor GitLab's CI public roadmap; if announced, accelerate Conventional Commits + GitHub differentiation; pivot to "best multi-provider tagger" framing |
| Confusion with dormant PyPI `autosemver` / active `RightBrain/auto-semver` | Mitigated by the rename to `semvertag`; migration docs explicitly link both predecessors |

**Resource & governance risks:**

| Risk | Mitigation |
|---|---|
| Bus factor of one team at one bank | Treat "recruit non-Raiffeisen co-maintainer" as a 6-month deliverable; publish a "we will never add X" anti-feature list to make contribution scope legible; default-respond to non-trivial issues within 7 days |
| Raiffeisen legal/IP clearance blocks launch | Begin IP review in parallel with v1.0 implementation, not after; the rename + Raiffeisen-default removal also reduces clearance complexity |
| Raiffeisen security review delays internal adoption of public package | Out of scope as a success metric (already removed from 12-month signals); a separate internal-vendoring path can run on its own timeline |
| Naming collision lawsuit / trademark issue | Low likelihood given the rename to `semvertag` (PyPI-verified free, generic-descriptive name); SECURITY.md and CONTRIBUTING.md include CLA/DCO language to reduce IP ambiguity on contributions |
| Maintainer time available drops below 1–2 hrs/week | Documented anti-feature list and stability policy mean the project can sit idle for months without users losing trust; defaults age well |

### Launch Decisions Pending

Launch-meta decisions handed off by the product brief or surfaced during PRD review. None block implementation; all should resolve before public announcement.

| Decision | Source | Target resolution | Status |
|---|---|---|---|
| GitHub org choice (personal user vs. dedicated `semvertag-dev` org vs. Raiffeisen public org) | Brief open question; affects handle reservation and bus-factor narrative | Before handle reservation (pre-announcement) | Open |
| Dormant PyPI `autosemver` sunset signal (quietly ignore vs. proactively contact the maintainer) | Brief open question | Before PyPI publish | Open |
| "Used in production at Raiffeisen since [date]" line in README | Brief distillate open question; IP-clearance-dependent | After IP clearance, before announcement | Open |
| Frame "existing tools over-reach" as a third explicit problem bullet in the Executive Summary problem statement (currently implicit via scope discipline + anti-goals) | PRD review observation | Optional polish before announcement | Open |

## Functional Requirements

These FRs are the binding capability contract for v1.0 unless otherwise noted (FRs marked *v1.x* belong to post-MVP phases per the Scoping section). Any capability not listed here will not exist in the final product.

### Tag Creation

- **FR1:** System creates a semver tag on the default branch's latest commit when invoked.
- **FR2:** System reads the most recent commit on the default branch to determine bump candidacy.
- **FR3:** System skips tag creation without error (exit 0, informative log) when the latest commit is not a merge commit or contains no signal conforming to the active bump strategy.
- **FR4:** System skips tag creation without error when the latest commit is already tagged.
- **FR5:** System reports the created tag name, the source commit SHA, and the chosen bump strategy in its output.
- **FR6:** System is idempotent — repeated invocations on the same commit produce no duplicate tag and exit success.
- **FR7:** System handles repositories with zero pre-existing tags by skipping with an informative message and exit 0.
- **FR8:** System ignores non-semver-conforming tags (e.g. `release-2024-Q1`) when determining the previous version, finding the latest valid semver tag.
- **FR9:** System detects the default branch from the active provider's API, with `SEMVERTAG_DEFAULT_BRANCH` as an explicit override. (Local-dev / `--offline` operation without a provider context is deferred to v1.x.)
- **FR10:** System operates correctly on repositories using shallow CI clones by sourcing tag history from the provider API rather than the local git tree.

### Bump Strategy

- **FR11:** User can select the bump strategy (`branch-prefix` or `conventional-commits`) per repository via configuration.
- **FR12:** System parses GitFlow-style branch prefixes from merge commit messages to determine bump level when the branch-prefix strategy is active.
- **FR13:** *(v1.x)* User can override the default branch-prefix → bump-level mappings via configuration (e.g., add custom prefixes, change which prefix produces which bump). Requires the v1.x file-based config layer (FR23/FR24) — collection-shaped overrides are not expressible as flat env vars.
- **FR14:** System parses Conventional Commits headers from merge commit messages to determine bump level when the Conventional Commits strategy is active.
- **FR15:** System detects major bumps via the `!` suffix or `BREAKING CHANGE:` footer when the Conventional Commits strategy is active.
- **FR16:** *(v1.x)* User can extend or override the Conventional Commits → bump-level mappings via configuration (e.g., treat `perf:` as minor, add custom commit types). Requires the v1.x file-based config layer (FR23/FR24) — collection-shaped overrides are not expressible as flat env vars.

### Provider Integration

- **FR17:** System creates tags on GitLab projects via the GitLab REST API (v1.0).
- **FR18:** System creates tags on GitHub repositories via the GitHub REST API (*v1.x*).
- **FR19:** System creates tags on Bitbucket Cloud repositories via the Bitbucket REST API (*v1.x*).
- **FR20:** System auto-detects the active provider from CI environment variables (`CI_PROJECT_ID`, `GITHUB_REPOSITORY`, etc.) and falls back to the git remote URL.
- **FR21:** User can override the auto-detected provider via the `--provider` flag or `provider` config key.
- **FR22:** A contributor can add a new provider by implementing the documented `Provider` protocol in a single file, following the GitLab provider as the reference shape. New providers ship in the standard install — no optional-extras packaging or per-provider SDK gating.

### Configuration & Environment

- **FR23:** *(v1.x)* User can configure semvertag via a `[tool.semvertag]` block in `pyproject.toml` for Python projects.
- **FR24:** *(v1.x)* User can configure semvertag via a standalone `.semvertag.toml` file in the repository root for provider-agnostic projects.
- **FR25:** User can run semvertag entirely via environment variables and CLI flags — the only supported configuration surface in v1.0.
- **FR26:** System reads provider-native credential environment variables (`CI_JOB_TOKEN`, `GITLAB_TOKEN`, `GITHUB_TOKEN`, `BITBUCKET_TOKEN`) as fallbacks when `SEMVERTAG_TOKEN` is unset.
- **FR27:** System resolves effective configuration with the precedence: CLI flags > environment variables > built-in defaults. (When file-based config arrives in v1.x per FR23/FR24, it slots between environment variables and built-in defaults.)
- **FR28:** When file-based configuration arrives in v1.x (FR23, FR24), the loader rejects templating constructs (e.g., `.semvertag.toml.j2`), env-var interpolation inside TOML values, and remote/URL-loaded config — exiting with a configuration error (exit code 2). This is a forward-compatibility policy that constrains the v1.x file layer at design time; v1.0 has no file layer for the policy to act on.

### Diagnostics & Validation

- **FR29:** User can run `semvertag doctor` to validate token presence, token scopes, project access, default-branch detection, and protected-tag rules before first use.
- **FR30:** System reports each pre-flight check with a named, actionable cause on failure (e.g., `Token is missing the 'write_repository' scope`, not a generic `403`).
- **FR31:** User can run `semvertag doctor --json` to obtain machine-readable pre-flight status suitable for CI dashboards.
- **FR32:** System reports the resolved configuration source for each value (CLI / env / config / default) as part of doctor output, with secrets redacted.

### CLI Surface & Output

- **FR33:** User invokes the primary action with no required positional arguments when running inside a recognized CI environment.
- **FR34:** User can override the active project via `--project-id` or the equivalent provider-native flag (`--repository`).
- **FR35:** User can request machine-readable output via `--json`, returning a schema-versioned envelope (top-level `schema_version` key).
- **FR36:** User can suppress non-error informational output during the run via `--quiet` — the final result is still emitted in the chosen output format (so `--quiet --json` composes), and exit code remains meaningful.
- **FR37:** System uses stable, documented exit codes: 0 (success or intentional no-op), 1 (generic failure), 2 (configuration error), 3 (auth or permission error), 4 (provider API error).
- **FR38:** System writes informational output to stdout and error output to stderr with no interleaving.
- **FR39:** User can install shell completion for bash, zsh, fish, and PowerShell via `semvertag --install-completion`.

### CI Distribution

- **FR40:** User can adopt semvertag in GitLab CI by including the published GitLab CI Catalog component (v1.0).
- **FR41:** User can adopt semvertag in GitHub Actions via the published Marketplace action wrapper (v1.0).
- **FR42:** User can invoke semvertag with zero installation footprint via `uvx semvertag` in any CI environment where `uv` is available.

### Documentation & Trust

- **FR43:** User can read a published migration guide for switching from `semantic-release`, `go-semrel-gitlab`, or `RightBrain/auto-semver`, each with a config-mapping table.
- **FR44:** User can rely on the published API stability policy: CLI flags, config keys, exit codes, and JSON output schema are SemVer-stable post-1.0, with deprecations carrying a one-minor-version warning.
- **FR45:** User can discover semvertag via SEO-tuned README content (containing "GitLab CI", "auto tag", "semver") and via published presence on the GitHub Actions Marketplace and GitLab CI Catalog. (`awesome-gitlab` / `awesome-ci` listing is tracked as a Success Criterion outcome at 12 months, not an FR — outside the team's direct control.)
- **FR46:** A contributor can set up a development environment using documented commands in `CONTRIBUTING.md` (`uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check`) and run the full test suite offline using `httpx2.MockTransport` fixtures.

## Non-Functional Requirements

Quality attributes for v1.0. Each NFR is measurable and bound to a specific test or observation point. NFRs that don't apply to a single-invocation CI CLI (scalability, accessibility) are intentionally omitted to avoid requirement bloat.

### Performance

- **NFR1:** End-to-end CI runtime (process start to tag created) is **≤30 seconds** at the 95th percentile for a repository with <500 existing tags, measured on a warm `uvx` cache and a healthy provider API.
- **NFR2:** Cold-start `uvx semvertag --help` returns in **≤5 seconds** on a fresh CI runner (no `uv` cache), including dependency resolution and import time.
- **NFR3:** First-tag time — measured from a new user starting `uvx semvertag --help` to a successful auto-tag in their CI — is **<5 minutes median**, measured via user telemetry from migration-doc readers.
- **NFR4:** `semvertag doctor` completes in **≤10 seconds** against a single project, including all four validation checks (token, scopes, access, protected-tag rules).

### Reliability

- **NFR5:** Identical inputs produce identical outputs across runs — running `semvertag` twice on the same commit produces no duplicate tag and exits 0 both times (idempotency, formalized from FR6).
- **NFR6:** System exits 0 with an informative message on every documented benign no-op condition (no merge commit, no conforming Conventional Commit, already-tagged, no existing tags) — these never produce a non-zero exit code.
- **NFR7:** System retries transient provider API failures (HTTP 5xx, connection reset, rate-limit 429) with exponential backoff, up to 3 retries with a maximum total wall time of 30 seconds, before exiting with code 4.
- **NFR8:** System fails closed on auth/scope errors — never attempts a tag creation when pre-flight validation cannot succeed. Exit code 3 is always paired with a named cause.
- **NFR9:** No regressions on internal Raiffeisen `pypelines` shared-CI usage: prior to public v1.0 release, the `semvertag` build runs in shadow mode against the same triggers as `raif-autosemver` for at least one full release cycle (~2 weeks) with byte-identical tag outcomes.

### Security

- **NFR10:** Tokens are never written to stdout, stderr, log files, or `semvertag doctor` output — all credential references are redacted to `***` or the last 4 characters only.
- **NFR11:** Configuration sources are local-only: v1.0 supports CLI flags and environment variables; v1.x adds file-based config (FR23, FR24) under the FR28 forward-compatibility policy — no remote/URL-loaded config, no in-file templating, no env-var interpolation inside TOML. Violations exit with configuration error (exit code 2).
- **NFR12:** Dependency surface is audited at every release: published GitHub releases include a `pip-audit` clean-report attestation; transitive dependencies are pinned in `uv.lock` and reviewed before any minor-version bump.
- **NFR13:** Released PyPI artifacts are signed via PyPI trusted publishing (no long-lived API tokens in CI secrets); signatures are verifiable via `pip install --require-hashes` against the published `uv.lock`.
- **NFR14:** A documented vulnerability-disclosure path exists in `SECURITY.md`: private reporting via GitHub Security Advisories, 90-day disclosure timeline, no public bug bounty.

### Integration

- **NFR15:** GitLab provider supports GitLab CE/EE **15.0 and later**, including both `gitlab.com` and self-hosted instances; tested against the latest current major + previous major at CI time.
- **NFR16:** GitHub provider (v1.x) supports `github.com` and GitHub Enterprise Server **3.10 and later**.
- **NFR17:** Bitbucket provider (v1.x) supports **Bitbucket Cloud only** at v1.x; Bitbucket Data Center is out of scope.
- **NFR18:** System operates correctly inside the documented CI environments: GitLab CI (16.0+), GitHub Actions (any active runner version), Bitbucket Pipelines (v1.x).
- **NFR19:** System honors provider-native context detection without manual configuration in the four canonical scenarios: GitLab CI with `CI_JOB_TOKEN`, GitLab CI with PAT, GitHub Actions with `GITHUB_TOKEN`, Bitbucket Pipelines with `BITBUCKET_TOKEN` (v1.x).
- **NFR20:** JSON output schema (`--json`) is versioned and stable — `schema_version: "1.0"` for the v1.0 release; changes follow the API stability policy.

### Maintainability

- **NFR21:** Core codebase (excluding tests, docs, generated files) stays under **1,500 lines of Python** for v1.0 — enforced as a soft target visible in CI to keep "small/opinionated" honest.
- **NFR22:** Test coverage is **≥85% line coverage** overall; bump-strategy parsing logic is **100% branch coverage**; measured by `pytest-cov` and gated in CI.
- **NFR23:** `ty` type-check passes with no `# ty: ignore` comments outside of documented external-API boundaries; `ruff check` passes with the `ALL` ruleset (current `pyproject.toml` configuration retained, minimal added ignores).
- **NFR24:** Mean issue first-response time is **≤7 days** for the first 12 months post-launch; tracked via GitHub issue labels and a monthly self-audit recorded in `MAINTENANCE.md` or equivalent.
- **NFR25:** Public CLI flag and config-key surface is **SemVer-stable** post-1.0: removal or breaking change requires (a) a one-minor-version deprecation warning, (b) a documented migration path in the changelog. Internal modules (`semvertag.providers.*`, `semvertag.strategies.*`) are explicitly *not* covered by this policy.
- **NFR26:** Dependency-update cadence is at least quarterly: `uv lock --upgrade` runs on a schedule (CI cron) and produces a PR; if no maintainer merges within 30 days, the build remains on the prior lock to avoid silent drift.

### Compatibility

- **NFR27:** Supports **Python 3.10, 3.11, 3.12, 3.13** at launch — all tested in CI matrix on every PR.
- **NFR28:** Runs on **Linux (Ubuntu latest LTS)** as the canonical CI target. macOS and Windows are best-effort: they're in the v1.0 CI matrix only for the unit test job, not the integration tests. Issues opened against macOS/Windows are accepted but lower priority.
- **NFR29:** Compatible with **`uv` 0.5 and later** for `uvx` invocation — the documented zero-install path.
- **NFR30:** Drops support for a Python minor version no sooner than 12 months after that version's upstream end-of-life. Drops are announced one minor semvertag release in advance.

## Traceability

The BMAD chain Vision → Success Criteria → Journeys → FRs → NFRs is made explicit below so downstream artifacts (UX, Architecture, Epics, Stories) can audit coverage in one place.

### Differentiation legs → Functional Requirements

| Leg (from Executive Summary) | Primary FRs | Primary NFRs |
|---|---|---|
| Migration-aware dual-mode | FR11, FR12, FR14, FR15, FR3 (v1.0 with built-in mappings); FR13, FR16 (v1.x mapping overrides) | NFR6 |
| GitLab-native and alive | FR17, FR40, NFR15 | NFR15, NFR18 |
| Zero-install, runtime-minimal | FR42 | NFR1, NFR2 |

### Journeys → Functional Requirements

| Journey | Primary FRs | Primary NFRs |
|---|---|---|
| 1 — First-time GitLab CI adoption (Petr) | FR1, FR17, FR20, FR29, FR30, FR33, FR40, FR42 | NFR1, NFR2, NFR4 |
| 2 — Mid-migration team lead (Marina) | FR3, FR5, FR11, FR14, FR15, FR25 (v1.0 env/flag-only); FR23, FR24 (v1.x file-based) | NFR6 |
| 3 — Tag-only secondary user (Dani) | FR18*, FR41, FR45 | NFR16* |
| 4 — Contributor adding Bitbucket provider (Sasha) | FR19*, FR22, FR46 | NFR21, NFR22, NFR23 |

*FR18, FR19, NFR16 are v1.x deliverables; Journey 3 and Journey 4 are partially supported by v1.0 (Marketplace action exists; contributor seam exists) and fully realized by v1.x.

### Success Criteria → Validation source

| Success criterion | Validated by |
|---|---|
| First-tag time <5 min median | NFR3 (formal target); FR29 (`doctor`) gates first-run friction |
| Strategy switching with one config change | FR11, FR25 (v1.0 via `SEMVERTAG_STRATEGY` CI variable); FR23, FR24 (v1.x via file-based config); Journey 2 |
| `doctor` passes for ≥80% of new users | FR29, FR30, NFR4 |
| Specific error feedback | FR30, NFR8, NFR10 |
| Aha-moment confirmation (public write-up) | Outside-tracked; FR45 (discovery surfaces) creates the conditions |
| 6-month adoption signals (downloads, stars, contributor, mention) | Outside-tracked; FR43 (migration docs), FR45 (discovery) create conditions |
| Zero regressions on internal pipelines | NFR9 (shadow-mode validation) |
| Test coverage ≥85% / 100% branch on bump logic | NFR22 |
| API stability post-1.0 | FR44, NFR25 |

### Phase coverage

| Phase | FRs in scope | NFRs in scope |
|---|---|---|
| v1.0 (MVP) | FR1–FR12, FR14, FR15, FR17, FR20–FR22, FR25–FR46 (i.e. all FRs not tagged *(v1.x)*) | NFR1–NFR15, NFR18–NFR30 |
| v1.x (Growth) | FR13, FR16 (collection-shaped mapping overrides), FR18, FR19 (GitHub + Bitbucket providers), FR23, FR24 (file-based configuration) | NFR16, NFR17, NFR19 (Bitbucket scenario) |
| Vision (2–3 yr) | Family-of-repos packaging; non-Raiffeisen maintainer pool | (no new NFRs; existing ones remain) |
