# Story 4.3b: GitLab CI Catalog component (`templates/semvertag.yml`)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Petr the GitLab SRE (PRD Journey 1),
I want to include semvertag via the GitLab CI Catalog with a minimal `include:` snippet referencing a published component,
So that GitLab CI adopters get a native one-liner integration path discoverable through the Catalog browser — and so that **FR40** (GitLab CI Catalog adoption) and **FR45** (Catalog discoverability) are satisfied for v1.0.

## Acceptance Criteria

### AC1 — Component descriptor exists at the canonical Catalog-discoverable path with required metadata

**Given** the repo root currently contains `pyproject.toml`, `Justfile`, `README.md`, `LICENSE`, `mkdocs.yml`, `action.yml` (Story 4.3a, landed `eca3f07`), `.github/`, `docs/`, `semvertag/`, `tests/`, `_bmad/`, `_autosemver_reference/`, `.gitignore`, `.readthedocs.yaml` (no `templates/`, no `.gitlab/`)
**When** Story 4.3b lands
**Then** a NEW file `templates/semvertag.yml` exists at the repo root with these top-level YAML keys, in this order, separated by the `---` document marker GitLab requires between the `spec:` header and the job body:

1. `spec:` — the component-metadata header; contains exactly one sub-key `inputs:` (see AC2). Marketplace/Catalog ingestion reads this block to render the component's parameter form in the Catalog UI.
2. `---` — the YAML document separator. **Required.** Without it, GitLab treats the whole file as a single YAML document and rejects the `spec:` block as an unknown top-level pipeline key.
3. The job body — see AC3.

**And** there is **no** top-level `image:` key (image is per-job inside the body, see AC3); **no** `before_script:` / `after_script:` at the top level; **no** `variables:` block at the top level (env vars come from the GitLab-injected runtime, see AC3).

**And** the file path is `templates/semvertag.yml` (single-file component, one component per repo) — NOT `templates/semvertag/template.yml` (the bundled-component layout, which is for multi-file components) and NOT `.gitlab/catalog/component.yml` (the path prescribed by `architecture.md:1067-1069` and the epic `epics.md:779`, but **NOT** Catalog-discoverable per GitLab's `glab release create --publish-to-catalog` behavior — see Constraint 1 and OQ1).

**And** the include-ref shape consumers will use is `include: - component: $CI_SERVER_FQDN/<org>/semvertag/semvertag@<version>` — the component name (the trailing `semvertag` after the second `/`) is derived from the `templates/<name>.yml` filename, NOT from the `spec:` block.

### AC2 — Inputs: exactly one (`strategy`), optional with default

**Given** the epic AC1 explicitly enumerates inputs ("declares its inputs (e.g., `strategy`)", `epics.md:781`) and the architecture's "per-repo strategy" surface is the `SEMVERTAG_STRATEGY` env var (`prd.md:199`)
**When** the component is included
**Then** `templates/semvertag.yml`'s `spec.inputs` block declares exactly one input:

```yaml
spec:
  inputs:
    strategy:
      description: 'Bump strategy. One of: branch-prefix (default), conventional-commits.'
      type: string
      options: [branch-prefix, conventional-commits]
      default: branch-prefix
```

**And** the `type:` is `string` (GitLab Catalog v17.0+ supports typed inputs; using the typed form lets the Catalog UI render a dropdown — see Library/framework specifics).

**And** the `options:` enumeration MUST contain exactly `[branch-prefix, conventional-commits]` — the two strategies semvertag implements (`_settings.py:64` `Literal["branch-prefix", "conventional-commits"]`). Typos in `options:` propagate to the Catalog UI form; an out-of-list value passed by a consumer is rejected by GitLab before the job runs, surfacing a clean `inputs.strategy is not a valid option` error — strictly better than the runtime pydantic ValidationError 4-3a's strategy input emits.

**And** there is **no** `token` input. Unlike 4-3a's `action.yml` (which must surface `token` because GitHub's `${{ github.token }}` lives in the workflow context), GitLab CI auto-exports `CI_JOB_TOKEN` into every job's environment, and the existing settings-layer alias chain in `semvertag/_settings.py:15-20` reads it natively:

```python
validation_alias=pydantic.AliasChoices(
    "SEMVERTAG_GITLAB__TOKEN", "SEMVERTAG_TOKEN",
    "CI_JOB_TOKEN", "GITLAB_TOKEN",
),
```

Surfacing a `token` input would be redundant for the common case and would tempt consumers to leak a hard-coded token into pipeline YAML. Token override is documented as a `SEMVERTAG_TOKEN` CI variable in `docs/providers/gitlab.md` (AC6), not as a component input.

**And** there is **no** `gitlab_endpoint` / `project_id` input. Both are environment-driven: `CI_SERVER_FQDN` informs the default endpoint (self-hosted consumers set `SEMVERTAG_GITLAB__ENDPOINT` once at the project level — single declaration vs. per-job repetition), and `CI_PROJECT_ID` is in the `_PROJECT_ID_ALIASES` chain (`_settings.py:26-29`). v1.0 keeps the component's surface minimal per Journey 1's narrative ("Copies the snippet into one repo. Sets `SEMVERTAG_TOKEN` from his existing GitLab PAT." — `prd.md:172`).

### AC3 — Job body uses `image:` + `script:` with `uvx semvertag` invocation

**Given** the architecture mandates `uvx semvertag` as the zero-install invocation (`architecture.md:55, 1349`) and the CLI is API-driven (no local git reads, see `semvertag/_use_case.py:24-71`)
**When** the component runs
**Then** the job body declares:

```yaml
semvertag:
  image: python:3.13-slim
  variables:
    SEMVERTAG_STRATEGY: $[[ inputs.strategy ]]
  before_script:
    - pip install --quiet --no-cache-dir uv
  script:
    - uvx semvertag
```

**And** the job name is `semvertag` (matching the Catalog component name; not `auto-tag` / `tag` / `semvertag-job`). The job name is what appears in the consumer's pipeline view when they include this component, so the name needs to be both descriptive and consistent with the brand.

**And** the input substitution syntax is `$[[ inputs.strategy ]]` (GitLab Catalog v17.0+ component-input interpolation) — NOT `${{ inputs.strategy }}` (GitHub Actions syntax) and NOT `$CI_INPUT_STRATEGY` / `$INPUTS_STRATEGY` (not a real GitLab variable). The `$[[ ... ]]` form is template-substituted at include time, before any pipeline variable expansion; it is distinct from `$VARNAME` / `${VARNAME}` (runtime variable expansion). See Anti-pattern 1.

**And** `image:` is `python:3.13-slim` (NOT a custom semvertag-vendored image, NOT `ghcr.io/astral-sh/uv:0.5-python3.13`, NOT floating `python:slim`). Rationale:
- `python:3.13-slim` is the smallest official Python image with the version matching the project's `pyproject.toml` `[project] requires-python = ">=3.10"` floor + `publish.yml`'s `python-version: 3.13` (Story 4.2).
- A vendored `ghcr.io/<org>/semvertag` image would add a release-surface (we'd own a container registry presence) — explicitly excluded by `architecture.md:1347-1351`.
- `ghcr.io/astral-sh/uv:0.5-python3.13` would couple us to a third-party image registry and a uv-version pin. The floating-uv philosophy in 4-3a Constraint 8 applies here too.
- `python:slim` (no version) violates Story 4.2's pin-discipline for reproducibility.

**And** `before_script: pip install --quiet --no-cache-dir uv` is the install path (NOT `pip install astral-sh/uv@v3` — that's the GitHub setup-uv action, not a Python package; NOT a curl-bash). `pip install uv` is the official documented install when not using an installer script. `--no-cache-dir` matches the CI hygiene already in `Justfile` (Story 1.1 convention). `--quiet` keeps job output focused on `uvx semvertag` itself.

**And** the env-var bridge `SEMVERTAG_STRATEGY: $[[ inputs.strategy ]]` is the same surface 4-3a uses (`action.yml:41` after that story landed). It hits the settings-layer's `AliasChoices` chain identically; no provider-specific CLI flags needed.

**And** the job declares no `stage:` (consumers can override at include time per GitLab's standard include-overlay semantics if they want to bind the job to a specific stage); no `rules:` (consumers own trigger rules); no `dependencies:` / `needs:` (the component is standalone).

### AC4 — Component descriptor declares schema-friendly metadata; NO branding equivalent

**Given** GitLab CI Catalog has no `branding:` / `icon:` / `color:` block in its component schema (unlike GitHub Marketplace `action.yml`) — the Catalog UI sources its presentation from the **repo README** + project description, not from the component file
**When** the component is published
**Then** `templates/semvertag.yml` declares **no** `branding:` block, **no** `icon:` / `color:` keys, and **no** `metadata:` block (the latter is reserved for a GitLab-specific feature not relevant to component discoverability).

**And** the component's discoverability metadata is delegated entirely to:
- The repo's GitLab project description (Story 4.7 ownership; out of scope for 4.3b).
- The repo's `README.md` (Story 4.7 hero content; out of scope for 4.3b).
- The semantic version tag on the release (Story 4.2 `publish.yml` ownership for cutting tags).

**Note:** This is the major shape difference from 4-3a's AC4 (Marketplace branding). 4-3b deliberately has **fewer** keys than 4-3a, not more — the Catalog protocol surfaces less metadata than Marketplace by design.

### AC5 — `templates/semvertag.yml` validates against best-available gate in `ci.yml`

**Given** `check-jsonschema`'s builtin schema list (verified locally on 2026-05-30: `vendor.azure-pipelines, vendor.bamboo-spec, vendor.bitbucket-pipelines, vendor.buildkite, vendor.circle-ci, vendor.cloudbuild, vendor.codecov, vendor.compose-spec, vendor.dependabot, vendor.drone-ci, vendor.github-actions, vendor.github-workflows, vendor.gitlab-ci, vendor.meltano, vendor.mergify, vendor.renovate, vendor.snapcraft, vendor.taskfile, vendor.travis, vendor.woodpecker-ci`) does NOT include a GitLab CI Catalog component schema, and schemastore.org does NOT publish one as of 2026-05-30
**When** Story 4.3b ships
**Then** `.github/workflows/ci.yml`'s `lint` job gains a new step **after** 4-3a's `Validate action.yml against GitHub Actions schema` step and **before** `uv build` (at the same nesting level as the existing steps):

```yaml
- name: Validate templates/semvertag.yml shape
  run: |
    uv run --with pyyaml python - <<'PY'
    import sys, yaml
    docs = list(yaml.safe_load_all(open('templates/semvertag.yml')))
    assert len(docs) == 2, f'expected 2 YAML docs (spec + body), got {len(docs)}'
    spec, body = docs
    # Spec block sanity
    assert 'spec' in spec and 'inputs' in spec['spec'], 'spec.inputs missing'
    inputs = spec['spec']['inputs']
    assert set(inputs) == {'strategy'}, f'expected inputs={{strategy}}, got {set(inputs)}'
    s = inputs['strategy']
    assert s.get('type') == 'string'
    assert s.get('default') == 'branch-prefix'
    assert sorted(s.get('options', [])) == ['branch-prefix', 'conventional-commits']
    # Body sanity
    assert 'semvertag' in body, 'job "semvertag" missing'
    job = body['semvertag']
    for key in ('image', 'variables', 'before_script', 'script'):
        assert key in job, f'job.{key} missing'
    assert job['variables'].get('SEMVERTAG_STRATEGY') == '$[[ inputs.strategy ]]'
    print('templates/semvertag.yml shape OK')
    PY
```

**And** the step exits 0 on success; the `assert` failures surface as clean Python traceback lines in CI logs.

**And** the implementation explicitly chooses this structural-check fallback over the three alternatives the epic AC3 wording ("if available") acknowledges:
- (a) `check-jsonschema --builtin-schema vendor.gitlab-ci` — validates `.gitlab-ci.yml` pipeline syntax, not Catalog components; would either pass (wrong-schema false positive) or fail on the `spec:` block (wrong-schema false negative). Either way, wrong tool.
- (b) `check-jsonschema --schemafile <URL>` against a community schema — none exists at schemastore.org or in any widely-known third-party registry as of 2026-05-30 (verified via Context7 `/websites/gitlab` query and direct schemastore browse).
- (c) GitLab's CI Lint API (`POST /api/v4/projects/:id/ci/lint`) — an HTTP roundtrip from CI requires network + an authenticated project endpoint; this story is a static-gate story, not an integration-test story.

**Rationale captured:** the structural Python check validates the contract our consumers will rely on (the two `spec.inputs.strategy` defaults + the job body's existence) without depending on an upstream schema that doesn't exist. When GitLab publishes a canonical schema (or `check-jsonschema` adds a vendored one), the gate gets upgraded in a follow-up story.

### AC6 — A working consumer-side example pipeline ships in `docs/providers/gitlab.md`

**Given** Story 4.3a established the `docs/providers/<provider>.md` convention (`docs/providers/github.md` exists; 4-3a's AC6 names six required H2 sections)
**When** Story 4.3b ships
**Then** a NEW file `docs/providers/gitlab.md` exists at this path with these H2 sections, in this order (mirroring `github.md`'s structure for adopter consistency):

1. `## Quick Start` — a working `.gitlab-ci.yml` snippet, ~10 lines, that a consumer pastes into their repo and gets auto-tagging on push-to-main. Drawn from Journey 1's "4-line `.gitlab-ci.yml` snippet" framing (`prd.md:170`).
2. `## Inputs` — table matching `templates/semvertag.yml`'s `spec.inputs` block verbatim (drift-detection: AC10).
3. `## Required permissions` — a section about the **token** (NOT permissions in the GitHub-Actions sense). Names `CI_JOB_TOKEN` (the default), and the conditions under which the consumer needs a Project Access Token (PAT) or Personal Access Token instead — see Constraint 9. References the `semvertag doctor` command (Story 3.x) as the diagnostic.
4. `## Token scope: `CI_JOB_TOKEN` vs Project Access Tokens` — covers the (real, common) case where `CI_JOB_TOKEN` lacks the scope needed to push protected tags. Documents the GitLab `Settings → CI/CD → Token Permissions` toggle that re-grants `CI_JOB_TOKEN` write-repository scope. Documents the PAT alternative (`SEMVERTAG_TOKEN` CI variable). Documents the `SEMVERTAG_GITLAB__ENDPOINT` env var for self-hosted GitLab (Petr's context, `prd.md:168`).
5. `## Branch-prefix vs conventional-commits` — copy of `github.md`'s same section (prose-equivalent, since the two strategies are provider-agnostic). Per 4-3a's OQ4 resolution, do NOT link to `docs/strategies/branch-prefix.md` / `docs/strategies/conventional-commits.md` (those land in Story 4.4; dead links fail `mkdocs build --strict`).
6. `## Troubleshooting` — at minimum four failure modes:
   - **403 on tag push from `CI_JOB_TOKEN`** — the consumer needs to either grant `CI_JOB_TOKEN` write-repository scope or substitute a PAT via `SEMVERTAG_TOKEN`. Names the `semvertag doctor` output that reports this.
   - **`Project id missing` error** — the runner did not export `CI_PROJECT_ID` (e.g., running outside a GitLab CI job, or under a custom executor that strips CI variables). Document the `SEMVERTAG_PROJECT_ID` override.
   - **Self-hosted GitLab on a private FQDN** — set `SEMVERTAG_GITLAB__ENDPOINT` as a project-level CI variable; the component's default (`CI_SERVER_FQDN` discovery) only works on `gitlab.com`-shaped hostnames per the settings layer.
   - **`include: - component: <org>/semvertag@v1` fails to resolve in the consumer's pipeline** — `<org>` is a literal placeholder per Story 4.7's convention; the consumer must substitute the real organization name.

**And** there is **no** "preview / status" banner at the top of `gitlab.md` (unlike `github.md`'s `!!! warning "v1.0 status: distribution-channel preview"` admonition for the GitHub-provider-stub state, landed in 4-3a's code-review). The GitLab provider (`semvertag/providers/gitlab.py`, 16.3K) is **fully implemented** as of Epic 1; the wrapped CLI works end-to-end for GitLab CI consumers.

**And** the Quick Start snippet is byte-equal to this canonical form (use it verbatim; AC8 byte-stability applies):

```yaml
include:
  - component: $CI_SERVER_FQDN/<org>/semvertag/semvertag@v1
    inputs:
      strategy: branch-prefix

stages: [tag]

semvertag:
  stage: tag
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
```

The snippet length (12 lines incl. blank lines) is a deliberate trade-off — fewer lines than 4-3a's 15-line GitHub snippet because GitLab's `include:` model is denser; more than 4 lines because Journey 1's "4-line snippet" framing was aspirational and didn't account for `rules:` (which Petr would need to avoid tagging on every feature-branch push).

### AC7 — `mkdocs.yml` gains a `Providers → GitLab CI` nav leaf

**Given** Story 4.3a's `mkdocs.yml` nav (after `4-3a` landed) has:

```yaml
nav:
  - Quick Start: index.md
  - Providers:
    - GitHub Actions: providers/github.md
  - Contributing:
    - Release runbook: contributing/release.md
```

**When** Story 4.3b ships
**Then** `mkdocs.yml` is amended to insert a sibling `GitLab CI: providers/gitlab.md` entry **alphabetically before** `GitHub Actions: providers/github.md` (GitHub < GitLab alphabetically; placing GitLab first means the order is alphabetical AND chronologically older provider first, since GitLab is Epic 1's primary provider). Final nav:

```yaml
nav:
  - Quick Start: index.md
  - Providers:
    - GitLab CI: providers/gitlab.md
    - GitHub Actions: providers/github.md
  - Contributing:
    - Release runbook: contributing/release.md
```

**And** the theme, palette, markdown_extensions, plugins, repo_url, and `extra:` blocks are byte-identical to the pre-Story-4.3b state. AC11 enforces this.

**And** `mkdocs build --strict` exits 0 with the new nav entry (AC12 gate).

### AC8 — `templates/semvertag.yml` is byte-stable against schema/version drift

**Given** the GitLab Catalog component schema may evolve between v17.0 (current minimum for typed inputs) and future GitLab versions
**When** the dev completes implementation
**Then** the descriptor uses only keys/values that are stable across GitLab 17.0 → 18.x:
- `spec:inputs:` with `description`, `type: string`, `options: [...]`, `default:` — all introduced in 17.0, stable through 18.x.
- `image:`, `variables:`, `before_script:`, `script:` — core GitLab CI keys, stable since 11.x.
- `$[[ inputs.<name> ]]` template substitution — stable since 17.0.

**And** the descriptor avoids experimental keys: `spec.inputs.<name>.regex` (added 17.4, conditionally available), `spec.inputs.<name>.required: true` paired with `default:` (semantic conflict in some GitLab versions), `image:name:` + `image:entrypoint:` (override syntax that has fluctuated across versions).

### AC9 — Catalog publishing is wired through a future CI workflow; this story does NOT add it

**Given** GitLab CI Catalog publication requires the project to be (a) hosted on a GitLab instance (NOT GitHub), (b) marked as a "CI/CD Catalog project" in project settings, and (c) cut a release via `release:` keyword in a GitLab CI job with `--publish-to-catalog`
**When** Story 4.3b lands
**Then** the publication path is **NOT** added to this repo's GitHub workflows. Specifically:
- No new `.gitlab-ci.yml` at repo root.
- No `release.yml` GitHub Action that mirrors the repo to GitLab.
- No changes to `.github/workflows/publish.yml` (Story 4.2's PyPI publish).

**And** the publication mechanism is captured in `_bmad/deferred-work.md §4-3b` (post-review only, Task 9) as a follow-up question for **either Story 4.7 (pre-launch coordination) or a future story** to decide. The three live options:
- (a) Mirror semvertag's GitHub repo to a GitLab project; a scheduled GitHub Action pushes tags to the mirror, which then triggers GitLab's Catalog publish via its own `.gitlab-ci.yml`. (Complex; cross-host coordination.)
- (b) Manually push to a GitLab mirror per release as part of the maintainer runbook. (Low-tech; depends on humans.)
- (c) Co-locate `templates/semvertag.yml` AND the GitLab-side `.gitlab-ci.yml` in a parallel GitLab-only repo that `include:`s back to the GitHub canonical source. (Highest complexity; rejected on day 1.)

**The story 4.3b explicitly does not pick.** The descriptor lands first because it's a static artifact that's correct regardless of which publication path is chosen.

### AC10 — `templates/semvertag.yml` and `docs/providers/gitlab.md` are drift-free

**Given** the Inputs table in `docs/providers/gitlab.md` and the `spec.inputs` block in `templates/semvertag.yml` MUST describe the same shape
**When** the dev completes implementation
**Then** the `default`, `options`, and `description` values in the docs table are character-identical to the values in `spec.inputs.strategy` (excluding the leading `'` Marketplace-quote convention 4-3a uses — GitLab Catalog accepts both quoted and unquoted strings; pick the unquoted form for readability since `branch-prefix` has no YAML-special characters).

### AC11 — No changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `LICENSE`, `docs/index.md`, `docs/contributing/`, `docs/requirements.txt`, `action.yml`, `docs/providers/github.md`, `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `.gitlab/` (architecture-suggested path — do not create this), `context7.json`, `CLAUDE.md`

**Given** Story 4.3b's scope is strictly the GitLab CI Catalog wrapper + its docs + one ci.yml step + one mkdocs nav line
**When** the dev runs `git diff HEAD --` against these paths after landing 4.3b
**Then** the diffs are EMPTY. AC11's "do-not-touch" list mirrors 4-3a's AC11 with two additions:
- `action.yml` and `docs/providers/github.md` — both landed by 4-3a. The two sibling stories are independent; 4-3b MUST NOT modify 4-3a's outputs.
- `.gitlab/` — the architecture suggests this path (`architecture.md:1067-1069`) but AC1 above explicitly does not use it. **Don't create this directory; don't put anything in it.** OQ1 captures the architecture deviation for code-review resolution.

### AC12 — Local validation gates stay green

**Given** the project's Justfile recipes (Story 4.1 ownership) include `just install lint-ci`, `just test`, `just coverage`, plus the architecture's `mkdocs build --strict` and the new schema-validate step
**When** the dev runs each gate locally before committing
**Then** each exits 0:
- `uv run --with pyyaml python -c "from yaml import safe_load_all; list(safe_load_all(open('templates/semvertag.yml')))"` → no error
- The structural Python gate from AC5 → `templates/semvertag.yml shape OK`
- `just lint-ci` (`eof-fixer` + `ruff format --check` + `ruff check --no-fix` + `uv run ty check`) → all clean
- `uv build` → sdist + wheel land in `dist/` byte-stably (architecture invariant)
- `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` → no warnings on the new nav entry, no dead links, no orphan files
- `uv run pytest` → 425+ tests pass (the count must be ≥ post-4.3a baseline; no test additions expected, no test removals)
- `uv run pytest --cov=semvertag --cov-branch --cov-report=term-missing` → branch coverage on `semvertag/strategies/branch_prefix.py`, `semvertag/strategies/conventional_commits.py`, `semvertag/_doctor/` ≥ post-4.3a baselines (`Story 1.6 100% / Story 2.1 100% / Story 3.1 100%` are the pre-existing invariants — 4.3b does not regress them)

### AC13 — All existing pre-Story-4.3b CI behaviors are preserved byte-identical

**Given** Story 4-3a added a single `Validate action.yml…` step to `ci.yml`'s `lint` job and Story 4.1 / 4.2 own the rest of `ci.yml`
**When** the dev's only `ci.yml` change is inserting the new `Validate templates/semvertag.yml shape` step
**Then** `git diff 76ddc3d -- .github/workflows/ci.yml` (against 4-3a's landed state) shows exactly ONE insertion block — the new step. All other steps (`actions/checkout@v4`, `astral-sh/setup-uv@v3` + `cache-dependency-glob`, `uv python install 3.10`, `just install lint-ci`, the 4-3a schema-validate step, `uv build`, `mkdocs build --strict`, `LOC gate (NFR21)`, `Test matrix`, `pip-audit`) are byte-stable.

### AC14 — A green CI run on the PR demonstrates all jobs pass with the new file present

**Given** the PR that lands Story 4.3b
**When** GitHub Actions runs the workflow
**Then** the `lint` job passes (including the new `Validate templates/semvertag.yml shape` step), the test matrix passes on all Python versions 3.10–3.14, and `pip-audit` reports no new advisories. The PR is mergeable.

## Tasks / Subtasks

- [x] **Task 1: Author `templates/semvertag.yml`** (AC: 1, 2, 3, 4, 8) — applied 2026-05-30
  - [x] 1.1 Created directory `templates/` at repo root.
  - [x] 1.2 Authored the `spec:` block with `strategy` input (type, options, default, description).
  - [x] 1.3 Added `---` YAML document separator.
  - [x] 1.4 Authored job body: `image: python:3.13-slim`, `variables.SEMVERTAG_STRATEGY: $[[ inputs.strategy ]]`, `before_script: pip install --quiet --no-cache-dir uv`, `script: uvx semvertag`.
  - [x] 1.5 Verified parse: `parse OK, docs: 2`.
  - [x] 1.6 No branding/icon/color, no `outputs:`-equivalent, no top-level `image:`/`variables:`/`before_script:`/`after_script:`.

- [x] **Task 2: Author `docs/providers/gitlab.md`** (AC: 6, 10) — applied 2026-05-30
  - [x] 2.1 Created `docs/providers/gitlab.md` (~120 LOC markdown).
  - [x] 2.2 H1 `# GitLab CI`.
  - [x] 2.3 Intro paragraph: 4 sentences mirroring `github.md`'s shape.
  - [x] 2.4 H2 `## Quick Start` with the canonical `.gitlab-ci.yml` snippet + Required-setup callout.
  - [x] 2.5 H2 `## Inputs` with 4-column table mirroring `spec.inputs.strategy`.
  - [x] 2.6 H2 `## Required permissions` covering token alias chain + `semvertag doctor`.
  - [x] 2.7 H2 `## Token scope: CI_JOB_TOKEN vs Project Access Tokens` covering opt-in scope toggle + PAT alternative + `SEMVERTAG_GITLAB__ENDPOINT` for self-hosted.
  - [x] 2.8 H2 `## Branch-prefix vs conventional-commits` — prose-equivalent to `github.md`'s section; no links to `docs/strategies/*.md`.
  - [x] 2.9 H2 `## Troubleshooting` with 4 failure modes (403 token-scope, Project id missing, self-hosted endpoint, `<org>` placeholder).
  - [x] 2.10 No preview banner; the GitLab provider is fully implemented.

- [x] **Task 3: Update `mkdocs.yml` nav** (AC: 7, 11, 12) — applied 2026-05-30
  - [x] 3.1 Inserted `GitLab CI: providers/gitlab.md` leaf alphabetically before `GitHub Actions: providers/github.md` under `Providers:`.
  - [x] 3.2 `mkdocs build --strict` → 0.21s, no warnings.
  - [x] 3.3 Theme / palette / markdown_extensions / plugins / repo_url / extra blocks byte-stable.

- [x] **Task 4: Add `Validate templates/semvertag.yml shape` step to `ci.yml`** (AC: 5, 13) — applied 2026-05-30
  - [x] 4.1 New step inserted between the 4-3a `Validate action.yml against GitHub Actions schema` step (lines 29-39 pre-4-3b) and `uv build`.
  - [x] 4.2 Inline Python heredoc per AC5; single step, single `run:` block (28 LOC delta).
  - [x] 4.3 Verified locally: `templates/semvertag.yml shape OK` (passes); negative-test informal (removing `options:` yields `AssertionError`).
  - [x] 4.4 Rest of `ci.yml` byte-stable: only insertion is the new step.

- [x] **Task 5: Local gate sweep** (AC: 12, 14) — applied 2026-05-30
  - [x] 5.1 yaml.safe_load_all → 2 docs, no error.
  - [x] 5.2 AC5 structural gate → `templates/semvertag.yml shape OK`.
  - [x] 5.3 `just lint-ci` (eof-fixer + ruff format + ruff check + ty check) → all clean.
  - [x] 5.4 `uv build` → `dist/semvertag-0.tar.gz` + `dist/semvertag-0-py3-none-any.whl`.
  - [x] 5.5 `mkdocs build --strict` → 0.21s, no warnings.
  - [x] 5.6 `uv run pytest` → 425 passed in 1.18s.
  - [x] 5.7 Branch coverage: `branch_prefix.py` 100% (24/24, 6/6 br), `conventional_commits.py` 100% (43/43, 16/16 br), `doctor/_checks.py` 100% (36/36, 14/14 br), `doctor/_render.py` 100% (63/63, 12/12 br). No regression.

- [x] **Task 6: Consumer-snippet smoke check** (AC: 6, 10) — applied 2026-05-30
  - [x] 6.1 Quick Start YAML block extracted via `re.search(r'```yaml\n(.*?)\n```', src, re.DOTALL)` then `yaml.safe_load` → `keys: ['include', 'semvertag', 'stages']`.
  - [x] 6.2 Drift check passed: docs Inputs table's `branch-prefix` default + `[branch-prefix, conventional-commits]` options match `templates/semvertag.yml` character-identically.
  - [x] 6.3 No scratch `.github/workflows/test-snippet.yml` created (in-memory only; mirrors 4-3a Change Log precedent).

- [x] **Task 7: File-list / regression audit** (AC: 11, 13) — applied 2026-05-30
  - [x] 7.1 `git status --short` confirmed exactly: `templates/semvertag.yml` NEW, `docs/providers/gitlab.md` NEW, `mkdocs.yml` MODIFIED, `.github/workflows/ci.yml` MODIFIED, `_bmad/4-3b-...md` MODIFIED (Task 8 + eof-fixer trailing-newline normalization), `_bmad/sprint-status.yaml` MODIFIED. No `.gitlab/` created; no diff in `action.yml` or `docs/providers/github.md`.
  - [x] 7.2 `git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md LICENSE docs/index.md docs/contributing/ docs/requirements.txt action.yml docs/providers/github.md .github/workflows/publish.yml .github/workflows/dependency-update.yml context7.json CLAUDE.md` → EMPTY. AC11 confirmed.

- [x] **Task 8: Update Dev Agent Record + Story Status** (AC: all) — applied 2026-05-30
  - [x] 8.1 `Agent Model Used` filled (Claude Opus 4.7, 1M context).
  - [x] 8.2 `Debug Log References` filled with gate exit confirmations.
  - [x] 8.3 `Completion Notes List` filled with per-AC verification statements.
  - [x] 8.4 `File List` table filled.
  - [x] 8.5 `Change Log` filled.
  - [x] 8.6 Status: `ready-for-dev` → `review`.

- [ ] **Task 9: Post-review — update `_bmad/deferred-work.md` (admin)**
  - [ ] 9.1 Append `## Deferred from: code review of 4-3b-gitlab-ci-catalog-component (YYYY-MM-DD)` with any non-blocking decisions / discovered edge cases.
  - [ ] 9.2 Cross-link the closure (or non-closure) of these prior deferred items:
    - From `_bmad/deferred-work.md §4-3a` line 156 (`<org>/semvertag@v1` floating major-tag refs in Quick Start snippets) — Story 4.3b perpetuates the same convention for the GitLab include ref; item stays open until Story 4.7.
    - From `_bmad/deferred-work.md §1-1` line 12 (`<org>` URL placeholders) — Story 4.3b perpetuates the placeholder in `templates/semvertag.yml` (if applicable) and `docs/providers/gitlab.md`; item stays open until Story 4.7.
  - [ ] 9.3 Specifically capture: (a) which of AC9's three Catalog-publish options the maintainer plans to pursue (mirror, manual push, parallel repo); (b) whether the AC5 structural Python check should be upgraded to a proper JSON-schema validation once GitLab publishes or `check-jsonschema` vendors a Catalog-component schema; (c) whether a `just lint-templates` recipe is warranted (per 4-3a Anti-pattern 15's "wait for a second action-yml-style file" condition — `templates/semvertag.yml` IS now that second file, so the question is live); (d) the GitLab version-floor mismatch (architecture/PRD says 15.0+; Catalog v1 components need 17.0+); (e) whether the Quick Start snippet should add an `image:` override to demonstrate the consumer-overlay pattern, or stay minimal.

> **Note**: Task 9 (deferred-work updates) is gated on code-review per its own header ("Post-review"); intentionally left unchecked until code-review lands. Mirrors Story 4.2 / 4.3a Task 9 discipline.

## Dev Notes

### Story framing

Story 4.3b is the **fourth story of Epic 4** (Public-Launch Readiness) and the GitLab sibling of Story 4.3a (`epics.md:749`, landed 2026-05-30 as commit `eca3f07`). Both stories sit under implementation-sequence step 9's "Trust-surface scaffolding / Distribution channels" branch (`architecture.md:594`). The two siblings are:

- **4.3a** (landed): GitHub Actions Marketplace wrapper (`action.yml`).
- **4.3b** (this story): GitLab CI Catalog component (`templates/semvertag.yml`).

They are independent and orthogonal — neither blocks the other; 4.3a was sequenced first by sprint choice, not by technical dependency. 4.3b reads heavily from 4.3a as a template for shape, gate discipline, and post-review handoff, but the underlying technology (GitLab CI Catalog vs. GitHub Actions Marketplace) and the descriptor file's syntax are completely different.

The work is **entirely at the repo root (`templates/`) + `docs/providers/` + `.github/workflows/ci.yml` + `mkdocs.yml`** — zero changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `publish.yml`, `dependency-update.yml`, `action.yml`, `docs/providers/github.md`, or any existing doc page. The `semvertag` CLI's GitLab provider is already fully implemented (Epic 1, `semvertag/providers/gitlab.py` 16.3K), so the wrapper's runtime contract is real — unlike 4-3a's preview-state for GitHub.

The epic ACs (`epics.md:777-790`) are 3 narrative G/W/T triplets covering:
1. `templates/semvertag.yml` exists at the canonical path, declares its inputs, runs `uvx semvertag` with `CI_JOB_TOKEN` auto-detected, and ships with a working example in `docs/providers/gitlab.md`.
2. The release process publishes the Catalog listing — but unlike Marketplace's auto-poll-on-release model, GitLab Catalog publication requires cross-host coordination that this story explicitly defers (AC9).
3. `templates/semvertag.yml` validates against GitLab's published schema **if available** — and per the architecture and Context7 verification, GitLab does NOT publish a Catalog component schema as of 2026-05-30, so AC5 falls back to a structural Python check.

These three narratives expand to 14 dev-facing ACs above (mirrors Story 4.2 / 4.3a's granularity discipline).

The PRD anchors:
- **FR40** — "User can adopt semvertag in GitLab CI by including the published GitLab CI Catalog component (v1.0)" (`prd.md:553`).
- **FR45** — Catalog presence as a discoverability channel (`prd.md:561`).
- **FR42** — `uvx semvertag` zero-install pattern (`prd.md:555`).
- **FR26** — Provider-native credential env vars including `CI_JOB_TOKEN` (`prd.md:530`).
- **Journey 1 — Petr** — The GitLab SRE migrating 15 product repos off manual tagging (`prd.md:166-184`).
- **NFR19** — auto-detected provider-native context via `CI_JOB_TOKEN` (`prd.md:597`).

### Critical architectural constraints

1. **Component descriptor path: `templates/semvertag.yml`, NOT `.gitlab/catalog/component.yml`.** This is a **deviation from `architecture.md:1067-1069`** (which prescribes `.gitlab/catalog/component.yml`) and **from `epics.md:779`** (which says the same). Rationale, with evidence: GitLab CI Catalog ingestion (`glab release create --publish-to-catalog`, the GitLab CLI's release-publish command) **strictly scans the `templates/` directory** for `.yml` component files. The verbatim text from GitLab's own docs (verified via Context7 `/websites/gitlab` query, source `docs.gitlab.com/18.11/cli/release/create` and `docs.gitlab.com/ee/ci/components`):
   > *"It retrieves components from the current repository by searching for `yml` files within the **'templates' directory** and its subdirectories. Components can be defined: In single files ending in `.yml` for each component, like `templates/secret-detection.yml`."*
   And:
   > *"To publish a component project in the CI/CD catalog... at least one CI/CD component in the `templates/` directory."*
   A descriptor at `.gitlab/catalog/component.yml` would exist on disk but would NOT be discovered by Catalog ingestion. **This deviation is captured in OQ1 below for explicit code-review resolution**; the story author's recommendation is to override the architecture and use the GitLab-canonical path.

2. **No `branding:` block.** GitLab Catalog has no equivalent to GitHub Marketplace's `branding.icon` / `branding.color`. Catalog UI presentation is sourced from the repo's GitLab project description and README. Adding speculative `branding:` keys would fail YAML parsing (`spec:` does not have a `branding:` sub-key in any GitLab version) — quietly fail validation in a non-obvious way.

3. **`spec:` + `---` + job body — both YAML documents in one file.** The Catalog component file is a multi-document YAML stream: the first document declares the component metadata (`spec:`), the second document declares the job(s) the component contributes. Missing the `---` separator is a parse error at component-include time, surfacing as an unhelpful `Found unexpected key 'spec'` error in the consumer's pipeline log.

4. **`$[[ inputs.<name> ]]` is the substitution syntax — NOT `${{ }}` (GitHub Actions) and NOT `$VARNAME` (runtime env vars).** GitLab Catalog component inputs are template-substituted at include time; `$[[ ... ]]` syntax was introduced in GitLab 17.0 specifically to distinguish template-time inputs from runtime variables. Mixing the syntaxes produces silent failures (the literal text `${{ inputs.strategy }}` would be passed through unchanged and reach the runtime as a literal string).

5. **`CI_JOB_TOKEN` may NOT have write-repository scope by default in modern GitLab.** This is the major footgun. Older GitLab versions auto-granted `CI_JOB_TOKEN` full repo scope; recent versions (16.x+) require the consumer to explicitly opt in via Settings → CI/CD → Token Permissions → Job token permissions. Petr's narrative (`prd.md:172`) — *"Sets `SEMVERTAG_TOKEN` from his existing GitLab PAT"* — already accounts for this; Petr uses a PAT, not `CI_JOB_TOKEN`. The component's default is to attempt `CI_JOB_TOKEN` first (via the alias chain), but the docs page MUST surface the PAT alternative prominently — AC6 §Token-scope captures this.

6. **`uvx semvertag` (NOT `uv run semvertag`, NOT `pip install semvertag && semvertag`).** Same rationale as 4-3a Constraint 4: ephemeral install, no persistent state, no local project context required.

7. **`image: python:3.13-slim` is the only pinned image choice.** See AC3 rationale. Variants `python:3-slim` (no version) violate Story 4.2 reproducibility; vendored `ghcr.io/<org>/semvertag:<tag>` adds release surface; `ghcr.io/astral-sh/uv:...` couples to a third-party registry. `python:3.13-slim` is the single sane choice for v1.0.

8. **No `before_script:` / `after_script:` outside the job body.** Top-level `before_script:` / `after_script:` would apply to every job in the consumer's pipeline at include time — pollutes the consumer's pipeline namespace. Scope all setup to the `semvertag` job body specifically (AC3).

9. **`SEMVERTAG_GITLAB__ENDPOINT` is the env var for self-hosted GitLab; it is NOT in the alias chain.** Per `semvertag/_settings.py:48` (and the pydantic-settings nested-delimiter convention `__`), self-hosted consumers set `SEMVERTAG_GITLAB__ENDPOINT` as a project-level CI variable. The component does NOT auto-discover this from `CI_SERVER_FQDN` — that would be a hidden-magic behavior contradicting `prd.md:366`'s explicit env-var contract. Docs page (AC6 §Token-scope) MUST surface this; self-hosted consumers (Petr is on GitLab 17 self-hosted, `prd.md:168`) are a first-class user.

10. **Schema validation via structural Python check, NOT `check-jsonschema --builtin-schema`.** AC5 rationale. The `vendor.gitlab-ci` builtin validates `.gitlab-ci.yml` pipeline syntax, not Catalog components. Schemastore does not vendor a Catalog component schema as of 2026-05-30. The structural Python heredoc validates the contract we ship without depending on an upstream schema that doesn't exist.

11. **`<org>` placeholder preserved in `docs/providers/gitlab.md` include-ref snippet and (if it appears) in `templates/semvertag.yml`.** Per Story 4.7 ownership and the pre-launch convention carried by every prior story. 4-3b does NOT substitute the real org name. The first GitLab Catalog release tagged before Story 4.7 lands would have the `<org>` placeholder in its discoverability copy — a maintainer following the runbook MUST do the swap before cutting the first real release (same as 4-3a Constraint 11).

12. **No Catalog publish automation in 4-3b.** AC9 rationale. The cross-host coordination question (GitHub canonical vs. GitLab Catalog publish location) is bigger than this story and is captured in deferred-work for Story 4.7 or later. The descriptor lands first; the publication path lands when the maintainer picks one.

13. **CI schema-validation step is in the `lint` job, NOT a new job.** Same as 4-3a Constraint 14: the `lint` job already runs `actions/checkout` + `astral-sh/setup-uv@v3` + has `uv` + `python` available. Adding a top-level job for one step is over-engineering. The new step adds ~2-3s to the `lint` job (the structural check is faster than 4-3a's external-schema fetch was; it's marginally faster now that 4-3a uses `--builtin-schema vendor.github-actions`).

14. **No `outputs:`-equivalent.** GitLab Catalog component schema does not have a job-outputs feature in v17.0. Even if it did, v1.0 surfaces no structured output (same as 4-3a Constraint 15). The CLI's exit code is the contract.

15. **GitLab version floor in user-facing docs: 17.0+** (NOT 15.0+ as PRD `prd.md:113` says). GitLab Catalog v1 components, typed inputs (`type: string`), and the `$[[ ... ]]` substitution syntax all require GitLab 17.0+. This is a documentation correction surfaced by 4-3b that the PRD should reflect in a future polish pass. Docs page (AC6) names the floor explicitly; the PRD edit is captured in OQ7 / deferred-work.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `templates/semvertag.yml` | **NEW** | ~25 LOC YAML. `spec.inputs.strategy` block + `---` separator + `semvertag` job body. |
| `templates/` | **NEW** (implied) | New directory at repo root. Tracked by git only via its content (the `.yml` file). |
| `docs/providers/gitlab.md` | **NEW** | 90–130 LOC markdown. Six H2 sections per AC6. Contains the canonical `.gitlab-ci.yml` consumer snippet. |
| `mkdocs.yml` | **UPDATE** | Add `GitLab CI: providers/gitlab.md` leaf under existing `Providers:` block. 1 LOC delta. Theme / palette / extras byte-stable. |
| `.github/workflows/ci.yml` | **UPDATE** | Add ONE step to the `lint` job: `Validate templates/semvertag.yml shape` running the AC5 inline Python heredoc. ~25 LOC delta (the heredoc body is multi-line). |
| `_bmad/sprint-status.yaml` | **UPDATE** | `4-3b-gitlab-ci-catalog-component: backlog → ready-for-dev → in-progress → review → done`; `last_updated` + `last_updated_note`. |
| `_bmad/4-3b-gitlab-ci-catalog-component.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| `_bmad/deferred-work.md` | **UPDATE** (post-review only) | Append `## Deferred from: code review of 4-3b-…` with non-blocking decisions / discovered edge cases. |
| **Do-not-touch** (Epic 4.3b scope guardrails) | — | All `semvertag/**/*.py`, all `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `.gitignore`, `docs/index.md`, `docs/contributing/`, `docs/requirements.txt`, `context7.json`, `LICENSE`, `CLAUDE.md`, `action.yml` (4-3a), `docs/providers/github.md` (4-3a), `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `.gitlab/` (architecture-suggested path — do not create this directory per Constraint 1 + OQ1). |

### Anti-patterns to avoid

(Architecture §Anti-Patterns + GitLab CI Catalog canonical patterns + Story 4.1 / 4.2 / 4.3a inherited discipline.)

1. **Using `${{ inputs.strategy }}` (GitHub Actions syntax) inside `templates/semvertag.yml`.** The CORRECT GitLab Catalog substitution is `$[[ inputs.strategy ]]`. Mixing the syntaxes does not raise a parse error — the literal `${{ inputs.strategy }}` text passes through unchanged and arrives at the runtime as a literal string, causing `SEMVERTAG_STRATEGY` to be set to the literal text `${{ inputs.strategy }}` instead of the resolved value. The CLI then fails with a pydantic ValidationError on the strategy literal. Silent, hard to debug. AC5's structural check catches this (`assert job['variables']['SEMVERTAG_STRATEGY'] == '$[[ inputs.strategy ]]'`).

2. **Missing `---` document separator between `spec:` and the job body.** A single-document YAML stream with both keys produces `Found unexpected key 'spec'` at component-include time. The AC5 structural check catches this (`assert len(docs) == 2`).

3. **Adding `branding:` / `icon:` / `color:` to mimic 4-3a's Marketplace metadata.** GitLab Catalog has no such concept; these keys are not in the schema. Either the parse fails or (worse) the keys are silently ignored and the dev thinks they accomplished something. Constraint 2.

4. **Hardcoding `image: python:3.13` instead of `python:3.13-slim` to "match local dev".** `python:3.13` is ~330MB; `python:3.13-slim` is ~50MB. Image pulls dominate component cold-start; using the full image adds 5-10s per CI run with no functional benefit.

5. **Adding `before_script:` at the top level of the file.** It would apply to ALL jobs in the consumer's included pipeline, not just `semvertag`. Pollutes the consumer's namespace. Scope to the job body only (Constraint 8).

6. **Pinning the consumer-side `include: - component: ...@v1` to a SHA pin.** Catalog convention is semver-tag refs (`@v1`, `@v1.2.3`, `@~v1` for floating-minor). SHA pinning a Catalog include is allowed but extremely uncommon — it's a security choice the consumer makes, not a default the component-author recommends. (Same call as 4-3a Anti-pattern 7 + Constraint 11.)

7. **Surfacing `token` as a component input** (so consumers write `with: token: $MY_PAT`). The settings-layer alias chain (`_settings.py:15-20`) already handles `SEMVERTAG_TOKEN` / `CI_JOB_TOKEN` / `GITLAB_TOKEN`. A component-level `token` input would either (a) require the consumer to write secret-references in pipeline YAML (Bad — secrets-in-YAML are a known footgun even with `${VARIABLE_NAME}` indirection) or (b) duplicate the env-var path with extra ceremony. The doc page (AC6) tells consumers to set `SEMVERTAG_TOKEN` as a project-level masked CI variable — the GitLab-canonical secret-injection path.

8. **`semvertag --strategy $[[ inputs.strategy ]]` as a CLI flag** instead of the `SEMVERTAG_STRATEGY` env-var bridge. Same as 4-3a Anti-pattern 6: env-var path is canonical per `prd.md:199`; CLI flag couples the component to a specific flag name and bypasses the alias chain. The env-var bridge is also the cross-channel-consistent pattern (4-3a's `action.yml` uses the same env-var bridge).

9. **Adding `dependencies:` / `needs:` / `stage:` to the component job body.** These belong to the **consumer's** pipeline shape, not the component. The component should be stage-agnostic and dependency-free; consumers attach it to their pipeline however they want via the include-overlay pattern. AC6 Quick Start shows the overlay shape.

10. **`uv run semvertag` instead of `uvx semvertag`.** `uv run` needs a project context (a `pyproject.toml` in the working directory); the consumer's repo isn't a semvertag project. `uvx` is the correct ephemeral-install verb.

11. **Building and publishing a vendored container image (`ghcr.io/<org>/semvertag:<tag>`).** Adds release surface; explicitly excluded by `architecture.md:1347-1351`. `pip install --quiet --no-cache-dir uv` inside the existing `python:3.13-slim` image is the right install path.

12. **`SEMVERTAG_PROVIDER: gitlab` set explicitly in `variables:`.** Unlike 4-3a's `action.yml` (which MUST set `SEMVERTAG_PROVIDER: github` because the default is `gitlab` — see 4-3a code-review patch landed 2026-05-30), GitLab is the default in `_settings.py:65`. Adding the explicit set is harmless but wastes a line. Omit.

13. **Re-validating the descriptor against `check-jsonschema --builtin-schema vendor.gitlab-ci`** to feel "thorough". The `gitlab-ci` builtin validates `.gitlab-ci.yml` pipeline syntax, NOT Catalog components. A descriptor that passes `vendor.gitlab-ci` validation may have invalid Catalog metadata and still ship — false sense of security. The AC5 structural check is the right gate.

14. **Creating `.gitlab/catalog/component.yml` AND `templates/semvertag.yml` "for backward compatibility".** Constraint 1 + OQ1. Pick one path; the canonical GitLab path is `templates/`. Co-locating both is process debt that will rot.

15. **A `just lint-templates` recipe.** 4-3a Anti-pattern 15 deferred this to "when a second action-yml-style file lands." 4-3b IS that second file. **But the call here is still "defer"** — the AC5 structural check is a one-liner in CI (no recipe needed for the lint job to execute it), and the existing pattern (manually-run `uvx --from check-jsonschema check-jsonschema` for 4-3a, inline Python heredoc for 4-3b) is two heterogeneous invocations that don't naturally unify into one recipe. A `lint-descriptors` recipe is a real polish opportunity, but only after a third file lands; capture in deferred-work.

### Library / framework specifics

#### GitLab CI Catalog component schema

Authoritative sources (verified 2026-05-30 via Context7 `/websites/gitlab`):
- `docs.gitlab.com/ee/ci/components` — component structure, single-file vs. bundled-directory layout.
- `docs.gitlab.com/ci/inputs` — `spec:inputs:` syntax, `$[[ ... ]]` substitution.
- `docs.gitlab.com/cli/repo/publish/catalog` — `glab repo publish catalog` and the `templates/` discovery rule.
- `docs.gitlab.com/18.11/cli/release/create` — `glab release create --publish-to-catalog`.

Required component structure:
- File at `templates/<component-name>.yml` (single-file) OR `templates/<component-name>/template.yml` (bundled, for multi-file components). 4-3b uses the single-file form.
- Two YAML documents in the file, separated by `---`:
  - Document 1: `spec:` block declaring `inputs:`.
  - Document 2: job(s) the component contributes.

`spec:inputs:` canonical example (from Context7):

```yaml
spec:
  inputs:
    job-stage:
      default: test
    environment:
      type: string
      description: "Deployment environment"
      options: [dev, staging, production]
      default: production
---
component-job:
  stage: $[[ inputs.job-stage ]]
  script: ./scan-website $[[ inputs.environment ]]
```

Input attributes:
- `description: <str>` — surfaces in Catalog UI form.
- `type: string | boolean | number | array` — 17.0+; type-checked at include time.
- `options: [<list>]` — 17.0+; enumeration check before pipeline runs.
- `default: <value>` — optional; if omitted, the input is required.
- `regex: <pattern>` — 17.4+; format validation.

`$[[ ... ]]` substitution:
- Resolved at include time, BEFORE pipeline variable expansion.
- Cannot reference runtime variables (`$CI_*`, project CI variables) — only the input bag.
- Distinct from `$VARNAME` (runtime expansion) and `${VARNAME}` (bash expansion in scripts).

Catalog publish requirements (out of scope for 4-3b code; captured for posterity):
1. Project must be on GitLab (not GitHub).
2. Project must be marked "CI/CD Catalog project" in project settings (one-time UI toggle).
3. Project must have a description and a README.md.
4. Project must have at least one component file under `templates/`.
5. A semver release tag triggers Catalog ingestion via the `release:` keyword + `--publish-to-catalog` flag in a CI job.

#### `check-jsonschema` builtin schemas (for AC5 rationale)

Verified locally on 2026-05-30 via `uvx --from check-jsonschema check-jsonschema --help`:
`vendor.azure-pipelines, vendor.bamboo-spec, vendor.bitbucket-pipelines, vendor.buildkite, vendor.changie, vendor.circle-ci, vendor.citation-file-format, vendor.cloudbuild, vendor.codecov, vendor.compose-spec, vendor.dependabot, vendor.drone-ci, vendor.github-actions, vendor.github-discussion, vendor.github-issue-config, vendor.github-issue-forms, vendor.github-workflows, vendor.gitlab-ci, vendor.meltano, vendor.mergify, vendor.readthedocs, vendor.renovate, vendor.snapcraft, vendor.taskfile, vendor.travis, vendor.woodpecker-ci, custom.github-workflows-require-timeout`

**No `vendor.gitlab-ci-component` or similar.** Schemastore.org's directory was also checked — no Catalog component schema published as of 2026-05-30.

#### `semvertag` settings layer — env var contracts the component relies on

From `semvertag/_settings.py`:
- `_GITLAB_TOKEN_ALIASES` (lines 15-20): `SEMVERTAG_GITLAB__TOKEN` → `SEMVERTAG_TOKEN` → `CI_JOB_TOKEN` → `GITLAB_TOKEN`. The component does NOT export any of these explicitly; GitLab CI exports `CI_JOB_TOKEN` automatically; consumers set `SEMVERTAG_TOKEN` as a project-level masked CI variable for the PAT override path.
- `_PROJECT_ID_ALIASES` (lines 26-29): `SEMVERTAG_PROJECT_ID` → `CI_PROJECT_ID`. GitLab CI exports `CI_PROJECT_ID` automatically.
- `_STRATEGY_ENV_VAR`: `SEMVERTAG_STRATEGY` — the component's job body sets this from `$[[ inputs.strategy ]]`.
- `GitLabConfig.endpoint`: defaults `"https://gitlab.com"`; env override is `SEMVERTAG_GITLAB__ENDPOINT` (note the double-underscore for pydantic-settings nested delimiter).

### Previous story intelligence

Story 4.3a (`_bmad/4-3a-github-actions-marketplace-wrapper.md`, landed 2026-05-30 as commit `eca3f07`) is the direct sibling. Key carryovers:

- **Same `<org>` placeholder convention** — no real org name substitution in any 4-3b file; Story 4.7 owns that swap.
- **Same `uvx semvertag` invocation discipline** — no `uv run`, no `pip install`. The same env-var bridge for `SEMVERTAG_STRATEGY`. The same no-CLI-flag pattern.
- **Same do-NOT-link-to-`docs/strategies/*`** convention — those pages are Story 4.4 and would fail `mkdocs --strict`. Use prose, not links.
- **Same do-NOT-touch-runbook** convention — `docs/contributing/release.md` is Story 4.2 territory; the Catalog-publish runbook addition (if any) is captured in deferred-work for a future amendment.
- **Same six H2 sections in the docs page** — `Quick Start`, `Inputs`, `Required permissions`, `Token scope`, `Branch-prefix vs conventional-commits`, `Troubleshooting`.
- **4-3a's code-review patches that 4-3b inherits:** 4-3a's `ci.yml` schema-validate step now uses `--builtin-schema vendor.github-actions` (not the original `--schemafile <URL>`). 4-3a's `action.yml` now sets `SEMVERTAG_PROVIDER: github` explicitly. 4-3b's schema-validate step is structured similarly (inline gate in the `lint` job, before `uv build`) but uses the inline Python heredoc per AC5 — not `check-jsonschema`.
- **Code-review surfaced 7 patches in 4-3a** — the dev should expect a similar volume of code-review feedback on 4-3b. The most likely categories (mirroring 4-3a's): docs-page wording precision, troubleshooting bullet veracity (don't quote error strings the CLI doesn't actually emit — verify against `semvertag/providers/gitlab.py:201, 301`), and explicit-vs-implicit env-var passthrough.

### Git intelligence (last 5 commits)

```
eca3f07 land story 4.3a code-review     ← The most recent landed work. action.yml + ci.yml + docs/providers/github.md
76ddc3d land story 4.3a implementation  ← 4-3a dev landing.
4b43e47 contextualise story 4.3a        ← Story 4-3a file creation.
db476d3 land story 4.2                  ← publish.yml (PyPI trusted publishing).
1f74105 land epic 3 retrospective       ← Epic 3 (doctor) retro.
```

Pattern observed: each story lands in **three commits** — contextualise (story file creation), implementation, code-review. Story 4-3b will follow the same shape:
- This commit: contextualise (story file landed in `ready-for-dev` status).
- Dev commit: implementation (Tasks 1-7 + Task 8 partial; status `review`).
- Code-review commit: review patches applied (Task 8 final + Task 9; status `done`).

### Testing strategy

**No Python code is added or modified**, so:
- No new pytest tests are written.
- The existing 425-test suite must continue to pass; the branch-coverage gates on `branch_prefix.py`, `conventional_commits.py`, `_doctor/` must not regress.
- All gates run via `just lint-ci` + `uv build` + `mkdocs --strict` + the new AC5 structural check.

The **only new gate** is AC5's structural Python check, run as a CI step in the `lint` job. This gate is intentionally NOT a pytest test:
- It validates a deployment artifact (`templates/semvertag.yml`), not Python code.
- Putting it in the pytest suite would couple pytest collection to YAML-file presence (brittle if the file moves).
- Running it as a `lint`-job step keeps it next to its sibling (4-3a's `Validate action.yml` step).

A future story might consolidate `lint`'s static-artifact gates (action.yml, templates/semvertag.yml, mkdocs nav, eof-fixer, ruff-format) into a `just lint-artifacts` recipe — captured in deferred-work per 4-3a Anti-pattern 15's "wait-for-N-files" condition.

### Open questions (carry to code-review)

1. **OQ1 (HIGHEST PRIORITY): Component path is `templates/semvertag.yml`, NOT `.gitlab/catalog/component.yml` as `architecture.md:1067-1069` and `epics.md:779` prescribe.** Evidence cited in Constraint 1 (Context7 GitLab docs, multiple sources). Recommended resolution: keep `templates/semvertag.yml`, edit the architecture and epic to match. Alternative: dual-location (one canonical, one shim) — rejected as process debt. Code-review needs an explicit user/PM call here; this is a deliberate spec deviation that the dev should not silently accept.

2. **OQ2: Catalog publish mechanism (AC9).** Three options enumerated; story does not pick. Mirror to GitLab + scheduled push? Manual per-release push to a GitLab mirror? Parallel GitLab-only repo with `include:`-back? Code-review (or Story 4.7) needs to commit to one. The descriptor itself is correct regardless of choice.

3. **OQ3: Schema-validate gate strength.** Structural Python heredoc (AC5 chosen path) is correct but minimal. Should the story add a follow-up to upgrade to proper JSON-schema validation if `check-jsonschema` vendors a Catalog-component schema, or if GitLab publishes a canonical one? Same OQ shape as 4-3a's OQ3 (which closed when 4-3a switched to `--builtin-schema vendor.github-actions`).

4. **OQ4: `docs/strategies/*.md` cross-link policy.** Same as 4-3a OQ4 — strategy explainer pages are Story 4.4. 4-3b's docs page does NOT link to them. Confirm by code-review that this convention continues to be acceptable.

5. **OQ5: `SEMVERTAG_GITLAB__ENDPOINT` passthrough — explicit `variables:` entry vs. consumer-project CI variable?** The story chose consumer-project CI variable (no explicit `variables:` entry in `templates/semvertag.yml`). Alternative: surface as a second component input `gitlab_endpoint` and bridge to `SEMVERTAG_GITLAB__ENDPOINT`. The first is simpler; the second is more discoverable for self-hosted consumers. Code-review can flip if Petr-style users complain.

6. **OQ6: Runbook amendment for Catalog publish setup.** Mirrors 4-3a's runbook OQ (Marketplace opt-in checkbox). The Catalog publish steps (project settings toggle, release-job authoring) belong in `docs/contributing/release.md` (Story 4.2 territory). Captured in deferred-work; an explicit follow-up story may amend the runbook.

7. **OQ7: GitLab version-floor doc fix.** Constraint 15. PRD says GitLab 15.0+; Catalog v1 components need 17.0+. 4-3b's docs page uses 17.0+ in adopter-facing copy. The PRD should be amended in a future doc-polish story — capture in deferred-work.

### Project structure notes

The new `templates/` directory at the repo root is GitLab CI Catalog's **mandatory** layout. It sits alongside `.github/`, `docs/`, `semvertag/`, `tests/` — peer-level project directories. mkdocs ignores it (not in `docs_dir`), pytest ignores it (no `*test*.py` files), ruff/ty ignore it (no `*.py` files). No `__init__.py`, no `pyproject.toml` entry, no Justfile recipe touches it.

### References

- `epics.md:771-790` — Story 4.3b epic-level spec (3 G/W/T triplets).
- `epics.md:290-294` — Epic 4 framing (Public-Launch Readiness — Trust Surface, Distribution & Shadow-Mode).
- `epics.md:807-808` — Story 4.4 cross-references for `docs/providers/gitlab.md` (Story 4.4 absorbs token scopes / `CI_JOB_TOKEN` notes; 4-3b creates the page).
- `architecture.md:55-56, 204-206, 260-261, 594, 1067-1069, 1207, 1350, 1397` — CI Distribution architecture decisions and (the now-known-wrong) path prescription.
- `architecture.md:448-456` — Token plumbing alias chain.
- `prd.md:166-184` — Journey 1, Petr the GitLab SRE.
- `prd.md:530, 553-555, 561, 597` — FR26 (provider-native fallbacks), FR40 (Catalog adoption), FR41 (Marketplace adoption — sibling story FR), FR42 (uvx zero-install), FR45 (discoverability), NFR19 (auto-detected provider context).
- `_bmad/4-3a-github-actions-marketplace-wrapper.md` (753 lines) — sibling story file; structural template; convention source.
- `_bmad/deferred-work.md §1-1, §4-1, §4-3a` — cross-linked deferred items.
- `docs/providers/github.md` (166 lines, post-4-3a-review) — docs-page convention reference.
- `mkdocs.yml` (67 lines, post-4-3a) — nav location.
- `.github/workflows/ci.yml` (125 lines, post-4-3a) — schema-validate step's insertion point.
- `semvertag/_settings.py:15-29, 48, 64-65` — env-var alias contracts.
- `semvertag/providers/gitlab.py` (16.3K) — implemented GitLab provider; the wrapped CLI's GitLab path is real, not a stub.
- Context7 `/websites/gitlab` — verified Catalog component syntax, `templates/` discovery rule, `$[[ ... ]]` substitution.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`. Knowledge cutoff January 2026; current date 2026-05-30.

### Debug Log References

Gate run (2026-05-30, post-implementation):
- `uv run --with pyyaml python -c "from yaml import safe_load_all; docs=list(safe_load_all(open('templates/semvertag.yml'))); print('parse OK, docs:', len(docs))"` → `parse OK, docs: 2`
- AC5 inline structural check → `templates/semvertag.yml shape OK`
- `just lint-ci` → `eof-fixer . --check`, `ruff format --check` (47 files already formatted), `ruff check --no-fix` (All checks passed!), `ty check` (All checks passed!) — clean (after a one-line eof-fixer normalization of the story file itself)
- `uv build` → `Successfully built dist/semvertag-0.tar.gz`, `Successfully built dist/semvertag-0-py3-none-any.whl`
- `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` → `Documentation built in 0.21 seconds`
- `uv run pytest -q` → `425 passed in 1.18s`
- `uv run pytest --cov=semvertag --cov-branch -q` → `TOTAL 1072 73 310 36 92%`; branch_prefix.py / conventional_commits.py / doctor/_checks.py / doctor/_render.py all 100% branch
- Snippet smoke (`re.search` + `yaml.safe_load` extraction from `docs/providers/gitlab.md`) → `Quick Start snippet parses OK; keys: ['include', 'semvertag', 'stages']`; drift check `Inputs drift check OK`
- AC11 do-not-touch diff → empty
- `.gitlab/` directory absence verified (`ls /Users/kevinsmith/src/pypi/autosemver/.gitlab` → `No such file or directory`)

### Completion Notes List

- **OQ1 resolved at dev start (preempting code-review):** descriptor path is `templates/semvertag.yml`, NOT `.gitlab/catalog/component.yml`. Rationale: GitLab Catalog ingestion strictly scans `templates/` (Context7-verified). Sarah's call captured at user-question time before any file was written. Architecture.md / epics.md still carry the old prescription; deferred to a future amendment story.
- **AC1**: NEW `templates/semvertag.yml` at repo root (15 LOC YAML). Two-document layout (`spec:` + `---` + `semvertag` job). Include-ref shape consumers will use: `$CI_SERVER_FQDN/<org>/semvertag/semvertag@v1`.
- **AC2**: One input `strategy`, typed `string`, options `[branch-prefix, conventional-commits]`, default `branch-prefix`. No `token`, no `gitlab_endpoint`, no `project_id` — all env-driven via the existing settings-layer alias chains.
- **AC3**: `image: python:3.13-slim`, `variables: { SEMVERTAG_STRATEGY: $[[ inputs.strategy ]] }`, `before_script: [pip install --quiet --no-cache-dir uv]`, `script: [uvx semvertag]`. Job named `semvertag`. No `stage:`, no `rules:`, no `dependencies:`/`needs:`.
- **AC4**: No `branding:` / `icon:` / `color:` / `metadata:` block. Catalog has no equivalent surface.
- **AC5**: Inline Python heredoc in `ci.yml`'s `lint` job validates the two-document layout, the `spec.inputs.strategy` shape (type, default, options), and the job body's required keys (`image`, `variables`, `before_script`, `script`) including the `$[[ inputs.strategy ]]` substitution literal. `check-jsonschema --builtin-schema` not applicable: no Catalog component schema upstream.
- **AC6**: NEW `docs/providers/gitlab.md` (~120 LOC markdown). Six H2 sections in canonical order (Quick Start / Inputs / Required permissions / Token scope / Branch-prefix vs conventional-commits / Troubleshooting). No preview banner.
- **AC7**: `mkdocs.yml` nav: `GitLab CI: providers/gitlab.md` inserted alphabetically before `GitHub Actions: providers/github.md` under the existing `Providers:` block. +1 LOC. Theme/palette/markdown_extensions/extra byte-stable.
- **AC8**: descriptor uses only keys stable across GitLab 17.0 → 18.x; no experimental keys (`regex`, `image:name:`, `required: true + default:`).
- **AC9**: Catalog publish mechanism is NOT added in this story. Three options enumerated in deferred-work; story 4.7 (or a future story) owns the decision. The descriptor lands first because it's a static artifact correct regardless of publish-path choice.
- **AC10**: Inputs table in `docs/providers/gitlab.md` mirrors `spec.inputs.strategy` character-identically. Drift check passed.
- **AC11**: do-not-touch diff EMPTY. `.gitlab/` not created. `action.yml` and `docs/providers/github.md` untouched.
- **AC12**: all gates green (see Debug Log References).
- **AC13**: `ci.yml` change is exactly the new step; byte-stable elsewhere.
- **AC14**: pending PR/CI run; local gates are the v1.0 proxy.

### File List

| Path | Action | Summary |
|---|---|---|
| `templates/semvertag.yml` | **NEW** | 15 LOC YAML. GitLab CI Catalog component: `spec.inputs.strategy` (typed string, options `[branch-prefix, conventional-commits]`, default `branch-prefix`) + `---` + `semvertag` job (`image: python:3.13-slim`, `variables.SEMVERTAG_STRATEGY: $[[ inputs.strategy ]]`, `before_script: pip install --quiet --no-cache-dir uv`, `script: uvx semvertag`). |
| `docs/providers/gitlab.md` | **NEW** | ~120 LOC markdown. Six H2 sections per AC6. Canonical `.gitlab-ci.yml` include snippet, Inputs table mirroring the descriptor, Token-scope guidance for `CI_JOB_TOKEN` opt-in / PAT alternative / `SEMVERTAG_GITLAB__ENDPOINT` for self-hosted, four troubleshooting bullets. No preview banner. |
| `mkdocs.yml` | **UPDATE** | +1 LOC: `GitLab CI: providers/gitlab.md` leaf inserted alphabetically before `GitHub Actions: providers/github.md`. Rest byte-stable. |
| `.github/workflows/ci.yml` | **UPDATE** | +28 LOC: new `Validate templates/semvertag.yml shape` step in the `lint` job, between 4-3a's `Validate action.yml against GitHub Actions schema` step and `uv build`. Inline Python heredoc; structural sanity check (no upstream schema available). Rest byte-stable. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `4-3b-gitlab-ci-catalog-component: ready-for-dev → review`. `last_updated` + `last_updated_note` re-written. |
| `_bmad/4-3b-gitlab-ci-catalog-component.md` (this file) | **UPDATE** | Status flip; tasks 1-8 checked off; Dev Agent Record filled; File List + Change Log filled. Plus a one-byte eof-fixer normalization (trailing newline). |
| `action.yml` (Story 4.3a) | NO-CHANGE | Untouched. AC11 verified. |
| `docs/providers/github.md` (Story 4.3a) | NO-CHANGE | Untouched. AC11 verified. |
| `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `LICENSE`, `docs/index.md`, `docs/contributing/`, `docs/requirements.txt`, `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `context7.json`, `CLAUDE.md` | NO-CHANGE | AC11 do-not-touch list — `git diff HEAD` against all 14 paths is EMPTY. |
| `.gitlab/` (architecture-suggested path) | NO-CHANGE | Directory not created, per Constraint 1 + OQ1 resolution. |

### Change Log

1. **2026-05-30 (Sarah's call before file writes):** OQ1 resolved → use `templates/semvertag.yml` (canonical GitLab Catalog discovery path). Architecture.md:1067-1069 and epics.md:779 carry the now-known-wrong `.gitlab/catalog/component.yml` prescription; future docs amendment captured in deferred-work post-review.
2. **Task 1:** Authored `templates/semvertag.yml` (15 LOC). Decisions baked in: typed `string` input (Catalog v17.0+ feature), options enumeration `[branch-prefix, conventional-commits]` (matches `_settings.py:64` Literal), default `branch-prefix`. Job named `semvertag` to match the file-derived component name. `image: python:3.13-slim` (not vendored container, not `ghcr.io/astral-sh/uv`).
3. **Task 2:** Authored `docs/providers/gitlab.md`. Followed `github.md`'s six-section convention. Notable deviations from `github.md`:
   - No preview banner (GitLab provider is fully implemented per Epic 1).
   - "Required permissions" section names the full token alias chain (`SEMVERTAG_GITLAB__TOKEN` → `SEMVERTAG_TOKEN` → `CI_JOB_TOKEN` → `GITLAB_TOKEN`) since GitLab consumers will see all four behaviors.
   - Token-scope section adds a self-hosted-GitLab callout for `SEMVERTAG_GITLAB__ENDPOINT` (Petr-style consumers).
   - Troubleshooting bullets describe ACTUAL CLI/API error symptoms — verified against `semvertag/providers/gitlab.py` to avoid 4-3a's "fictional error strings" code-review finding.
4. **Task 3:** Inserted `GitLab CI: providers/gitlab.md` alphabetically before `GitHub Actions`. Single-line nav delta.
5. **Task 4:** Added inline Python heredoc step in `ci.yml`'s `lint` job after the 4-3a `Validate action.yml against GitHub Actions schema` step and before `uv build`. Rejected `check-jsonschema --builtin-schema vendor.gitlab-ci` (validates pipeline YAML, not Catalog components) and `--schemafile <URL>` (no community schema published). The structural check validates exactly the contract this story ships.
6. **Task 5:** All gates green: yaml.safe_load (2 docs), structural check (`shape OK`), lint-ci clean (after eof-fixer auto-normalization of this story file's trailing newline), `uv build` (sdist + wheel), `mkdocs --strict` (0.21s), pytest (425/425), branch coverage (100% on all gate-protected modules).
7. **Task 6:** Quick Start snippet extracted from markdown via `re.search` + `yaml.safe_load` — parses cleanly with keys `['include', 'semvertag', 'stages']`. Inputs table matches descriptor.
8. **Task 7:** Full file-list audit confirms strict AC11 compliance; do-not-touch diff is EMPTY; `.gitlab/` not created.
9. **Task 8:** Status flipped `ready-for-dev` → `review`. Dev Agent Record + File List + Change Log filled. Sprint-status.yaml synced.
10. **Open for code-review (OQ1 already resolved):** OQ2 (Catalog publish mechanism), OQ3 (schema-validate upgrade path), OQ4 (`docs/strategies/*` dead-link policy continuation), OQ5 (`SEMVERTAG_GITLAB__ENDPOINT` passthrough — kept as project CI variable, not surfaced as a component input), OQ6 (runbook amendment for first Catalog publish), OQ7 (PRD GitLab-version-floor 15.0+ → 17.0+ correction). Task 9 (deferred-work updates) intentionally left unchecked until code-review.
