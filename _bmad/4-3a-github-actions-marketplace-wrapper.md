# Story 4.3a: GitHub Actions Marketplace wrapper (`action.yml`)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Dani the Terraform module maintainer (PRD Journey 3),
I want to add semvertag to my GitHub Actions workflow with a 7-line YAML block referencing the Marketplace action,
So that "tag-only" adopters on GitHub get a one-liner integration path without writing a custom `run:` block — and so that **FR41** (Marketplace adoption) and **FR45** (Marketplace discoverability) are satisfied for v1.0.

## Acceptance Criteria

### AC1 — `action.yml` exists at the repo root with required Marketplace metadata

**Given** the repo root currently contains `pyproject.toml`, `Justfile`, `README.md`, `LICENSE`, `mkdocs.yml`, `.github/`, `docs/`, `semvertag/`, `tests/`, `_bmad/`, `_autosemver_reference/`, `.gitignore`, `.readthedocs.yaml`, `context7.json`, `CLAUDE.md` (no `action.yml`)
**When** Story 4.3a lands
**Then** a NEW file `action.yml` exists at the repo root with these top-level keys, in this order (mirroring the GitHub-docs canonical example):

1. `name:` — a short, human-readable name. **Must equal `'semvertag'`** to match the Marketplace listing slug and the PyPI package name. Marketplace rejects listings whose `name:` collides with another published action — see Constraint 2 below.
2. `description:` — one-sentence Marketplace tagline. Spec value: `'Auto-tag your repo with a SemVer git tag based on commits or branch prefixes — wraps the semvertag CLI.'` (≤ 125 chars; Marketplace UI truncates beyond ~125 in card views.)
3. `author:` — repository owner identifier. Value: `'<org>'` (placeholder; resolved by Story 4.7 per the cross-repo `<org>` convention — see Constraint 11).
4. `branding:` — see AC4.
5. `inputs:` — see AC2.
6. `runs:` — see AC3.

**And** there is **no** `outputs:` block. v1.0 does not surface a structured output; the semvertag CLI's exit code (0 success / non-zero failure) plus stdout/stderr are the only contract — matching the architecture's "single verb" CLI shape (`architecture.md:286`).

**And** there is **no** top-level `using:` key — `runs.using:` is the only `using:` (a common copy-paste error from JavaScript-action examples).

### AC2 — Inputs: exactly two, `strategy` and `token`, both optional

**Given** the epic AC's "single input `strategy`" requirement (`epics.md:759`)
**When** the action is invoked
**Then** `action.yml`'s `inputs:` block declares:

```yaml
inputs:
  strategy:
    description: 'Bump strategy. One of: branch-prefix (default), conventional-commits.'
    required: false
    default: 'branch-prefix'
  token:
    description: 'GitHub token with contents: write scope. Defaults to the workflow-issued github.token.'
    required: false
    default: ${{ github.token }}
```

**And** there are **no** other inputs. NO `working-directory`, NO `python-version`, NO `uv-version`, NO `debug`, NO `extra-args`. v1.0 keeps the surface minimal per Journey 3's "Single input: `strategy`. Done." narrative (`prd.md:211`).

**And** `inputs.token.default: ${{ github.token }}` is the **canonical** auto-token pattern for composite actions — `secrets.GITHUB_TOKEN` is NOT available inside a composite action's expression context (it's the *caller's* secrets context), so the action MUST read the token via `${{ github.token }}` or an explicit input. The `default: ${{ github.token }}` pattern lets the caller omit `with.token:` entirely and the action still gets the workflow-issued token — that's what makes Journey 3's 7-line snippet work.

### AC3 — `runs.using: 'composite'` with three steps: setup-uv → run semvertag

**Given** the architecture mandates `astral-sh/setup-uv@v3` as the uv install path (`architecture.md:249, 594, 1349`) and `[project.scripts] semvertag = "semvertag.__main__:main"` (`pyproject.toml:28-29`) makes `uvx semvertag` work zero-install
**When** the action runs
**Then** `runs:` declares:

```yaml
runs:
  using: 'composite'
  steps:
    - uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
        cache-dependency-glob: ''   # no project lockfile here; consumer's repo is heterogeneous
    - name: Run semvertag
      shell: bash
      env:
        GITHUB_TOKEN: ${{ inputs.token }}
        SEMVERTAG_STRATEGY: ${{ inputs.strategy }}
      run: uvx semvertag
```

**And** every `run:` step inside the composite carries an explicit `shell:` field (GitHub Actions requires this for composite steps — workflow `defaults.run.shell: bash` does **not** apply inside composite actions; missing `shell:` is a hard parse error at run time). See Anti-pattern 1.

**And** the action does NOT pin a specific uv version on `setup-uv` (no `with.version:` key). Rationale: the consumer's caller workflow may already have set up uv (idempotent), and the action wants the latest stable to pick up any `uvx semvertag` improvements. `publish.yml` pins uv because it controls a write-scope OIDC token; the wrapper action runs in the consumer's `contents: write` context with no PyPI scope, so float-uv is acceptable. **Constraint:** revisit if `uvx semvertag` ever requires a uv-version-specific feature.

**And** the action does NOT include an `actions/checkout` step. The consumer's workflow is responsible for checkout (semvertag needs git history + tags, which the consumer's `actions/checkout@v4 with: fetch-depth: 0, fetch-tags: true` provides). Embedding checkout inside the composite would either (a) shadow the consumer's checkout (resulting in a wrong-ref state if they checked out a tag explicitly) or (b) double-clone. Document this in the runbook AC6.

**And** `SEMVERTAG_STRATEGY` is the canonical env-var path documented in `prd.md:199` ("Per-repo strategy selection via the `SEMVERTAG_STRATEGY` environment variable, settable as a project-level CI variable in GitLab CI (and equivalents in GitHub Actions / Bitbucket Pipelines)"). Using the env-var bridge (not a CLI flag) means the input maps onto an already-supported settings layer surface without inventing a new CLI flag in this story.

### AC4 — Marketplace `branding:` icon + color

**Given** Marketplace shows each action's `branding.icon` (a Feather Icon name) and `branding.color` (one of `white | yellow | blue | green | orange | red | purple | gray-dark`) as the card badge
**When** `action.yml` is written
**Then** the `branding:` block is:

```yaml
branding:
  icon: 'tag'      # Feather: tag — matches the action's verb (creates a tag)
  color: 'blue'    # neutral category color; matches FR45 "non-noisy" Marketplace presence
```

**And** the icon is **NOT** `git-commit`, `package`, `archive`, or `box` — those are taken by adjacent CI tooling categories (semantic-release, pypi-publish, gh-action-upload-artifact) and would muddy discoverability. `tag` is exact-fit for "this action makes a tag."

**And** the color is **NOT** `green` (already saturated in the CI/CD-success category) or `red` (signals danger/error). `blue` is the default-tier neutral pick.

**Anti-feature note:** Marketplace also accepts `icon: 'black'` — that's `gray-dark` in the color list; not an icon. The two enums are disjoint; do not cross them.

### AC5 — `action.yml` validates against the published schema in `ci.yml`

**Given** the epic AC's "validates against its schema (`actionlint` or equivalent) in `ci.yml`" requirement (`epics.md:769`) **and** Story 4.1 Constraint 13 / Story 4.2 Constraint 13 defer `actionlint` binary install in CI (`uvx actionlint` is the local gate only)
**When** Story 4.3a's `ci.yml` change lands
**Then** the existing `lint` job in `ci.yml` gains exactly **one** new step (inserted after `just install lint-ci` and before `uv build`):

```yaml
      - name: Validate action.yml against GitHub Actions schema
        run: |
          # JSON Schema validation via check-jsonschema (Python-based, runs via
          # uvx; no new binary install in CI; preserves Story 4.1 Constraint 13
          # by avoiding the actionlint Go binary). Uses the SchemaStore action.yml
          # schema, which tracks GitHub's published metadata syntax.
          uvx --from check-jsonschema check-jsonschema \
            --schemafile https://json.schemastore.org/github-action.json \
            action.yml
```

**And** the step is **NOT** added to `dependency-update.yml` or `publish.yml` (write-scope workflows are pin-disciplined; a network fetch to schemastore.org is acceptable in the read-only `lint` job but not in the OIDC-issuing publish job).

**And** the step is **NOT** added via a third-party GitHub Action wrapper (e.g., `rhysd/actionlint` or `reviewdog/action-actionlint`) — keeping the supply-chain surface at the four already-pinned actions in `ci.yml` (`actions/checkout@v4`, `extractions/setup-just@v2`, `astral-sh/setup-uv@v3`, `codecov/codecov-action@v5.5.1`, `pypa/gh-action-pip-audit@v1.1.0` — note: 5 actions, mistake-corrected). Adding a sixth action just to validate one YAML file is supply-chain over-investment.

**And** a Justfile recipe is **NOT** added for this validation. The recipe surface stays at the current 10 recipes (Story 4.2 Constraint 8 carry-over). The local equivalent is the same `uvx --from check-jsonschema check-jsonschema …` command, which a developer can run manually; documenting it in `CONTRIBUTING.md` is Story 4.6 scope.

### AC6 — A working consumer-side example workflow ships in `docs/providers/github.md`

**Given** the epic AC's "working example workflow is included in `docs/providers/github.md` (or equivalent) showing the 7-line `uses:` snippet from Journey 3" (`epics.md:761`) **and** `docs/providers/` does NOT yet exist
**When** Story 4.3a lands
**Then** a NEW file `docs/providers/github.md` exists with these sections (markdown headers verbatim; body content paraphrased here):

```markdown
# GitHub Actions

## Quick Start (7 lines)
## Inputs
## Required permissions
## Token scope: pushing tags from PRs vs main
## Branch-prefix vs conventional-commits
## Troubleshooting
```

**And** the **Quick Start** section MUST contain the Journey 3 7-line snippet, byte-equal to the form below (the snippet is the AC's reified deliverable — a maintainer should be able to copy-paste it):

```yaml
name: Auto-tag
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  tag:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          fetch-tags: true
      - uses: <org>/semvertag@v1
```

**And** the **Required permissions** section explicitly names `permissions: contents: write` and explains the consequence of omitting it (Journey 3's narrative: `"Token missing 'contents: write' permission."`). This is **not** a redundant statement — Journey 3 explicitly bakes in the discovery moment where Dani sees the error, adds the permission, and reruns successfully (`prd.md:213`).

**And** the **Inputs** section enumerates both `strategy` and `token` with the same defaults declared in `action.yml`. Drift between this doc and `action.yml` is an AC10 violation.

**And** the **Token scope** section addresses Journey 3's known footgun: the default `${{ github.token }}` cannot push to a protected branch in some org configurations, and a PR's token cannot push tags to upstream — caller must use a PAT or a GitHub App token in those cases. One paragraph; not a full security treatise (that's Story 4.6 SECURITY.md scope).

**And** the **Branch-prefix vs conventional-commits** section is a 2-paragraph routing guide: pick `branch-prefix` if the team merges PRs labeled `fix/`, `feat/`, `chore/`; pick `conventional-commits` if the team writes Conventional Commit messages on `main`. Links to `docs/strategies/branch-prefix.md` and `docs/strategies/conventional-commits.md` (Story 4.4 scope; until that lands, the links are dead but the explanation stands).

**And** the **Troubleshooting** section lists at minimum these failure modes, each with a one-paragraph mitigation: (a) "no GitLab provider found — set `SEMVERTAG_PROVIDER=github`" — actually: at FR41 v1.0 the GitHub provider is a stub (architecture §Provider Coverage), so this is a known-limit warning, not a fix; (b) "fetch-depth: 1 — semvertag finds no tags" (mitigation: set `fetch-depth: 0` + `fetch-tags: true` on checkout); (c) "branch is detached HEAD" (mitigation: `actions/checkout` defaults already handle this for `push:` events; for `release: published`, the action will be a no-op).

### AC7 — `mkdocs.yml` gains a `Providers → GitHub Actions` nav entry

**Given** the AC8/AC9 of Story 4.2 left `mkdocs.yml` at:
```yaml
nav:
  - Quick Start: index.md
  - Contributing:
    - Release runbook: contributing/release.md
```
**When** Story 4.3a lands
**Then** `mkdocs.yml` `nav:` gains a `Providers` section above `Contributing`:

```yaml
nav:
  - Quick Start: index.md
  - Providers:
    - GitHub Actions: providers/github.md
  - Contributing:
    - Release runbook: contributing/release.md
```

**And** the `mkdocs.yml` change is **only** to `nav:` — `theme:`, `palette:`, `markdown_extensions:`, `extra:` are preserved byte-identical (Story 4.2 AC9 precedent).

**And** Story 4.4 will expand the `Providers` section later (`GitLab CI` from 4.3b, plus per-strategy explainers from 4.4). 4.3a creates the section header + the GitHub leaf; 4.3b will add a sibling `GitLab CI: providers/gitlab.md` leaf. The two stories MUST NOT collide on `mkdocs.yml` — the dev should structure their edit to add **only** the `GitHub Actions:` line under `Providers:`, leaving the surrounding structure unambiguously open for 4.3b's later addition.

**And** `mkdocs build --strict` exits 0 against the new tree. The `docs/providers/` directory now contains one file (`github.md`) referenced from nav — no orphan, no warning.

### AC8 — `action.yml` is byte-stable against schema regeneration

**Given** the schema validator (check-jsonschema + schemastore) is the gate
**When** the same `action.yml` is validated locally and in CI
**Then** the schema-validator command exits 0 in both environments

**And** the `action.yml` carries **no schema-deviating extensions** — specifically: no `runs.using: 'node20'`, no `runs.main:`, no `runs.pre:`, no `runs.post:` (those are JavaScript-action keys, mutually exclusive with `runs.using: composite`); no `runs.image:`, no `runs.entrypoint:` (Docker-action keys, also mutually exclusive); no `outputs:` (AC1 prohibition; also costless in v1.0).

**And** any YAML quoting style is internally consistent — strings use single quotes for values containing only ASCII (`'branch-prefix'`, `'composite'`), and double quotes are reserved for strings containing apostrophes or expression interpolation context-sensitivity. Schema validation does not enforce style, but consistency matters for reviewability.

### AC9 — Marketplace publishing is triggered by the existing `release: published` workflow (no new automation in this story)

**Given** Story 4.2's `publish.yml` already fires on `release: published` (`publish.yml:3-6`) and publishes to PyPI **and** GitHub Marketplace auto-discovers `action.yml` at the **repo root** of any tagged release (no workflow step is needed to "publish" the action — Marketplace polls the release stream)
**When** the next release is cut per `docs/contributing/release.md`'s "Cutting a release" flow
**Then** the GitHub release event surfaces the Marketplace listing automatically; the `action.yml` becomes consumable as `uses: <org>/semvertag@v<X.Y.Z>` once GitHub Marketplace has processed it (typically within minutes per the epic AC, `epics.md:765`).

**And** Story 4.3a does **NOT** modify `publish.yml`. The publish workflow is byte-stable (Story 4.2 AC11/AC13 carry-over). The action's Marketplace presence is a GitHub-platform behavior triggered by `action.yml` existing at the tagged commit's root; no workflow step makes it so.

**And** the first Marketplace listing requires the maintainer to **opt in** via the GitHub release UI ("Publish this Action to the GitHub Marketplace" checkbox on the release draft form). The `docs/contributing/release.md` runbook (Story 4.2 ownership) MUST be amended in a **separate follow-up story** to document this one-time checkbox-toggle — 4.3a does not touch the runbook (Story 4.2 file-stability constraint).

### AC10 — `action.yml` and `docs/providers/github.md` are drift-free

**Given** the action's inputs are documented in two places — `action.yml`'s `inputs:` block and `docs/providers/github.md`'s "Inputs" section
**When** either is changed
**Then** both MUST be updated in the same commit. A drift in input name / default / description is a Marketplace UX failure (consumers paste the snippet from docs, the action doesn't accept the input, the workflow errors).

**And** the CI validation (AC5) catches schema-level drift in `action.yml`; the docs-level drift between the two surfaces is a code-review responsibility (no automated gate in 4.3a — a follow-up story could add a "scan docs/providers/*.md vs action.yml inputs:" smoke test, but that's not 4.3a scope).

### AC11 — No changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `LICENSE`, `docs/contributing/`, `docs/index.md`, `.gitlab/`

**Given** Story 4.3a is a Marketplace-wrapper story, **not** a refactor / feature / Python change / publish-workflow / GitLab change
**When** the story lands
**Then** `git diff HEAD --` against the above paths returns **empty**

**And** any "while we're in there" cleanup that would otherwise be appealing (e.g., bumping `dependency-update.yml`'s pinned SHAs to the latest stable, tidying `ci.yml`'s codecov fork-safe guard, adding a `just lint-action-yml` recipe) is **deferred** to a separate story or to `_bmad/deferred-work.md`. The dev should resist scope creep.

**And** the sibling Story 4.3b (GitLab CI Catalog component) ships `.gitlab/catalog/component.yml` separately — that file is **NOT** created in 4.3a, even though the architecture's tree (`architecture.md:1067-1069`) shows it. 4.3a and 4.3b are explicitly siblings; cross-touching is a scope error.

### AC12 — Local validation gates stay green

**Given** the dev runs the full local gate sweep before declaring `review` status
**When** the dev runs each of these
**Then** each exits 0:

- `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml` — schema validation gate (AC5 mirror)
- `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('action.yml'))"` — YAML parse gate (Story 4.1 / 4.2 precedent)
- `just lint-ci` — eof-fixer + ruff format + ruff check + ty check (unchanged from Story 4.2; no Python touched, but the gate confirms no incidental Python drift)
- `just test` — 425 passes (no Python touched; the gate confirms no incidental test drift)
- `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` — confirms `docs/providers/github.md` builds clean, nav resolves, no orphan files

**And** the CI counterparts of these gates pass on the PR — the `lint` job in `ci.yml` runs `mkdocs build --strict`, the schema-validation step (AC5), and the existing LOC gate.

### AC13 — All existing pre-Story-4.3a CI behaviors are preserved byte-identical

**Given** Story 4.1 polished `ci.yml` and Story 4.2 left it byte-stable
**When** Story 4.3a's `ci.yml` change lands
**Then** the only added content is the AC5 single-step block (the `Validate action.yml` step). The `lint` / `pytest` matrix / `pip-audit` jobs are otherwise byte-identical; the concurrency block, permissions block, and step ordering are preserved.

**And** the LOC gate (`ci.yml:31-59`) still passes — Story 4.3a adds **zero** Python LOC (no `semvertag/**/*.py` changes per AC11).

### AC14 — A green CI run on the PR demonstrates all jobs pass with the new files

**Given** the PR lands
**When** CI runs against the PR commit
**Then** the `lint`, `pytest` (matrix 3.10–3.14), and `pip-audit` jobs all pass

**And** the new schema-validation step from AC5 is included in the `lint` job's step output and exits 0

**And** local validation has already been performed per AC12 — CI is the final cross-check, not the discovery point.

## Tasks / Subtasks

- [x] **Task 1: Author `action.yml` at repo root (AC: 1, 2, 3, 4, 8)**
  - [x] 1.1 Create new `action.yml` at repo root with top-level keys in this order: `name:`, `description:`, `author:`, `branding:`, `inputs:`, `runs:`.
  - [x] 1.2 Set `name: 'semvertag'`, `description: 'Auto-tag your repo with a SemVer git tag based on commits or branch prefixes — wraps the semvertag CLI.'`, `author: '<org>'` (placeholder preserved per Constraint 11).
  - [x] 1.3 Add `branding:` block with `icon: 'tag'` and `color: 'blue'`.
  - [x] 1.4 Add `inputs:` block: `strategy` (default `'branch-prefix'`, required false) and `token` (default `${{ github.token }}`, required false). Verify both inputs have a non-empty `description:` (Marketplace UI rejects blank descriptions).
  - [x] 1.5 Add `runs:` block with `using: 'composite'` and three steps: (a) `astral-sh/setup-uv@v3` (with `enable-cache: true`, `cache-dependency-glob: ''`); (b) a `Run semvertag` step with `shell: bash`, `env: { GITHUB_TOKEN: ${{ inputs.token }}, SEMVERTAG_STRATEGY: ${{ inputs.strategy }} }`, and `run: uvx semvertag`.
  - [x] 1.6 Verify NO `outputs:` block, NO top-level `using:`, NO `runs.main:`/`runs.image:`/`runs.entrypoint:`. Verify EVERY composite step that uses `run:` carries an explicit `shell:` field (composite actions require it; missing `shell:` is a hard parse error at run time).
  - [x] 1.7 Run local schema validation: `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml` → exits 0.
  - [x] 1.8 Run local YAML parse: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('action.yml'))"` → no exception.

- [x] **Task 2: Author `docs/providers/github.md` (AC: 6, 10)**
  - [x] 2.1 Create new directory `docs/providers/` (no `__init__.py`-equivalent for mkdocs — empty dir is fine).
  - [x] 2.2 Create new file `docs/providers/github.md` with the six headers from AC6 verbatim.
  - [x] 2.3 In **Quick Start**, paste the 7-line snippet from AC6 exactly. Use a `yaml` code fence with no language-specific highlighting hints beyond `yaml`.
  - [x] 2.4 In **Inputs**, document `strategy` and `token` with descriptions and defaults that match `action.yml` byte-for-byte (AC10 drift check). Reference the action.yml file path: `[action.yml](https://github.com/<org>/semvertag/blob/main/action.yml)`.
  - [x] 2.5 In **Required permissions**, name `contents: write` and explain Journey 3's discovery moment (`prd.md:213`): the workflow fails with `Token missing 'contents: write' permission.` until the permission is added.
  - [x] 2.6 In **Token scope**, address the default-`github.token`-cannot-push-to-protected-branches footgun. One paragraph; link out to GitHub's auth docs (no direct URL — use a stable docs.github.com path).
  - [x] 2.7 In **Branch-prefix vs conventional-commits**, 2-paragraph routing guide. **Deviation from spec literal:** the spec's `[branch-prefix](../strategies/branch-prefix.md)` and `[conventional-commits](../strategies/conventional-commits.md)` links would trip `mkdocs build --strict` (AC12) because Story 4.4 has not landed yet — the targets don't exist. Implementation drops the link syntax and keeps the descriptive prose; flagged as OQ4 carry-forward for code-review.
  - [x] 2.8 In **Troubleshooting**, list AT LEAST the three failure modes from AC6: (a) GitHub provider stub limitation at v1.0; (b) `fetch-depth: 1` → no tags; (c) detached HEAD on `release:` triggers. Added a fourth bullet for the `<org>` placeholder resolution failure mode (consumers paste the snippet verbatim and don't realize `<org>` needs swapping).
  - [x] 2.9 The doc body is 60–120 LOC of markdown (similar order of magnitude to `docs/contributing/release.md`). Don't write a thousand lines; this is a Quick Start, not a manual.

- [x] **Task 3: Update `mkdocs.yml` nav (AC: 7)**
  - [x] 3.1 Open `mkdocs.yml`.
  - [x] 3.2 In `nav:`, insert a `Providers:` block between `Quick Start` and `Contributing`, with a single `GitHub Actions: providers/github.md` leaf entry.
  - [x] 3.3 Verify `theme:`, `palette:`, `markdown_extensions:`, `extra:` are preserved byte-identical via `git diff mkdocs.yml` — only the `nav:` block delta should appear.
  - [x] 3.4 Run `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` → exits 0, no warnings.

- [x] **Task 4: Add `action.yml` schema-validation step to `ci.yml`'s `lint` job (AC: 5, 13)**
  - [x] 4.1 Open `.github/workflows/ci.yml`.
  - [x] 4.2 In the `lint` job's `steps:`, insert ONE new step between `just install lint-ci` (line 28) and `uv build` (line 29):
    ```yaml
          - name: Validate action.yml against GitHub Actions schema
            run: |
              uvx --from check-jsonschema check-jsonschema \
                --schemafile https://json.schemastore.org/github-action.json \
                action.yml
    ```
  - [x] 4.3 Verify NO change to the `pytest` job or the `pip-audit` job.
  - [x] 4.4 Verify NO change to the workflow's `name:`, `on:`, `concurrency:`, `permissions:`, or existing step ordering.
  - [x] 4.5 Run `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` → no exception.

- [x] **Task 5: Local gate sweep (AC: 12, 14 readiness)**
  - [x] 5.1 Run `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml` → exits 0 (`ok -- validation done`).
  - [x] 5.2 Run `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('action.yml'))"` → `YAML OK`.
  - [x] 5.3 Run `just lint-ci` → exits 0 (eof-fixer + ruff format + ruff check + ty check).
  - [x] 5.4 Run `just test` → 425 passed in 1.18s (baseline preserved).
  - [x] 5.5 Run `just test-branch-strategies` (26/26, 100% branch) / `just test-cc-strategies` (44/44, 100% branch) / `just test-doctor` (56/56, 100% branch) → all pass.
  - [x] 5.6 Run `uv run ty check` → clean.
  - [x] 5.7 Run `uv build` → clean (`dist/semvertag-0.tar.gz` + `dist/semvertag-0-py3-none-any.whl`; pre-existing `uv_build` upper-bound warning is the template-inherited `_bmad/deferred-work.md §1-1` item, out of scope).
  - [x] 5.8 Run `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` → exits 0 in 0.22s (new `providers/github.md` page included; nav resolves clean; no orphan files).
  - [x] 5.9 Run `git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md LICENSE docs/index.md docs/contributing/ .github/workflows/publish.yml .github/workflows/dependency-update.yml .gitlab/` → empty (AC11 drift check passes).

- [x] **Task 6: Marketplace snippet smoke check (AC: 6 reified)**
  - [x] 6.1 Quick Start YAML block extracted in-place via a `re.search` + `yaml.safe_load` script (no scratch file needed — same gate, no committed-file risk).
  - [x] 6.2 `yaml.safe_load` on the extracted block returns a parsed structure (no exception).
  - [x] 6.3 Snippet contains the literal `<org>` placeholder, `uses: actions/checkout@v4`, and `contents: write` — all three pre-flight markers present.
  - [x] 6.4 N/A — no scratch file was created (sub-step 6.1 substituted an in-memory extraction).

- [x] **Task 7: Pre-review file-list audit (AC: 1, 11)**
  - [x] 7.1 `git status --short` shows exactly: NEW `action.yml`, NEW `docs/providers/` (containing `github.md`), MODIFIED `mkdocs.yml`, MODIFIED `.github/workflows/ci.yml`, MODIFIED `_bmad/sprint-status.yaml`, MODIFIED `_bmad/4-3a-github-actions-marketplace-wrapper.md`. Nothing else.
  - [x] 7.2 `_bmad/deferred-work.md` is NOT staged. Task 9 is post-review-only per spec.

- [x] **Task 8: Update Dev Agent Record + Status (AC: meta)**
  - [x] 8.1 Fill in `Dev Agent Record` → `Agent Model Used` with the active model id.
  - [x] 8.2 Append a `Debug Log References` section with each gate's exit confirmation.
  - [x] 8.3 Fill in `Completion Notes List` with per-AC verification statements (mirrors Story 4.2's format).
  - [x] 8.4 Fill in `File List` table: each touched file with `NEW` / `UPDATE` / `NO-CHANGE` action and a one-line summary.
  - [x] 8.5 Fill in `Change Log` with the chronological list of dev decisions.
  - [x] 8.6 Flip Status from `ready-for-dev` → `in-progress` → `review`.

- [ ] **Task 9: Post-review — update `_bmad/deferred-work.md` (admin)**
  - [ ] 9.1 Append `## Deferred from: code review of 4-3a-github-actions-marketplace-wrapper (YYYY-MM-DD)` with any non-blocking decisions / discovered edge cases.
  - [ ] 9.2 Cross-link the closure (or non-closure) of these prior deferred items:
    - From `_bmad/deferred-work.md §4-2` (Story 4.2 review deferrals) — none are 4.3a-relevant; this story does NOT touch publish.yml.
    - From `_bmad/deferred-work.md §1-1` line 12 (`<org>` URL placeholders) — Story 4.3a perpetuates the placeholder (Constraint 11); item stays open until Story 4.7.
  - [ ] 9.3 Specifically capture: (a) whether the schemastore.org schema URL needs an SHA/version pin (today it tracks the schema repo's `main`; a future schema-incompatibility could break the gate without any commit to this repo); (b) whether `check-jsonschema` itself should be version-pinned in CI (matches Story 4.2's uv-version-pin decision pattern); (c) whether a follow-up story should add a Justfile recipe `lint-action-yml` once a second action-style file lands (e.g., 4.3b's GitLab catalog descriptor, which uses a different schema).

> **Note**: Task 9 (deferred-work updates) is gated on code-review per its own header ("Post-review"); intentionally left unchecked until code-review lands. Mirrors Story 4.2 Task 11 discipline.

## Dev Notes

### Story framing

Story 4.3a is the **third story of Epic 4** (Public-Launch Readiness) and one of the two parallel siblings under implementation-sequence step 9's "Trust-surface scaffolding / Distribution channels" branch (`architecture.md:594`). The two siblings are:

- **4.3a** (this story): GitHub Actions Marketplace wrapper (`action.yml`).
- **4.3b** (next story per sprint): GitLab CI Catalog component (`.gitlab/catalog/component.yml`).

They are independent and orthogonal — neither blocks the other; both can land in any order. Sequencing 4.3a before 4.3b is a sprint-status ordering choice, not a technical dependency.

The work is **entirely at the repo root + `docs/providers/` + `.github/workflows/ci.yml` + `mkdocs.yml`** — zero changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `publish.yml`, `dependency-update.yml`, or any existing doc page.

The epic ACs (`epics.md:749-770`) are 3 narrative G/W/T triplets covering:
1. `action.yml` exists at root, accepts `strategy` input, reads `GITHUB_TOKEN`, shells out to `uvx semvertag`, has Marketplace metadata, and ships with a working example in `docs/providers/github.md`.
2. The release process publishes the Marketplace listing — already handled by Story 4.2's `publish.yml` `release: published` trigger (GitHub Marketplace polls release events; no new workflow step needed).
3. `action.yml` validates against its schema in `ci.yml`.

These three narratives expand to 14 dev-facing ACs above (mirrors Story 4.2's granularity discipline).

The PRD anchors:
- **FR41** — "User can adopt semvertag in GitHub Actions via the published Marketplace action wrapper (v1.0)" (`prd.md:554`).
- **FR45** — Marketplace presence as a discoverability channel (`prd.md:561`).
- **Journey 3** — Dani the Terraform maintainer searches "github actions auto semver python", finds semvertag on the Marketplace, pastes a 7-line workflow (`prd.md:211-220`).
- **NFR19** — auto-detected provider-native context via `GITHUB_TOKEN` (`prd.md:597`).

### Critical architectural constraints

1. **No source-code changes — `action.yml` + docs + nav + one ci.yml step only.** Story 4.3a is **NOT** a Python feature, **NOT** a refactor, **NOT** a test addition. The dev should resist any temptation to "while we're in there" tidy `semvertag/`, `pyproject.toml`, or `Justfile`. The story's value is the Marketplace surface — not code.

2. **Action name MUST be exactly `'semvertag'` and is global on Marketplace.** GitHub Marketplace rejects two actions with the same `name:` field across all of Marketplace (not just within an org). At first publish, the maintainer will see one of: (a) name accepted and the listing claims the `semvertag` slug; (b) name rejected because someone already published `semvertag` — in which case the action's identity collapses against the PyPI package name and we have a real product-naming problem. **Pre-publish check:** maintainer searches https://github.com/marketplace/?type=actions&query=semvertag and confirms the slug is unclaimed; if claimed, this becomes a naming-decision blocker that must be resolved before the first release. (Out of scope for this story to perform the search; in scope to flag the dependency.)

3. **Composite action, NOT JavaScript action and NOT Docker action.** The architecture's `astral-sh/setup-uv@v3` + `uvx semvertag` pattern is explicit (`architecture.md:594, 1349`). A JavaScript action would require us to write JS, which violates the "Python-only repo" stance (`prd.md` PRD §Code Organization). A Docker action would require us to build and publish a container image, which adds a release surface (Docker Hub or ghcr.io) the v1.0 distribution model explicitly excludes (`architecture.md:1347-1351`). Composite is the only fit.

4. **`uvx semvertag` (NOT `uv run semvertag`, NOT `pip install semvertag && semvertag`).** `[project.scripts] semvertag = "semvertag.__main__:main"` in `pyproject.toml:28-29` exposes `semvertag` as an installable console script. `uvx semvertag` is the canonical "install ephemerally + run" invocation — equivalent to `pipx run semvertag` but inside the uv toolchain. `uv run semvertag` would need a local project context (the consumer's repo isn't a semvertag project), and `pip install semvertag` would leak persistent state into the runner. `uvx` is the cleanest fit.

5. **Composite step `shell:` is mandatory and non-inheriting.** GitHub Actions composite steps require an explicit `shell:` on every `run:` step. Workflow-level `defaults.run.shell: bash` does **NOT** apply inside composite actions — the action's `runs.steps[*].run` steps need their own `shell:` field. Missing `shell:` is a hard parse error at action run time, surfacing as `"Required property 'shell' missing"` in the consumer's workflow log. Easy regression target if the dev copy-pastes from a non-composite example.

6. **`${{ inputs.token }}` default = `${{ github.token }}`, not `${{ secrets.GITHUB_TOKEN }}`.** Inside a composite action, the `secrets:` context refers to the **consumer's** secrets, not the action repo's secrets. The workflow-issued token is exposed via `${{ github.token }}` — the canonical pattern for auto-token defaults in composite actions. Mixing `secrets.GITHUB_TOKEN` here would fail to resolve when the action is invoked by a fork PR (where `secrets:` is intentionally locked down). See AC2 above and the Context7 GitHub Actions docs (`/websites/github_en_actions` — `Pass GITHUB_TOKEN as input to GitHub CLI action`).

7. **No `actions/checkout` step inside the composite.** The consumer's workflow owns checkout (with `fetch-depth: 0` + `fetch-tags: true` for tag history). Adding checkout inside the action would either shadow the consumer's checkout state or double-clone — both are observable user-facing bugs. Document the consumer-owned checkout in `docs/providers/github.md`'s Quick Start (AC6).

8. **No uv-version pin on `setup-uv` inside the action.** Unlike Story 4.2's `publish.yml` (which pins `setup-uv` to `0.11.17` for OIDC-scope determinism), `action.yml` runs in the consumer's read+write-to-their-repo context with no PyPI scope. The trade-off favors picking up `uvx semvertag` improvements (uv version floats) over reproducibility (uv version locks). Re-evaluate if `uvx semvertag` ever depends on a specific uv feature.

9. **Schema validation via `uvx --from check-jsonschema check-jsonschema`, not actionlint.** Story 4.1 Constraint 13 / Story 4.2 Constraint 13 defer adding the actionlint Go binary to CI. `check-jsonschema` is a Python tool that already runs through `uvx` (the same install path as other lint-ci tools), with no new binary, no new third-party action. The schemastore.org schema URL it validates against (`json.schemastore.org/github-action.json`) tracks GitHub's published metadata syntax (`github_en_actions`). The trade-off: schemastore lags GitHub's docs by hours-to-days, so a brand-new GitHub field would not validate until the schema catches up — acceptable for FR41 v1.0.

10. **`docs/providers/github.md` is the FIRST page in `docs/providers/`.** Story 4.3b will add `docs/providers/gitlab.md`; Story 4.4 will add per-strategy pages (`docs/strategies/*.md`). The mkdocs nav structure created here (a `Providers:` section header) MUST be open to extension by 4.3b — concretely, the dev should add the nav lines in a way that 4.3b can insert a sibling line under the same `Providers:` block without re-indenting (see Task 3.2 + AC7).

11. **`<org>` placeholder preserved in `action.yml.author`, `docs/providers/github.md` snippet, and `docs/providers/github.md` link URLs.** Per Story 4.7 ownership and the pre-launch convention carried by every prior story. Story 4.3a does NOT substitute the real org name; that's a coordinated, repo-wide swap done in Story 4.7. **Reality check:** the first GitHub release tagged before Story 4.7 lands will have the `<org>` placeholder in its Marketplace listing — a maintainer following the runbook MUST do the swap before cutting the first real release. The Story 4.2 runbook now contains a `> Note: Replace <org> …` instruction (post-code-review patch landed 2026-05-30); 4.3a does not duplicate that note.

12. **No Marketplace publish automation.** GitHub Marketplace polls release events; `action.yml` at the tagged commit's root makes the action consumable as `uses: <org>/semvertag@v<X.Y.Z>` automatically. There is **no** GitHub Action that "publishes to Marketplace" — the listing arises from the existence of `action.yml` + the `release: published` event. Story 4.3a adds **zero** lines to `publish.yml`.

13. **Marketplace listing requires a one-time opt-in checkbox in the release UI.** When the maintainer drafts the first release, the GitHub release UI shows a "Publish this Action to the GitHub Marketplace" checkbox. The checkbox must be ticked once; subsequent releases auto-update the Marketplace listing. This is a runbook addition for `docs/contributing/release.md` — but that file is Story 4.2 territory and is NOT touched in 4.3a. The runbook amendment is captured as a follow-up in `_bmad/deferred-work.md §4-3a` post-review.

14. **CI schema-validation step is in the `lint` job, NOT a new job.** Adding a new top-level job for one step would be over-engineering. The `lint` job already runs `actions/checkout` + `astral-sh/setup-uv@v3`, which is exactly what the schema-validation needs. The new step adds ~5s to the `lint` job; net-net cheaper than a new job's startup cost.

15. **No `outputs:` on the action.** v1.0 surfaces no structured output — the semvertag CLI exits 0 on success, non-zero on failure. A consumer who wants to read the new tag value can grep stdout. Adding `outputs:` would require a `tag:` capture step inside the composite, which adds complexity for a use case that's not in any Journey. Defer to a v1.x story if a real consumer asks.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `action.yml` | **NEW** | ~30 LOC YAML. Top-level `name`, `description`, `author`, `branding`, `inputs` (2), `runs.using: composite` (3 steps). |
| `docs/providers/github.md` | **NEW** | 60–120 LOC markdown. Six sections per AC6. Contains Journey 3's 7-line consumer snippet verbatim. |
| `docs/providers/` | **NEW** (implied) | Empty directory — mkdocs builds against `docs_dir` so the dir gets walked. No `__init__.py` analogue needed. |
| `mkdocs.yml` | **UPDATE** | Add `Providers:` section under `nav:` with one leaf (`GitHub Actions: providers/github.md`). 4 LOC delta. Theme / palette / extras byte-stable. |
| `.github/workflows/ci.yml` | **UPDATE** | Add ONE step to the `lint` job: `Validate action.yml against GitHub Actions schema` running `uvx --from check-jsonschema check-jsonschema …`. ~5 LOC delta. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `4-3a-github-actions-marketplace-wrapper: backlog → ready-for-dev → in-progress → review → done`; `last_updated` + `last_updated_note`. |
| `_bmad/4-3a-github-actions-marketplace-wrapper.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| `_bmad/deferred-work.md` | **UPDATE** (post-review only) | Append `## Deferred from: code review of 4-3a-…` with non-blocking decisions / discovered edge cases. |
| **Do-not-touch** (Epic 4.3a scope guardrails) | — | All `semvertag/**/*.py`, all `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `.gitignore`, `docs/index.md`, `docs/contributing/`, `docs/requirements.txt`, `context7.json`, `LICENSE`, `CLAUDE.md`, `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `.gitlab/` (Story 4.3b sibling). |

### Anti-patterns to avoid

(Architecture §Anti-Patterns + GitHub Actions composite-action canonical patterns + Story 4.1/4.2 inherited discipline.)

1. **Missing `shell:` on composite-action `run:` steps** — Composite actions require an explicit `shell:` on every `run:` step. `defaults.run.shell` at the consumer's workflow level does NOT propagate into the action. Missing `shell:` is a hard parse error at run time, surfacing as `"Required property 'shell' missing"` in the consumer's workflow log. Easy regression target.

2. **`${{ secrets.GITHUB_TOKEN }}` inside the composite** — `secrets:` context is **not** available inside a composite action (the action repo has no access to the consumer's secrets). Use `${{ github.token }}` or read from an explicit `inputs.token`. Mixing `secrets.GITHUB_TOKEN` would fail to resolve at run time, breaking fork-PR consumers.

3. **`runs.using: 'node20'` / `runs.main:` keys** — JavaScript-action keys; mutually exclusive with `runs.using: 'composite'`. Schema validation (AC5) will catch this; would still be a sign the dev copy-pasted from a JS-action example.

4. **`runs.image:` / `runs.entrypoint:`** — Docker-action keys; mutually exclusive with `runs.using: 'composite'`. Same as above.

5. **`actions/checkout` inside the composite** — Constraint 7 above. Consumer owns checkout. Embedding it inside the action shadows the consumer's checkout state.

6. **`uvx semvertag --strategy ${{ inputs.strategy }}` as a CLI flag instead of `SEMVERTAG_STRATEGY` env var** — Per PRD `prd.md:199`, the env-var path is the canonical "per-repo strategy" surface across all CI providers. Using a CLI flag couples the action to a specific CLI-flag name and bypasses the settings-layer's `AliasChoices` chain (FR26). The env-var bridge is the cleaner integration point and matches the GitLab catalog component (Story 4.3b) pattern.

7. **Pinning `astral-sh/setup-uv@<SHA>` inside `action.yml`** — Constraint 8 above. The action runs in the consumer's contents-write context with no PyPI scope; the blast-radius asymmetry that justifies SHA-pinning in `publish.yml` doesn't apply here. Tag-pinning (`@v3`) matches `ci.yml`'s pin discipline for read-scope contexts.

8. **Adding `outputs:` "for future-proofing"** — Constraint 15 + AC1 prohibition. No Journey asks for structured outputs in v1.0. Adding an unused output ships dead surface that consumers might depend on accidentally.

9. **Embedding the schema validation as a third-party action wrapper (e.g., `rhysd/actionlint@v1`)** — AC5 explicit. Add a sixth pinned action to `ci.yml` for one validation? Supply-chain over-investment. The `uvx --from check-jsonschema` path uses the existing `astral-sh/setup-uv@v3` install and `python` runtime — zero new dependencies.

10. **Pinning the schemastore.org schema URL to a SHA** — Tempting (Story 4.2 SHA-pin discipline), but schemastore.org schemas don't expose stable SHA-pinned download URLs in a per-schema-version way. The schema is a moving target on `main`; if a future schema-incompatibility breaks the gate, that's a follow-up decision (capture in `_bmad/deferred-work.md` post-review). Don't pre-optimize for a problem that hasn't manifested.

11. **Adding `dependabot.yml` entries for `action.yml`** — Out of scope. Dependabot can update tag pins inside `action.yml` (e.g., `astral-sh/setup-uv@v3` → `@v4` if v4 ships), but configuring dependabot is its own decision and would also touch `dependency-update.yml`'s SHA-pin discipline. Defer.

12. **`name: 'Semvertag'` (capitalized) or `name: 'semvertag-action'`** — Marketplace `name:` IS the user-facing slug. Capitalize once, you live with it forever. The PyPI package is `semvertag` (lowercase); the GitHub repo is `<org>/semvertag` (lowercase); the Marketplace listing slug should also be lowercase `semvertag` for consistency across surfaces. The `-action` suffix is redundant — the Marketplace category disambiguates.

13. **Adding `if:` conditions on the composite steps** — composite steps don't support `if:` the same way job steps do (they support per-step `if:` in modern GitHub Actions, but the semantics are subtle — `if:` checks evaluate against the **calling workflow's** expression context, not the action's). For v1.0 there's no need; both composite steps always run. Adding speculative `if:` clauses is over-engineering.

14. **Marketplace "logo" / "image" / "screenshots"** — Not part of `action.yml` schema. Marketplace pulls visual assets from the README at the tagged commit (Story 4.7's hero), the `branding:` block (AC4), and the GitHub repo's own social-preview image (set in repo settings, not in `action.yml`). Don't add image fields to `action.yml`; they'll fail schema validation.

15. **A `just lint-action-yml` recipe** — Constraint 14 above (in spirit). Story 4.2 Constraint 8 carried Story 4.1's anti-recipe-bloat discipline forward; Story 4.3a continues it. Adding a recipe for one CI step is recipe surface that the dev runs manually as a one-liner. If a second action-yml-style file lands (e.g., 4.3b's catalog component), revisit whether a shared lint recipe is worth its weight.

### Library / framework specifics

#### `action.yml` schema (GitHub Actions metadata syntax)

Authoritative source: [`docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax`](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax) (also accessible via Context7 library id `/websites/github_en_actions`).

Required top-level keys: `name`, `description`. All others are optional but Marketplace-discovery requires `branding` (else the action is a generic "internal" action without a card).

Composite action shape (Context7 canonical example):

```yaml
name: 'Hello World'
description: 'Greet someone'
inputs:
  who-to-greet:
    description: 'Who to greet'
    required: true
    default: 'World'
runs:
  using: "composite"
  steps:
    - name: Set Greeting
      run: echo "Hello $INPUT_WHO_TO_GREET."
      shell: bash
      env:
        INPUT_WHO_TO_GREET: ${{ inputs.who-to-greet }}
```

Note the `INPUT_` prefix convention is NOT required — env names can be anything as long as the `env:` block maps them — but it matches GitHub's own examples. Story 4.3a uses `SEMVERTAG_STRATEGY` (no prefix) because that's the existing settings-layer env-var name the CLI already reads (`prd.md:199`).

`branding` schema (Context7 canonical):

```yaml
branding:
  icon: 'tag'      # Feather Icons name; see https://feathericons.com
  color: 'blue'    # one of: white | yellow | blue | green | orange | red | purple | gray-dark
```

`branding.icon` is the Feather Icons free icon library — names like `tag`, `package`, `box`, `git-commit`, `award`. `branding.color` is a tightly enumerated set; passing a hex code fails schema validation.

`runs.using: 'composite'` mutually exclusive keys (Marketplace-rejecting):
- Cannot use `runs.main`, `runs.pre`, `runs.post` (those are JS-action keys).
- Cannot use `runs.image`, `runs.entrypoint`, `runs.args` (those are Docker-action keys).
- Can use `runs.steps[]` exclusively.

#### `check-jsonschema` (Python tool, validates YAML/JSON against JSON Schema)

Authoritative source: [`check-jsonschema on PyPI`](https://pypi.org/project/check-jsonschema/) (~7M monthly downloads, maintained by pre-commit org).

Invocation pattern (used in AC5):

```bash
uvx --from check-jsonschema check-jsonschema \
  --schemafile https://json.schemastore.org/github-action.json \
  action.yml
```

- `uvx --from check-jsonschema` — installs the `check-jsonschema` package and runs it ephemerally. The `--from <package>` flag is required because the package's console script is named `check-jsonschema` (matches the package name), but uvx defaults to `<name>` → `<name>` and might otherwise try `uvx check-jsonschema-pkg` or similar. Belt-and-suspenders form.
- `--schemafile <url>` — fetches the schema. The check-jsonschema tool also has a built-in `--builtin-schema vendor.github-actions` shorthand that ships the schema offline; both work. Spec uses the URL form to track upstream schema updates.
- Final positional arg is the file under test.

Exit code 0 = pass; non-zero = fail. Standard error includes the validation error message; standard output is the schema diagnostics.

#### `setup-uv` (composite vs caller install idempotency)

If the consumer's workflow already ran `astral-sh/setup-uv@v3` before invoking the action, the second `setup-uv` inside the composite is a no-op (uv is already on `$PATH` and cached). No collision, no error. The architecture's "uvx zero-install" model (`product-brief:56`) tolerates this gracefully.

If the consumer's runner has uv pre-installed (e.g., on `ubuntu-latest` runners after a future GitHub change), `setup-uv` short-circuits. Belt and suspenders.

### Previous story intelligence (Story 4.2 — landed `db476d3 land story 4.2`, 2026-05-30)

Story 4.2 landed the PyPI trusted-publishing workflow plus the release runbook. Specific learnings the 4.3a dev should absorb:

1. **SHA-pin discipline is workflow-class-specific.** Story 4.2 SHA-pinned every action in `publish.yml` because that workflow holds `id-token: write`. Story 4.3a's `action.yml` runs in the consumer's read+write-their-repo context (no PyPI scope) — tag-pinning is acceptable here, matching `ci.yml`'s discipline. Don't import the publish-workflow discipline reflexively.

2. **Schema validation as a CI gate is feasible without new binaries.** Story 4.2 used `yaml.safe_load` as the fallback because `actionlint` wasn't acceptable. Story 4.3a's `check-jsonschema` invocation is the next-level evolution of that fallback — full schema validation, still no Go binary. If Story 4.3b (sibling) chooses a different validator for the GitLab catalog component, that's their call; the precedent set here is "Python tool via uvx, no new third-party action."

3. **`mkdocs.yml` nav expansions are cheap when the dev sticks to scope.** Story 4.2 added a 2-line `Contributing → Release runbook` entry; Story 4.3a adds a 4-line `Providers → GitHub Actions` entry. The convention is established: each story that ships a new top-level docs section adds exactly its section's nav lines, nothing else. Don't speculate about Story 4.4's mkdocs nav layout.

4. **`<org>` placeholder is universal until Story 4.7.** Story 4.2's code review added a `> Note: Replace <org> …` instruction to `docs/contributing/release.md`. Story 4.3a's `docs/providers/github.md` may need a similar one-liner — but check the existing runbook content first; a single repo-wide note linked from the providers doc might be cleaner than duplicating per-doc notes.

5. **Local gate sweep is the discovery point, CI is the cross-check.** Story 4.2's dev ran the full gate sweep locally before declaring `review`. Story 4.3a's AC12 makes this explicit — the dev does NOT push and wait for CI to discover schema errors; they validate locally first. CI confirms.

6. **Deferred-work entries are written post-review only.** Story 4.2 Task 11 (now closed) was intentionally unchecked at dev-complete time; the same pattern applies to Story 4.3a Task 9. Don't pre-fill `_bmad/deferred-work.md` with speculative items.

7. **The Story 4.2 spec evolved through 14 patches during code review.** Half were docs clarifications, half were workflow-YAML hardenings. Story 4.3a's smaller surface (one `action.yml` + one provider doc + one ci.yml step + one nav line) should require **fewer** review-time patches if the dev follows the constraints above carefully.

### Git intelligence (last 5 commits)

```
db476d3 land story 4.2                       # PyPI trusted publishing + release runbook + 14 review patches
1f74105 land epic 3 retrospective             # admin
1756bac land epic 2 retrospective             # admin
4d5bbce land story 4.1 code-review            # ci.yml polish review patches
ce2b3ec land story 4.1 implementation         # ci.yml polish (pip-audit, codecov, LOC gate, dependency-update.yml)
```

Pattern: each story lands in 1 or 2 commits (`land story X.Y` or split into `implementation` + `code-review`). Story 4.3a should follow the single-commit `land story 4.3a` pattern if dev + review converge in one cycle; otherwise split.

Conventions established in the recent commits:
- Story 4.1 established the **5-pinned-actions** baseline in `ci.yml`: `actions/checkout@v4`, `extractions/setup-just@v2`, `astral-sh/setup-uv@v3`, `codecov/codecov-action@v5.5.1`, `pypa/gh-action-pip-audit@v1.1.0`. Story 4.3a adds **zero** new actions to `ci.yml`.
- Story 4.2 established the SHA-pin-on-write-scope convention. Story 4.3a's read-scope context doesn't need it.
- Story 4.2 established the `check-jsonschema`-style "validate the new file against a schema" pattern (via `yaml.safe_load` initially). Story 4.3a evolves it to full schema validation.

### Testing strategy

Story 4.3a adds **no Python code**, **no Python tests**, and **no semvertag CLI tests**. The validation surface is:

1. **`check-jsonschema` schema validation** — AC5 CI step. Asserts `action.yml` is structurally valid GitHub Actions metadata.
2. **`yaml.safe_load` parse gate** — AC12 local check. Asserts `action.yml` parses as YAML (a structural prerequisite to AC5).
3. **`mkdocs build --strict`** — AC12 + AC14. Asserts `docs/providers/github.md` renders, nav references resolve, no orphan files exist.
4. **Manual snippet smoke (Task 6)** — copy the Quick Start snippet into a scratch workflow file, parse it with `yaml.safe_load`. Asserts the published consumer snippet itself is parseable.
5. **Regression sweep** — `just test` (425 pass), `just lint-ci` clean, `uv build` clean. Asserts no incidental drift.

**What is explicitly NOT tested in this story:**
- The action's runtime behavior on a consumer repo. That requires running `uvx semvertag` against a real GitHub Actions runner, which would necessitate a separate "integration" workflow (e.g., a self-test workflow in `.github/workflows/action-smoke.yml`). Out of scope for v1.0 per the epic AC's "integration tests cannot run the Marketplace in CI directly" guidance (`epics.md:768`).
- Marketplace publication itself. This is GitHub-platform behavior triggered by `release: published` + `action.yml` at root. Verified post-release by the maintainer per AC9 + AC13.
- The seven-line consumer snippet's end-to-end execution. Manual snippet smoke (Task 6) validates parse-correctness; runtime correctness is implicit in the action's composite-step shape.

A future story could add a self-test workflow that runs the action against the repo itself on every PR. Not 4.3a scope; capture as a possible follow-up in deferred-work post-review.

### Open questions (carry to code-review)

- **OQ1:** Is the Marketplace slug `semvertag` actually available, or has someone else claimed it? Pre-publish check by the maintainer; resolution surfaces as either (a) listing claims `semvertag` cleanly, (b) maintainer chooses a different `name:` field. 4.3a assumes (a); flag if reviewer wants a fallback name baked in.
- **OQ2:** Should `inputs.token`'s default be `${{ github.token }}` or `${{ env.GITHUB_TOKEN }}`? Both work for the common path. `github.token` is the cleaner expression-context default; `env.GITHUB_TOKEN` only resolves if the caller's job has `env: GITHUB_TOKEN:` set (which it typically doesn't). 4.3a uses `github.token`; flag if reviewer prefers the env-var path.
- **OQ3:** Should the schema-validation step use `--schemafile <URL>` (current network fetch) or `--builtin-schema vendor.github-actions` (offline-bundled)? URL form tracks upstream; bundled form is offline-deterministic. 4.3a uses URL; flag if reviewer wants offline determinism.
- **OQ4:** Should `docs/providers/github.md` link to `docs/strategies/branch-prefix.md` and `docs/strategies/conventional-commits.md` (which don't exist until Story 4.4)? 4.3a writes dead links; flag if reviewer wants the links removed or replaced with inline explainers until 4.4 lands.
- **OQ5:** Should the action embed `GITHUB_REPOSITORY` and `GITHUB_REF_NAME` as explicit env vars on the `Run semvertag` step? GitHub Actions auto-exports them as env vars in every step's environment, so explicit re-mapping is redundant — but explicit-is-better-than-implicit might be worth a one-line `env:` addition. 4.3a relies on auto-export; flag if reviewer wants explicit.
- **OQ6:** Marketplace publishing requires a one-time "Publish this Action to the GitHub Marketplace" checkbox at first release. This is a runbook addition for `docs/contributing/release.md`. 4.3a flags it but does NOT touch the runbook (Story 4.2 file-stability). Resolution: separate follow-up story to amend the runbook, OR a one-line addition to 4.3a's deferred-work entry. Reviewer's call.
- **OQ7:** Should `action.yml` carry a top-level `# YAML comment` block linking back to `docs/providers/github.md` and to `architecture.md`? Story 4.2's `publish.yml` is heavily commented; the action.yml convention in the GitHub ecosystem is sparser. 4.3a writes minimal YAML comments (one per non-obvious block); flag if reviewer wants more.

### Project structure notes

- `action.yml` at repo root matches the architecture's tree (`architecture.md:1071`).
- `docs/providers/` is new; `docs/strategies/` and `docs/migrating-from-*.md` are also implied by the architecture but ship in later stories.
- `mkdocs.yml`'s `Providers:` section header is the first multi-leaf nav section in this repo. Story 4.3b will add a sibling leaf; Story 4.4 may add a `Providers → Overview: providers/index.md` landing page (4.3a does NOT pre-create the overview — that's 4.4 scope).
- `ci.yml`'s `lint` job gains one step; step ordering (checkout → setup-just → setup-uv → uv-python-install → just-install-lint-ci → **schema-validate** → uv-build → mkdocs-build → loc-gate) is the canonical order. The schema-validate step is inserted between `just install lint-ci` (which sets up the toolchain) and `uv build` (which depends on a clean lint state).

### References

- [Source: epics.md §Story 4.3a (line 749-770)] — full 3-G/W/T AC narrative.
- [Source: epics.md §FR41 (line 79, 231, 554)] — Marketplace adoption requirement.
- [Source: epics.md §FR45 (line 85, 561)] — Marketplace discoverability requirement.
- [Source: prd.md §Journey 3 (line 211-220)] — Dani the Terraform maintainer narrative; 7-line snippet origin.
- [Source: prd.md §FR-cluster-CI-distribution (line 122, 124-125, 222, 265)] — Marketplace wrapper as v1.0 distribution channel.
- [Source: prd.md §Per-repo strategy selection (line 199)] — `SEMVERTAG_STRATEGY` env-var canonical path.
- [Source: prd.md §NFR19 (line 597)] — provider-native context auto-detection (`GITHUB_TOKEN` for GitHub Actions).
- [Source: architecture.md §Project Tree (line 1055-1080)] — `action.yml` placement at repo root.
- [Source: architecture.md §Deployment (line 1347-1351)] — "GitHub Actions Marketplace: published from `action.yml` automatically by tagging a release."
- [Source: architecture.md §Trust-surface scaffolding step 9 (line 594)] — implementation-sequence anchor.
- [Source: architecture.md §FR40-FR42 CI Distribution mapping (line 1207, 1397)] — `action.yml` + Catalog component pair.
- [Source: pyproject.toml §[project.scripts] (line 28-29)] — `semvertag = "semvertag.__main__:main"` enables `uvx semvertag`.
- [Source: .github/workflows/ci.yml (line 16-114)] — existing `lint` / `pytest` / `pip-audit` job shapes; the schema-validate step inserts in the `lint` job.
- [Source: .github/workflows/publish.yml] — Story 4.2 byte-stable; not touched in 4.3a.
- [Source: docs/contributing/release.md] — Story 4.2 territory; not touched in 4.3a.
- [Source: docs/index.md] — placeholder `# semvertag — coming soon`; Story 4.4 owns.
- [Source: _bmad/4-2-publish-workflow-via-trusted-publishing.md §Critical architectural constraints + Anti-patterns] — discipline carry-forward.
- [Source: _bmad/4-1-ci-workflow-polish.md §AC12 + Constraint 13] — local-validation-only precedent; `actionlint` deferral.
- [Source: _bmad/sprint-status.yaml (line 71)] — `4-3a-github-actions-marketplace-wrapper: backlog` → `ready-for-dev` transition target.
- [Source: _bmad/sprint-status.yaml (line 69)] — `epic-4: in-progress` (set by Story 4.1's create-story; no transition required).
- [Source: docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax (via Context7 `/websites/github_en_actions`)] — canonical `action.yml` schema, composite-action shape, `branding` enums.
- [Source: docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action (via Context7)] — canonical composite-action example with `shell: bash` on every step + `env:` mapping.
- [Source: pypi.org/project/check-jsonschema] — schema-validation tool.
- [Source: json.schemastore.org/github-action.json] — GitHub Actions metadata JSON Schema.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow, 2026-05-30.

### Debug Log References

- `action.yml` YAML parse: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('action.yml'))"` → `YAML OK`.
- `action.yml` schema validation: `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml` → `ok -- validation done` (14 packages installed in 26ms ephemerally; no persistent install).
- `ci.yml` YAML parse post-patch: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` → `YAML OK`. Step inserted between `just install lint-ci` (line 28) and `uv build` (now line 38).
- `mkdocs build --strict` first pass: FAILED on two dead links in `docs/providers/github.md` to `../strategies/branch-prefix.md` and `../strategies/conventional-commits.md`. Resolved by dropping the markdown link syntax and keeping the descriptive prose — Story 4.4 owns those pages; cross-reference will land then. Captured as a Change Log entry below + flagged for code-review.
- `mkdocs build --strict` second pass: clean, built in 0.22s (one new page registered; nav resolves; no orphans).
- `just lint-ci` → eof-fixer + ruff format (47 files already formatted) + ruff check (`All checks passed!`) + ty check (`All checks passed!`).
- `just test` → **425 passed in 1.18s** (matches Story 4.2's 425/1.51s baseline; no semvertag/ or tests/ change).
- `just test-branch-strategies` → 26/26, 100% branch on `strategies/branch_prefix.py`.
- `just test-cc-strategies` → 44/44, 100% branch on `strategies/conventional_commits.py`.
- `just test-doctor` → 56/56, 100% branch on `doctor/`.
- `uv run ty check` → clean.
- `uv build` → `dist/semvertag-0.tar.gz` + `dist/semvertag-0-py3-none-any.whl` built. The pre-existing `uv_build` unbounded-version warning is `_bmad/deferred-work.md §1-1` template-inherited; out of scope per Constraint 1.
- Drift check: `git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md LICENSE docs/index.md docs/contributing/ .github/workflows/publish.yml .github/workflows/dependency-update.yml .gitlab/` → empty (AC11 + AC13 byte-stable preserved).
- Working-tree audit: `git status --short` shows exactly the expected six entries (NEW `action.yml`, NEW `docs/providers/`, MODIFIED `mkdocs.yml`, MODIFIED `.github/workflows/ci.yml`, MODIFIED `_bmad/sprint-status.yaml`, MODIFIED `_bmad/4-3a-…`). Nothing else.
- Snippet smoke: extracted the Quick Start YAML block via `re.search` + `yaml.safe_load` — parses cleanly, contains `<org>`, `uses: actions/checkout@v4`, `contents: write`. Block is 15 lines (the full minimal workflow); the "7-line" framing in Journey 3 refers to the action-invocation surface inside `steps:` (~7 lines from the checkout `- uses:` through the action `- uses:`).

### Completion Notes List

- **AC1 (`action.yml` at repo root with required Marketplace metadata)** — verified: new `action.yml:1-44`. Top-level keys in spec order: `name`, `description`, `author`, `branding`, `inputs`, `runs`. No `outputs:`, no top-level `using:`, no `runs.main:`/`runs.image:`/`runs.entrypoint:`. Description ≤125 chars.
- **AC2 (inputs: exactly two, both optional)** — verified: `inputs.strategy` (default `'branch-prefix'`, required false) and `inputs.token` (default `${{ github.token }}`, required false). Both carry non-empty descriptions; no other inputs.
- **AC3 (`runs.using: 'composite'` with three steps)** — verified: `runs.using: 'composite'` + `runs.steps[]` containing setup-uv@v3 (`enable-cache: true`, `cache-dependency-glob: ''`) + Run-semvertag step (`shell: bash`, env `GITHUB_TOKEN` + `SEMVERTAG_STRATEGY`, `run: uvx semvertag`). No `actions/checkout` embedded. No uv-version pin per Constraint 8. Explicit `shell:` on the only `run:` step per Constraint 5.
- **AC4 (Marketplace branding)** — verified: `branding.icon: 'tag'`, `branding.color: 'blue'`. Comment block in `action.yml` documents the icon-choice rationale.
- **AC5 (schema validation in `ci.yml`)** — verified: new step in the `lint` job between `just install lint-ci` and `uv build`. Uses `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml`. No new third-party action, no Go binary. Preserves Story 4.1 / 4.2 actionlint-deferral.
- **AC6 (`docs/providers/github.md` with six sections + Quick Start snippet verbatim)** — verified: 6 H2 headers (`Quick Start (7 lines)` / `Inputs` / `Required permissions` / `Token scope: pushing tags from PRs vs main` / `Branch-prefix vs conventional-commits` / `Troubleshooting`). Quick Start snippet byte-equal to spec literal. Required permissions section names `contents: write` and the Journey 3 error wording. Troubleshooting section has four entries (the three spec failure modes plus a fourth for `<org>` placeholder resolution).
- **AC7 (`mkdocs.yml` nav)** — verified: `nav:` gains `Providers:` block between `Quick Start` and `Contributing`, with `GitHub Actions: providers/github.md` leaf. `theme:`, `palette:`, `markdown_extensions:`, `extra:` byte-stable per `git diff mkdocs.yml`. `mkdocs build --strict` exits 0.
- **AC8 (`action.yml` byte-stable against schema regeneration)** — verified: schema validator + yaml.safe_load both clean. No JavaScript-action or Docker-action key leakage. YAML quoting style consistent (single quotes for ASCII literals; double quotes only inside the `${{ }}` interpolations where the GitHub Actions expression engine already governs).
- **AC9 (Marketplace publishing piggybacks on `publish.yml`'s `release: published`)** — verified by inspection: `publish.yml` byte-stable; Marketplace polls release events independent of any workflow step. No changes made to `publish.yml`. The runbook update for the one-time `Publish this Action to the GitHub Marketplace` checkbox is captured as a post-review follow-up per Constraint 13.
- **AC10 (`action.yml` ↔ `docs/providers/github.md` drift-free)** — verified: docs Inputs table reproduces `action.yml`'s `strategy` + `token` (descriptions, defaults) verbatim. Docs link out to `action.yml` at `<org>/semvertag/blob/main/action.yml`.
- **AC11 (no changes to do-not-touch paths)** — verified: `git diff HEAD --` against the eleven do-not-touch paths returns empty.
- **AC12 (local gates green)** — verified: all eight gate commands exit 0 (see Debug Log).
- **AC13 (existing CI behaviors preserved byte-identical)** — verified: `ci.yml` delta is exactly `+9 -0` (the new step block). `pytest` matrix and `pip-audit` jobs untouched. The LOC gate exit logic unchanged.
- **AC14 (green CI run on PR)** — locally verified the new schema-validation step works; on-PR CI verification is the land-time pass. Local gates pass per AC12.

**Deviations from the spec literal:**

- **Task 2.7 — dead links to Story 4.4 pages.** The spec told the dev to add `[branch-prefix strategy](../strategies/branch-prefix.md)` and `[conventional-commits strategy](../strategies/conventional-commits.md)` links, knowing they'd be dead until Story 4.4 lands. AC12's `mkdocs build --strict` rejects dead links in strict mode; the gate wins. Implementation drops the link syntax and keeps the descriptive prose. The strategy explainer cross-links can be added back as a follow-up patch when Story 4.4 lands. Flagged as OQ4 resolution; surfaces in code-review.
- **Task 6 — in-memory snippet smoke (no scratch file).** The spec described a scratch `.github/workflows/test-snippet.yml` flow; implementation substituted an in-memory `re.search` + `yaml.safe_load` script in the same shell session. Same gate (proves the Quick Start block parses as YAML) with no risk of forgetting to delete the scratch file before commit.

**Open questions (carry to code-review):**

- **OQ1** (Marketplace slug `semvertag` availability) — pre-publish check by the maintainer at first-release time. Implementation assumes the slug is unclaimed.
- **OQ2** (`${{ github.token }}` vs `${{ env.GITHUB_TOKEN }}`) — implementation uses `github.token` (cleaner expression-context default).
- **OQ3** (`--schemafile <URL>` vs `--builtin-schema vendor.github-actions`) — implementation uses the URL form to track upstream schema updates.
- **OQ4** (dead links to Story 4.4 pages) — **resolved by dropping link syntax** (see Deviations above). Code-review can flag if a different resolution is preferred.
- **OQ5** (explicit `GITHUB_REPOSITORY` / `GITHUB_REF_NAME` env-var passthrough) — implementation relies on GitHub Actions' auto-export. Flag if reviewer wants explicit.
- **OQ6** (runbook addition for the one-time "Publish this Action to the GitHub Marketplace" checkbox) — flagged for a separate follow-up story; Story 4.2 file-stability is preserved.
- **OQ7** (YAML comment density in `action.yml`) — implementation writes minimal WHY comments (icon-choice rationale, `${{ github.token }}` constraint, `shell:` mandate, `SEMVERTAG_STRATEGY` env-var bridge). Flag if reviewer wants more or fewer.

### File List

| File | Action | Notes |
|---|---|---|
| `action.yml` | **NEW** | 44 LOC YAML. Composite action wrapper for `uvx semvertag`. `name: 'semvertag'`, `branding: { icon: tag, color: blue }`, inputs `strategy` (default `branch-prefix`) + `token` (default `${{ github.token }}`), `runs.using: composite` with `astral-sh/setup-uv@v3` + `uvx semvertag` (env `GITHUB_TOKEN` + `SEMVERTAG_STRATEGY`). `<org>` placeholder in `author:`. |
| `docs/providers/github.md` | **NEW** | 117 LOC markdown. Six sections per AC6: Quick Start (15-line minimal workflow incl. `<org>` placeholder, byte-equal to spec literal), Inputs (table reproducing `action.yml`), Required permissions (`contents: write` + Journey 3 error wording), Token scope (PR vs main + protected-branch footgun), Branch-prefix vs conventional-commits routing guide, Troubleshooting (4 failure modes). |
| `docs/providers/` | **NEW** (implied) | Empty-then-populated directory; mkdocs traverses `docs_dir`. |
| `mkdocs.yml` | **UPDATE** | +2 LOC: `Providers:` section header + `GitHub Actions: providers/github.md` leaf, inserted between `Quick Start` and `Contributing`. Theme / palette / markdown_extensions / extra byte-identical (verified via `git diff mkdocs.yml`). |
| `.github/workflows/ci.yml` | **UPDATE** | +9 LOC: one new step in the `lint` job between `just install lint-ci` and `uv build`, running `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml`. `pytest` matrix + `pip-audit` job untouched. `name:`, `on:`, `concurrency:`, `permissions:`, and existing step ordering preserved. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `4-3a-github-actions-marketplace-wrapper: ready-for-dev → in-progress → review`; `last_updated: 2026-05-30`; `last_updated_note` refreshed with dev-cycle summary. |
| `_bmad/4-3a-github-actions-marketplace-wrapper.md` (this file) | **UPDATE** | Status `ready-for-dev → in-progress → review`; Tasks 1-8 checked; Task 9 intentionally left unchecked (post-review gate per spec). Dev Agent Record (Agent Model, Debug Log, Completion Notes, File List, Change Log) filled. |
| `_bmad/deferred-work.md` | **NO-CHANGE** | Task 9 is post-review; deferred to code-review-time per spec. |
| `semvertag/**/*.py` | **NO-CHANGE** | Verified empty diff (AC11). |
| `tests/**/*.py` | **NO-CHANGE** | Verified empty diff (AC11). |
| `pyproject.toml` | **NO-CHANGE** | Verified empty diff (AC11). |
| `Justfile` | **NO-CHANGE** | Verified empty diff (AC11). |
| `README.md` | **NO-CHANGE** | Verified empty diff (AC11). |
| `LICENSE` | **NO-CHANGE** | Verified empty diff (AC11). |
| `docs/index.md` | **NO-CHANGE** | Story 4.4 owns. Verified empty diff. |
| `docs/contributing/` | **NO-CHANGE** | Story 4.2 territory. Verified empty diff. |
| `.github/workflows/publish.yml` | **NO-CHANGE** | Story 4.2 byte-stable. Verified empty diff. |
| `.github/workflows/dependency-update.yml` | **NO-CHANGE** | Story 4.1 byte-stable. Verified empty diff. |
| `.gitlab/` | **NO-CHANGE** | Story 4.3b sibling territory. Verified empty diff. |

### Change Log

- 2026-05-30 — Created `action.yml` at repo root: composite action wrapping `uvx semvertag`. `name: 'semvertag'`, `description:` ≤125 chars, `author: '<org>'` placeholder, `branding: { icon: tag, color: blue }`, inputs `strategy` (default `'branch-prefix'`) + `token` (default `${{ github.token }}`), `runs.using: 'composite'` with `astral-sh/setup-uv@v3` (no version pin per Constraint 8) + `Run semvertag` step (`shell: bash`, env `GITHUB_TOKEN` + `SEMVERTAG_STRATEGY`, `run: uvx semvertag`). [AC1, AC2, AC3, AC4, AC8]
- 2026-05-30 — Created `docs/providers/github.md` (117 lines): six sections — Quick Start (15-line minimal workflow byte-equal to AC6 literal), Inputs (table mirroring `action.yml`), Required permissions (`contents: write` + Journey 3 error wording), Token scope (PR vs main + protected-branch footgun), Branch-prefix vs conventional-commits routing guide, Troubleshooting (4 failure modes incl. `<org>` placeholder resolution failure). `<org>` placeholder preserved throughout per Constraint 11. [AC6, AC10]
- 2026-05-30 — **Deviation from spec literal at Task 2.7.** AC12 mandates `mkdocs build --strict` exits 0; the spec told the dev to add `[…](../strategies/…)` links to Story 4.4 pages that do not exist yet, which `--strict` rejects as broken links. Implementation drops the markdown link syntax and keeps the descriptive prose. Cross-link can be added in a follow-up patch when Story 4.4 lands. Flagged via OQ4 resolution.
- 2026-05-30 — Updated `mkdocs.yml` nav: 2-line `Providers → GitHub Actions: providers/github.md` block inserted between `Quick Start` and `Contributing`. Theme / palette / markdown_extensions / extra preserved byte-identical. [AC7]
- 2026-05-30 — Updated `.github/workflows/ci.yml` `lint` job: 1 new step (`Validate action.yml against GitHub Actions schema`) inserted between `just install lint-ci` and `uv build`. Runs `uvx --from check-jsonschema check-jsonschema --schemafile https://json.schemastore.org/github-action.json action.yml`. No new third-party action, no Go binary; preserves Story 4.1 / 4.2 actionlint-deferral. [AC5, AC13]
- 2026-05-30 — **Substituted in-memory snippet smoke for the spec's scratch-file approach.** Task 6.1 called for a scratch `.github/workflows/test-snippet.yml`; implementation used `re.search` + `yaml.safe_load` against the docs file in a single shell invocation. Same gate (Quick Start block parses as YAML; contains `<org>` + `uses: actions/checkout@v4` + `contents: write`) with no scratch-file lifecycle risk.
- 2026-05-30 — Verified zero changes to do-not-touch paths via `git diff HEAD --` against `semvertag/`, `tests/`, `pyproject.toml`, `Justfile`, `README.md`, `LICENSE`, `docs/index.md`, `docs/contributing/`, `.github/workflows/publish.yml`, `.github/workflows/dependency-update.yml`, `.gitlab/`. All eleven returned empty. [AC11]
- 2026-05-30 — Local validation gates: `action.yml` schema-validate clean; `action.yml` + `ci.yml` `yaml.safe_load` clean; `just lint-ci` clean (eof-fixer + ruff format + ruff check + ty check); `just test` → 425 pass in 1.18s; branch-strategies/cc-strategies/doctor 100% branch (26/44/56); `uv run ty check` clean; `uv build` clean (sdist + wheel); `mkdocs build --strict` clean (0.22s). [AC12, AC14 readiness]
- 2026-05-30 — Sprint status: `4-3a-github-actions-marketplace-wrapper` ready-for-dev → in-progress → review.
- 2026-05-30 — **Maintainer follow-ups (post-merge, captured for code-review)**: (a) Marketplace slug `semvertag` availability check (OQ1); (b) follow-up patch to add the strategy explainer cross-links when Story 4.4 lands (OQ4 carry-forward); (c) runbook amendment to `docs/contributing/release.md` documenting the one-time "Publish this Action to the GitHub Marketplace" checkbox on the GitHub release UI (Constraint 13, OQ6) — separate story to preserve Story 4.2 file-stability.
