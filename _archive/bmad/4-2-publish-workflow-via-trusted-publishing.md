# Story 4.2: Publish workflow via PyPI trusted publishing

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer releasing v1.0,
I want a `release: published` workflow that builds the wheel + sdist and publishes to PyPI via **trusted publishing (OIDC)**, with **no long-lived `PYPI_TOKEN` in CI secrets**, plus a release runbook at `docs/contributing/release.md` so a release is reproducible in ≤5 minutes,
So that NFR13 holds (no long-lived API tokens; signatures verifiable against the published `uv.lock`) and releases happen by tagging in GitHub, not by hand-running `uv publish --token …`.

## Acceptance Criteria

### AC1 — `.github/workflows/publish.yml` exists with `release: published` trigger

**Given** the directory `.github/workflows/` currently contains `ci.yml` (Stories 1.1 + 4.1) and `dependency-update.yml` (Story 4.1)
**When** Story 4.2 lands
**Then** a NEW file `.github/workflows/publish.yml` exists with:

- `name: publish`
- Triggers: `on: release: types: [published]` **only** — NO `push:`, NO `pull_request:`, NO `schedule:`.
- An optional `workflow_dispatch: {}` trigger for emergency manual re-runs **with one input**: `tag` (a string the maintainer supplies; the version-tag guard step uses this in lieu of `github.event.release.tag_name` when `event_name == 'workflow_dispatch'`).

**And** the workflow is **not** triggered by `release: created` / `release: prereleased` / `release: edited` — only `published` (the human-clicks-"Publish release" event), per the architecture's "release: published" wording (`architecture.md:250, 1060`).

### AC2 — Top-level workflow shape: permissions, environment, concurrency, timeout

**Given** the workflow needs OIDC token issuance for PyPI trusted publishing
**When** the file is written
**Then** it declares the following top-level blocks (in this order, mirroring the canonical uv-recommended publish workflow):

- `permissions:` block scoped to **least privilege** for trusted publishing:
  ```yaml
  permissions:
    id-token: write   # PyPI OIDC token issuance — REQUIRED for trusted publishing
    contents: read    # actions/checkout
  ```
- `environment: name: pypi` at the job level (NOT workflow level — the environment guard must be in the job that does the publish, so the OIDC token is scoped to it).
- `concurrency:` block:
  ```yaml
  concurrency:
    group: publish-${{ github.event.release.tag_name || inputs.tag }}
    cancel-in-progress: false
  ```
  Per-tag group prevents a workflow_dispatch + release double-fire from racing; `cancel-in-progress: false` ensures an in-flight publish is not cut off mid-upload.
- `timeout-minutes: 15` on the publish job (mirrors Story 4.1's per-job timeout discipline; gives `uv build` + smoke + `uv publish` headroom while bounding runaway-job blast radius).

**And** there is **no top-level `env:` block** referencing `PYPI_TOKEN`, `PYPI_API_TOKEN`, `TWINE_*`, or any publishing credential. Trusted publishing uses the GitHub OIDC token; no env-var credentials are needed.

### AC3 — Action pins: architectural set + SHA-pinning for write-scope job

**Given** the architecture mandates `astral-sh/setup-uv@v3`, `extractions/setup-just@v2`, `actions/checkout@v4` (`architecture.md:249`) **and** Story 4.1 established the precedent that **write-scope workflows are SHA-pinned** (Story 4.1 `dependency-update.yml:23-27` comment + AC justification)
**When** the publish workflow is written
**Then** **every** `uses:` step is SHA-pinned to the exact commit corresponding to the architecturally-named major tag, with the major-tag annotated in a trailing `# vN` comment for review legibility:

```yaml
- uses: actions/checkout@<SHA>            # v4
- uses: extractions/setup-just@<SHA>      # v2
- uses: astral-sh/setup-uv@<SHA>          # v3
```

**And** the SHAs MUST match the same commits used in `dependency-update.yml:47-49` (the dev re-uses the exact SHAs already vetted by Story 4.1 — no new SHA lookup needed for those three actions). The current vetted SHAs are:

| Action | SHA | Tag |
|---|---|---|
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | `v4` |
| `extractions/setup-just` | `dd310ad5a97d8e7b41793f8ef055398d51ad4de6` | `v2` |
| `astral-sh/setup-uv` | `caf0cab7a618c569241d31dcd442f54681755d39` | `v3` |

**And** NO third-party publish action (e.g., `pypa/gh-action-pypi-publish`) is used — `uv publish` runs as a direct `run:` invocation per `architecture.md:1347` ("PyPI via `uv publish` with PyPI trusted publishing"). Introducing a third action would add supply-chain surface for no functional gain (`uv publish` natively detects GitHub Actions OIDC environment and exchanges the token).

### AC4 — Pre-publish guard: tag must match `[project.version]`

**Given** the epic AC's "publish step fails with a clear error before `uv publish` is invoked" requirement (`epics.md:740-742`)
**When** the workflow runs
**Then** a guard step **before** `uv build` and `uv publish` (and after `actions/checkout@v4` so the file is present) does the following:

1. Resolves the **effective tag**:
   - `release: published` event → `github.event.release.tag_name`
   - `workflow_dispatch` event → `inputs.tag`
   - Strip a single leading `v` if present (`v1.0.0` → `1.0.0`), then re-assert the result matches `^[0-9]+\.[0-9]+\.[0-9]+(?:-.+)?$` (SemVer 2.0 form including optional pre-release/build suffix).
2. Reads `[project.version]` from `pyproject.toml` using a stdlib-only parser:
   ```sh
   PROJECT_VERSION=$(uv run --no-sync --no-project python -c \
     "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")
   ```
   (`uv run --no-sync --no-project` avoids creating/syncing a venv just to read TOML; `tomllib` is stdlib on Python 3.11+ — the `astral-sh/setup-uv@v3` step pinned to `uv python install 3.13` upstream guarantees ≥3.11.)
3. Asserts the two values are byte-equal. On mismatch, prints a clearly-formatted error and exits non-zero **before** `uv build` runs:
   ```sh
   if [ "$EFFECTIVE_TAG" != "$PROJECT_VERSION" ]; then
     echo "::error::Release tag (${EFFECTIVE_TAG}) does not match pyproject.toml [project.version] (${PROJECT_VERSION}). Refusing to publish. Bump [project.version] in pyproject.toml and tag matching, or amend the release tag."
     exit 1
   fi
   echo "::notice::tag ${EFFECTIVE_TAG} matches [project.version] ${PROJECT_VERSION} — proceeding to build + publish."
   ```

**And** the guard step is named `Verify release tag matches [project.version]` (or equivalent — exact step name not load-bearing) and is `id: tag_guard` so future stories can reference its outputs.

**And** if `pyproject.toml` ever ships with a placeholder version (e.g., `version = "0"` as it does today — see Open Question OQ4 below), the guard correctly **refuses** any non-`0` tag, forcing the maintainer to bump `[project.version]` in their release-prep PR.

### AC5 — Build step: `uv build` produces `dist/*.whl` + `dist/*.tar.gz`

**Given** the architecture's build pattern (`architecture.md:1340-1343` — "uv build produces dist/*.whl + dist/*.tar.gz via uv_build backend; driven by just publish which runs in publish.yml on release: published")
**When** the workflow's build step runs
**Then** it executes `uv build` (NOT `python -m build`, NOT `twine sdist + bdist_wheel`, NOT a custom shell pipeline). The step is a single `run:` line:

```yaml
- name: Build distribution
  run: uv build
```

**And** the step assumes `dist/` does not pre-exist (fresh runner — `actions/checkout` does not create it). If a future change introduces a `dist/` pre-existence concern, prepend `rm -rf dist` (mirrors modern-di's `Justfile:25-29` `publish` recipe pattern). Do NOT pre-emptively add the `rm -rf` for v1.0 — the runner is fresh.

**And** no `just publish` recipe is invoked (modern-di's `just publish` uses `--token` which is exactly what NFR13 forbids; semvertag's `Justfile` has no `publish` recipe and **MUST NOT** gain one in this story — see Constraint 6 below).

### AC6 — Publish step: `uv publish` via trusted publishing, no token

**Given** the architecture and PRD both mandate trusted publishing (`architecture.md:1347`, `prd.md:587-588`)
**When** the workflow's publish step runs
**Then** it executes `uv publish` (with no `--token` flag, no env credential, no third-party action wrapper):

```yaml
- name: Publish to PyPI via trusted publishing
  run: uv publish
```

**And** the step relies on uv's built-in trusted-publishing detection: with `id-token: write` permission and a `pypi` GitHub Environment whose name matches the PyPI trusted-publisher configuration, `uv publish` automatically performs the OIDC token exchange — no `--trusted-publishing always` flag is required at the CLI (uv's default is "check for trusted publishing when running in a supported environment; ignore if not configured" — per uv docs reference).

**And** `[tool.uv]` in `pyproject.toml` is **not** modified to add `trusted-publishing = "always"`. That key is a defense-in-depth that *forces* trusted publishing (and *errors* if not detected); we accept the default-detect behavior because (a) `pyproject.toml` is do-not-touch in this story per AC11, (b) the GitHub Environment + PyPI-side trusted-publisher config IS the gate — uv's detection is purely opportunistic.

**And** PEP 740 attestations are uploaded by default (`uv publish`'s default behavior; `--no-attestations` is not passed). If PyPI rejects attestations in the future, the runbook documents the `--no-attestations` escape hatch.

### AC7 — Zero credential references: no `PYPI_TOKEN`, no `TWINE_*`, no secret

**Given** the epic AC's "the workflow does not reference any `PYPI_TOKEN` / `PYPI_API_TOKEN` secret" (`epics.md:734`)
**When** I grep the workflow file
**Then** the following strings appear **nowhere** in `.github/workflows/publish.yml`:

- `PYPI_TOKEN`
- `PYPI_API_TOKEN`
- `TWINE_USERNAME`
- `TWINE_PASSWORD`
- `secrets.PYPI_` (any secret reference starting `secrets.PYPI_`)
- `--token` (as a flag to `uv publish`)
- `--username` / `--password` (as flags to `uv publish`)

**And** `secrets.GITHUB_TOKEN` MAY appear (it's needed by `actions/checkout` implicitly and grants `contents: read` for the checkout). But it MUST NOT be referenced in any step that does the publish — the publish uses OIDC, not the workflow token.

### AC8 — Release runbook at `docs/contributing/release.md`

**Given** the epic AC's "release-runbook entry in `docs/contributing/release.md` (or equivalent)" (`epics.md:744`)
**When** Story 4.2 lands
**Then** a NEW file `docs/contributing/release.md` exists with the following sections (markdown headers verbatim; body content paraphrased here):

```markdown
# Release runbook

## One-time setup (already done; documented for posterity)

- PyPI side: project page → Publishing → Add a trusted publisher
  - Owner: `<org>`
  - Repository: `semvertag`
  - Workflow filename: `publish.yml`
  - Environment name: `pypi`
- GitHub side: Settings → Environments → New environment → name: `pypi`
  - Optional: require reviewer approval before deployment to the `pypi` environment (recommended for v1.0+; defers the actual publish until a maintainer clicks "Approve").

## Cutting a release (≤5 minutes, target NFR13 + 5-min-from-merge-to-PyPI)

1. Land all PRs for the release on `main`. Verify CI green.
2. Open a release-prep PR that:
   - Bumps `[project.version]` in `pyproject.toml`.
   - Updates `CHANGELOG.md` with the new version section (Story 4.6 scope; until then, append a single line).
3. Merge the release-prep PR.
4. On GitHub → Releases → Draft a new release:
   - Tag: `v<X.Y.Z>` (must match `[project.version]` byte-equal after stripping leading `v`).
   - Title: `v<X.Y.Z>`.
   - Body: copy from `CHANGELOG.md`'s new section (or auto-generate).
   - Click "Publish release".
5. The `publish.yml` workflow auto-fires:
   - Verifies tag matches `[project.version]` (refuses to publish on mismatch).
   - Runs `uv build` → produces wheel + sdist.
   - Runs `uv publish` → trusted publishing exchanges the OIDC token with PyPI; publishes wheel + sdist + attestations.
6. Verify on https://pypi.org/project/semvertag/ that the new version is listed.

## v1.0 (and any subsequent major) pre-release gate

**MUST NOT release v1.0 or any subsequent major without:**

- Story 4.8's shadow-mode parity validation (`raif-autosemver` parity in `pypelines`, ≥2 weeks, 100% byte-identical tag outcomes per NFR9) has been re-run for the current `main` HEAD.
- Sign-off recorded in the GitHub release notes (or linked from them).

This gate is non-negotiable per the epic AC (`epics.md:747`) and PRD NFR9 (`prd.md:581`).

## Troubleshooting

- **"Tag does not match [project.version]"** — the guard step caught a mismatch. Either edit the release tag (delete + recreate the GitHub release) or bump `[project.version]` and re-tag.
- **OIDC token exchange fails** — check that the GitHub Environment is named `pypi` and the PyPI-side trusted-publisher config matches `<org>/semvertag` + workflow filename `publish.yml` + environment `pypi`.
- **PyPI rejects attestations** — workaround: temporarily add `--no-attestations` to the `uv publish` invocation in `publish.yml` (NOT in this story; only as an emergency lever).
- **First-release `[project.version] = "0"`** — the project ships with placeholder `"0"`. The release-prep PR for `v0.1.0` (or `v1.0.0`) must bump it; the guard will refuse otherwise. See OQ4 of this story.
```

**And** the runbook is registered in `mkdocs.yml`'s `nav:` so `mkdocs build --strict` (Story 4.1 CI lint job step) does not error on an orphan page — see AC9.

### AC9 — `mkdocs.yml` nav gains the release page

**Given** AC8 adds `docs/contributing/release.md` and `ci.yml`'s lint job runs `mkdocs build --strict`
**When** `mkdocs build --strict` runs against the post-4.2 working tree
**Then** the build exits 0 (no warnings, no errors).

**And** the only change to `mkdocs.yml` is a minimal `nav:` addition:

```yaml
nav:
  - Quick Start: index.md
  - Contributing:
    - Release runbook: contributing/release.md
```

**And** **no** theme, palette, or markdown-extension blocks in `mkdocs.yml` are modified — the change is a strict nav addition. Story 4.4 ("mkdocs site content") owns the broader nav redesign; 4.2 only registers the one page so `--strict` stays green.

### AC10 — Runbook documents the manual one-time trusted-publisher setup on PyPI

**Given** the epic AC's "the PyPI project page has been configured with the `semvertag` repo as a trusted publisher (a manual one-time setup step documented in the release runbook, **not in this workflow**)" (`epics.md:736`)
**When** I read `docs/contributing/release.md`
**Then** the "One-time setup" section names all four trusted-publisher fields PyPI requires:

- Owner (`<org>`)
- Repository (`semvertag`)
- Workflow filename (`publish.yml`)
- Environment name (`pypi`)

**And** `<org>` is left as a literal placeholder (matching the Story 4.1 + Story 1.1 convention — Launch Decisions Pending; Story 4.7 owns the concrete-`<org>` substitution).

**And** the runbook explicitly notes that this setup is **performed once before the first release** and is NOT part of the workflow's automation. No GitHub Action exists or is added for trusted-publisher provisioning — the maintainer does it through PyPI's web UI (or its API, out of scope).

### AC11 — No changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, or any existing workflow file

**Given** the story scope is "publish workflow YAML + release runbook + minimal `mkdocs.yml` nav addition only"
**When** I diff the branch against `main`
**Then** **no** `.py` file under `semvertag/` or `tests/` is modified, added, or deleted.
**And** `pyproject.toml` is **not** modified — `[project.version]` stays at its current `"0"` placeholder (bumping it is a per-release operation per the runbook, not this story's job).
**And** `Justfile` is **not** modified — no `publish` recipe is added; no `build` recipe is added; no recipe is renamed.
**And** `.github/workflows/ci.yml` is **not** modified — Story 4.1's byte-identical-preservation discipline carries forward.
**And** `.github/workflows/dependency-update.yml` is **not** modified — Story 4.1's output is preserved verbatim.
**And** `README.md` is **not** modified — Story 4.7 owns README hero work.
**And** the only repo files modified or added are:

- `.github/workflows/publish.yml` (NEW)
- `docs/contributing/release.md` (NEW)
- `mkdocs.yml` (UPDATE — nav addition only per AC9)
- `_bmad/sprint-status.yaml` (UPDATE — story status; epic-4 already `in-progress`)
- `_bmad/4-2-publish-workflow-via-trusted-publishing.md` (UPDATE — this file: Status, task checkboxes, Dev Agent Record, File List, Change Log)
- `_bmad/deferred-work.md` (UPDATE — post-review only; append any newly-discovered items)

### AC12 — Local validation: workflow YAML parses and lint-ci stays clean

**Given** `actionlint` may be unavailable locally (Story 4.1 confirmed: not on PyPI, not in this dev env)
**When** Story 4.2 is validated locally before push
**Then** the dev runs one of (acceptable substitutes per Story 4.1 AC12 precedent):

- `uvx actionlint .github/workflows/publish.yml` (if available — Go binary; uvx will fail with "package not found" in this env, fall through to YAML-parse path)
- **Fallback (accepted):** `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"` — must print no error.

**And** `just lint-ci` exits 0 (no Python change, so this is a regression canary on the lint stack — confirms the workflow change didn't accidentally invalidate `Justfile`).

**And** `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` exits 0 (confirms the new `docs/contributing/release.md` + `mkdocs.yml` nav addition produces a clean strict build — this is exactly the step that runs in `ci.yml`'s `lint` job after AC9 lands).

### AC13 — All existing pre-Story-4.2 CI and workflow behaviors are preserved byte-identical

**Given** Stories 1.1 + 4.1 each contributed structure to `.github/workflows/`
**When** Story 4.2 lands
**Then** the following are byte-identical to pre-4.2:

- `.github/workflows/ci.yml`: every byte (the post-4.1 file is preserved verbatim — no `permissions:` tweak, no new step, no comment change).
- `.github/workflows/dependency-update.yml`: every byte (SHA pins, `MODE` allowlist, `add-paths`, `gh workflow run` re-trigger step — all preserved verbatim).
- `pyproject.toml`: every byte (no `[tool.uv]` `trusted-publishing` key added per AC6; no `[project.version]` bump per AC11).
- `Justfile`: every byte.
- `README.md`: every byte (no badge addition for "PyPI version" yet — that's Story 4.7 territory).
- `semvertag/**/*.py` and `tests/**/*.py`: empty diff.

**And** `git diff HEAD -- .github/workflows/ci.yml .github/workflows/dependency-update.yml pyproject.toml Justfile README.md semvertag/ tests/` returns empty on the final pre-PR check.

### AC14 — A green CI run on the PR demonstrates all jobs pass with the new file present

**Given** the PR is opened with all of AC1–AC13's changes applied
**When** the PR's CI runs
**Then** all jobs in `ci.yml` end in `success`:

- `lint` (including `mkdocs build --strict` against the new `docs/contributing/release.md` + updated `mkdocs.yml` nav, and the LOC gate step still printing `semvertag_loc=<N>` unchanged from 4.1).
- `pytest` matrix (3.10–3.14, all 5 cells).
- `pip-audit`.

**And** `publish.yml` does NOT trigger on the PR (it has no `pull_request:` trigger by design — only `release: published` and `workflow_dispatch:`).

**And** a manual `workflow_dispatch` smoke-test of `publish.yml` is **OPTIONAL** verification (proves the tag-guard step works end-to-end). If performed:
- Use `inputs.tag: "0"` (matches the current placeholder `[project.version] = "0"`) → guard passes → `uv build` runs → `uv publish` runs.
- **DO NOT** run a real publish against `pypi.org` from a PR branch — the dispatch's tag-guard would let through `tag=0` and an actual `uv publish` would fail at the registry side (PyPI rejects `0` as a version), but more importantly, the smoke would consume the one-time-only "first publish" slot on PyPI for the `semvertag` project name. Treat this AC14 smoke purely as a static-validation: the workflow file parses, the guard step executes, the build step runs. **Do NOT proceed to the publish step manually.** If a true end-to-end test is needed, point the trusted publisher at TestPyPI in a follow-up story.

## Tasks / Subtasks

- [x] **Task 1: Create `.github/workflows/publish.yml` skeleton — name, triggers, top-level permissions/env/concurrency/timeout (AC1, AC2, AC7)**.
  - [x] 1.1 Write the file header:
    ```yaml
    name: publish

    on:
      release:
        types:
          - published
      workflow_dispatch:
        inputs:
          tag:
            description: "Effective tag for the version-guard check (e.g. v1.0.0). Used in lieu of github.event.release.tag_name."
            required: true
            type: string

    permissions:
      id-token: write   # PyPI OIDC token issuance — REQUIRED for trusted publishing
      contents: read    # actions/checkout

    concurrency:
      group: publish-${{ github.event.release.tag_name || inputs.tag }}
      cancel-in-progress: false
    ```
  - [x] 1.2 Verify no `env:` block references `PYPI_*` / `TWINE_*` (AC7 grep canary).
  - [x] 1.3 Verify the `release: types: [published]` shape (singular under `types:`, not `published:` as a sibling).

- [x] **Task 2: Add the publish job — runs-on, environment, timeout-minutes (AC2)**.
  - [x] 2.1 Append:
    ```yaml
    jobs:
      publish:
        runs-on: ubuntu-latest
        timeout-minutes: 15
        environment:
          name: pypi
          url: https://pypi.org/project/semvertag/
        steps:
    ```
  - [x] 2.2 Verify `environment.name: pypi` is **on the job**, NOT the workflow.
  - [x] 2.3 The `environment.url` is purely informational (renders as a "View deployment" link on the GitHub release UI). It is not load-bearing for the OIDC exchange; including it is a UX courtesy.

- [x] **Task 3: Add SHA-pinned action setup steps (AC3, AC13)**.
  - [x] 3.1 Append the three SHA-pinned setup steps; SHAs MUST match `dependency-update.yml:47-49` exactly:
    ```yaml
        - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4
        - uses: extractions/setup-just@dd310ad5a97d8e7b41793f8ef055398d51ad4de6  # v2
        - uses: astral-sh/setup-uv@caf0cab7a618c569241d31dcd442f54681755d39  # v3
          with:
            enable-cache: true
            cache-dependency-glob: "**/uv.lock"
        - run: uv python install 3.13
    ```
  - [x] 3.2 Add a SHA-pin justification comment at the top of `jobs:` (mirrors `dependency-update.yml:23-27`):
    ```yaml
    # Actions in this workflow are SHA-pinned (not tag-pinned) because this job
    # carries id-token: write — the OIDC token exchanged with PyPI confers PyPI
    # write scope on this repo. Tag retargeting would yield code execution with
    # publishing privileges; blast radius is asymmetric vs. ci.yml's read-only
    # context. ci.yml stays on tag pins per architecture policy.
    ```
  - [x] 3.3 `uv python install 3.13` matches the uv-canonical publish-workflow example (Context7 / uv docs); 3.13 is chosen because it is the highest fully-stable Python the matrix supports (pyproject.toml line 14). 3.10 (the floor) would also work; 3.13 is preferred for build-time consistency with the latest test cell.
  - [x] 3.4 Verify the SHAs are present in `dependency-update.yml` so reviewers can grep:
    ```sh
    grep -F 34e114876b0b11c390a56381ad16ebd13914f8d5 .github/workflows/*.yml | wc -l   # must be ≥2
    grep -F dd310ad5a97d8e7b41793f8ef055398d51ad4de6 .github/workflows/*.yml | wc -l   # must be ≥2
    grep -F caf0cab7a618c569241d31dcd442f54681755d39 .github/workflows/*.yml | wc -l   # must be ≥2
    ```

- [x] **Task 4: Add the pre-publish version-tag guard step (AC4)**.
  - [x] 4.1 Append after the setup steps:
    ```yaml
        - id: tag_guard
          name: Verify release tag matches [project.version]
          run: |
            # Resolve effective tag from the triggering event.
            if [ "${{ github.event_name }}" = "release" ]; then
              EFFECTIVE_TAG="${{ github.event.release.tag_name }}"
            elif [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
              EFFECTIVE_TAG="${{ inputs.tag }}"
            else
              echo "::error::Unexpected event_name ${{ github.event_name }} — publish.yml expects 'release' or 'workflow_dispatch'."
              exit 1
            fi

            # Strip a single leading 'v' (the SemVer-style 'v1.0.0' tag prefix).
            EFFECTIVE_TAG="${EFFECTIVE_TAG#v}"

            # Re-assert SemVer 2.0 form post-strip.
            if ! echo "$EFFECTIVE_TAG" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$'; then
              echo "::error::Effective tag '${EFFECTIVE_TAG}' is not SemVer 2.0 (expected MAJOR.MINOR.PATCH with optional -prerelease and +build)."
              exit 1
            fi

            # Read [project.version] from pyproject.toml (stdlib-only).
            PROJECT_VERSION=$(uv run --no-sync --no-project python -c \
              "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")

            if [ "$EFFECTIVE_TAG" != "$PROJECT_VERSION" ]; then
              echo "::error::Release tag (${EFFECTIVE_TAG}) does not match pyproject.toml [project.version] (${PROJECT_VERSION}). Refusing to publish. Bump [project.version] in pyproject.toml and tag matching, or amend the release tag."
              exit 1
            fi
            echo "::notice::tag ${EFFECTIVE_TAG} matches [project.version] ${PROJECT_VERSION} — proceeding to build + publish."
            echo "effective_tag=${EFFECTIVE_TAG}" >> "$GITHUB_OUTPUT"
    ```
  - [x] 4.2 Verify the regex matches: `1.0.0`, `1.0.0-rc.1`, `1.0.0-beta.2`, `1.0.0+build.123`, `1.0.0-rc.1+build.456`. Verify it rejects: `1.0`, `01.0.0`, `1.0.0-`, `1.0.0+`, the empty string. **Tightened regex from spec.** The Task 4.1 spec literal `^[0-9]+\.[0-9]+\.[0-9]+(?:-.+)?$` accepts `01.0.0` (leading zero) and `0` (no dots) — failing Task 4.2's verification cases. Implementation uses SemVer-2.0-correct `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$`. Local smoke: 5 SemVer-valid cases ACCEPT, 7 invalid cases REJECT (`1.0`, `01.0.0`, `1.00.0`, `1.0.0-`, `1.0.0+`, empty, `0`).
  - [x] 4.3 Verify `uv run --no-sync --no-project` runs without a venv (no `uv sync` first). This is critical — otherwise the first step takes 30s+ resolving deps just to read TOML. **Note:** uv warns `--no-sync has no effect when used alongside --no-project`; dropped the redundant `--no-sync` flag in the workflow.
  - [x] 4.4 Verify `tomllib` is stdlib on the target Python (Python ≥3.11 ships `tomllib`; `uv python install 3.13` from Task 3.1 guarantees it).
  - [x] 4.5 Smoke-test the guard logic locally:
    ```sh
    EFFECTIVE_TAG=0 PROJECT_VERSION=$(uv run --no-sync --no-project python -c \
      "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")
    echo "tag=$EFFECTIVE_TAG version=$PROJECT_VERSION"   # expect: tag=0 version=0
    ```
    Result should be `tag=0 version=0`; mismatch indicates either pyproject.toml drift or a typo in the heredoc.

- [x] **Task 5: Add the build step (AC5)**.
  - [x] 5.1 Append:
    ```yaml
        - name: Build distribution
          run: uv build
    ```
  - [x] 5.2 Do NOT prepend `rm -rf dist` — the runner is fresh; the directory is created by `uv build`.
  - [x] 5.3 Do NOT add a `Justfile` recipe — `Justfile` is do-not-touch per Constraint 1.
  - [x] 5.4 (Optional, deferred) — smoke-test the artifacts (`uv run --isolated --no-project --with dist/*.whl -- semvertag --version`). NOT included in v1.0 of this workflow per OQ5; flag if reviewer requests it.

- [x] **Task 6: Add the publish step (AC6, AC7)**.
  - [x] 6.1 Append:
    ```yaml
        - name: Publish to PyPI via trusted publishing
          run: uv publish
    ```
  - [x] 6.2 Verify there is no `--token` flag, no `--username` / `--password`, no `env:` block on the step.
  - [x] 6.3 Verify `pyproject.toml` is unchanged (no `[tool.uv]` `trusted-publishing = "always"` key was added — Constraint 1 + AC6 explicit).
  - [x] 6.4 Verify the entire `publish.yml` file is free of `PYPI_TOKEN`, `PYPI_API_TOKEN`, `TWINE_USERNAME`, `TWINE_PASSWORD`, `secrets.PYPI_`, and `--token` substrings (AC7 grep canary).

- [x] **Task 7: Create `docs/contributing/release.md` (AC8, AC9, AC10)**.
  - [x] 7.1 Create the `docs/contributing/` directory (it does not exist; `mkdir -p docs/contributing` or rely on `Write` to create both).
  - [x] 7.2 Write the release runbook with the sections specified in AC8 (One-time setup, Cutting a release, v1.0 pre-release gate, Troubleshooting).
  - [x] 7.3 Verify the runbook names all four PyPI trusted-publisher fields (Owner, Repository, Workflow filename, Environment name) per AC10.
  - [x] 7.4 Verify the v1.0 gate paragraph cites NFR9 + `epics.md:747` + Story 4.8.
  - [x] 7.5 Use `<org>` as the placeholder per Story 4.1 / 1.1 convention (Launch Decisions Pending; Story 4.7 owns substitution).
  - [x] 7.6 No external links to PyPI/GitHub docs that may rot — name the navigation paths ("PyPI project page → Publishing → Add a trusted publisher") rather than linking. The runbook is reference, not a tutorial.

- [x] **Task 8: Update `mkdocs.yml` nav to register the new page (AC9, AC11)**.
  - [x] 8.1 Edit `mkdocs.yml` nav block — minimal addition only:
    ```yaml
    nav:
      - Quick Start: index.md
      - Contributing:
        - Release runbook: contributing/release.md
    ```
  - [x] 8.2 Verify no other `mkdocs.yml` blocks are changed (theme, palette, markdown_extensions, extra — all preserved verbatim).
  - [x] 8.3 Verify `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` exits 0 against the new file + nav.

- [x] **Task 9: Local validation (AC12, AC13, AC14 readiness)**.
  - [x] 9.1 `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"` — **YAML OK**.
  - [x] 9.2 `just lint-ci` — eof-fixer + ruff format + ruff check + ty check all green.
  - [x] 9.3 `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` — built in 0.15s, no warnings/errors.
  - [x] 9.4 `just test` — **425 passed in 1.16s** (matches Story 4.1 baseline byte-exact).
  - [x] 9.5 `just test-branch-strategies` (26/26, 100% branch) + `just test-cc-strategies` (44/44, 100% branch) + `just test-doctor` (56/56, 100% branch).
  - [x] 9.6 `uv run ty check` — all checks passed.
  - [x] 9.7 `uv build` — sdist + wheel built cleanly (`dist/semvertag-0.tar.gz` + `dist/semvertag-0-py3-none-any.whl`). Pre-existing `uv_build` upper-bound warning is `_bmad/deferred-work.md §1-1` item, out of scope per Constraint 1. **Bonus sdist inspection (Task 11.2 closure):** `tar -tzf dist/semvertag-0.tar.gz | grep -E '_autosemver_reference|_bmad|docs/|site/'` returns empty — `uv_build`'s default excludes already handle the §1-1 "no sdist source-exclude" concern. dist/ removed post-smoke.
  - [x] 9.8 Source-tree drift check:
    ```sh
    git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md .github/workflows/ci.yml .github/workflows/dependency-update.yml
    ```
    **Empty.** AC11 + AC13 byte-exact preserved.
  - [x] 9.9 Grep canary on AC7:
    ```sh
    grep -E 'PYPI_TOKEN|PYPI_API_TOKEN|TWINE_USERNAME|TWINE_PASSWORD|secrets\.PYPI_|--token|--username|--password' .github/workflows/publish.yml
    ```
    **No matches** — AC7 passes.

- [x] **Task 10: Update `_bmad/sprint-status.yaml` and this story file (admin)**.
  - [x] 10.1 Bump `development_status['4-2-publish-workflow-via-trusted-publishing']` from `ready-for-dev` → `in-progress` at dev-start.
  - [x] 10.2 Tick all task/subtask checkboxes as each lands.
  - [x] 10.3 Fill in Dev Agent Record (Agent Model Used / Debug Log References / Completion Notes / File List / Change Log) at land time.
  - [x] 10.4 Bump `development_status['4-2-publish-workflow-via-trusted-publishing']` from `in-progress` → `review` when ready for code-review.
  - [x] 10.5 Set Status: `review` at the top of this file.
  - [x] 10.6 Update `last_updated` and `last_updated_note` in `sprint-status.yaml` with a one-line summary.

- [ ] **Task 11: Post-review — update `_bmad/deferred-work.md` (admin)**.
  - [ ] 11.1 Append `## Deferred from: code review of 4-2-publish-workflow-via-trusted-publishing (YYYY-MM-DD)` with any non-blocking decisions or discovered edge cases.
  - [ ] 11.2 Cross-link the closure of these prior deferred items (if applicable):
    - From `_bmad/deferred-work.md §1-1` (line 21): "`[tool.uv.build-backend]` declares no sdist `source-exclude`" → Story 4.2's `uv build` step will produce the first real artifact; flag for re-inspection of the sdist contents (does `_autosemver_reference/` or `_bmad/` ship?). If the sdist is bloated, this becomes a NEW deferred item; if clean (uv_build default-excludes those), it stays a 1-1 item.
    - From `_bmad/deferred-work.md §1-7` (line 103): "`--version` falls back to `'0'` silently" → Story 4.2 does NOT bump `[project.version]` per AC11; this item remains open until the maintainer cuts the first release per the runbook.

> **Note**: Task 11 (deferred-work updates) is gated on code-review per its own header ("Post-review"); intentionally left unchecked until code-review lands.

### Review Findings

_Generated by bmad-code-review on 2026-05-30. Three reviewers ran in parallel: Blind Hunter (17 raw findings), Edge Case Hunter (27 raw findings), Acceptance Auditor (1 violation). After dedup and triage: **6 decision-needed**, **10 patch**, **5 defer**, **9 dismissed as noise**. All 6 decisions resolved → 4 became patches, 2 dismissed as accepted-risk. All 14 patches applied 2026-05-30 (the 4 new patches from decisions + the original 10)._

#### Decision-needed (all resolved)

- [x] [Review][Decision]→[Patch] **Tag-guard regex inconsistencies — SemVer-strict vs PEP 440 vs runbook examples** — Resolved: keep SemVer + tighten + fix runbook examples. Regex now enforces SemVer §9/§10 strictly (rejects `1.0.0-01` and `1.0.0-.alpha` per smoke tests below); runbook reframes `1.0.0-rc.1` / `1.0.0+build.123` as guard-pass-but-PyPI-reject with an explicit caveat to use plain MAJOR.MINOR.PATCH tags until the workflow's tag language is aligned to PEP 440. Files: `publish.yml:71` and `docs/contributing/release.md` troubleshooting section.
- [x] [Review][Decision]→[Dismiss] **Single-job build+publish leaks OIDC token to the build backend** — Resolved: keep single job; risk accepted. `uv_build` is the configured pure-Python backend with no custom code; blast radius is theoretical until `pyproject.toml` switches backend. Reconsider if a non-stdlib build backend ever lands.
- [x] [Review][Decision]→[Patch] **`uv build` / `uv publish` rely on uv defaults; `setup-uv` not pinned to a uv version** — Resolved: pin uv version (`setup-uv` `with.version: "0.5.31"` — **verify against current stable at land time**), pass explicit `--out-dir dist` to `uv build`, explicit `dist/*` to `uv publish`, and add an `actions/upload-artifact` step for forensics. File: `publish.yml` setup-uv block + Build/Publish steps.
- [x] [Review][Decision]→[Patch] **No release-tag → main-branch ancestry check** — Resolved: add `target_commitish == 'main'` assertion as a guard step. `workflow_dispatch` skips the check (dispatched tag's ref is already maintainer-controlled). File: `publish.yml` "Verify release commit is on main" step.
- [x] [Review][Decision]→[Patch] **`<org>` placeholder in pyproject.toml, mkdocs.yml, runbook** — Resolved: keep placeholder (matches Change Log convention) and add a top-of-section `> Note:` instructing the maintainer to replace `<org>` before first release. File: `docs/contributing/release.md` One-time setup section.
- [x] [Review][Decision]→[Dismiss] **`--no-attestations` documented as an emergency lever but requires a code change** — Resolved: accept code-change recovery path. PyPI attestation rejections are rare; code-change adds audit trail. Reconsider if there's a real incident proving the need.

#### Patch (all applied 2026-05-30)

- [x] [Review][Patch] **`workflow_dispatch` checks out the dispatch branch, not the tagged commit** [`.github/workflows/publish.yml`] — Added `with.ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}` on `actions/checkout`.
- [x] [Review][Patch] **Release+dispatch concurrency collapse for same tag** [`.github/workflows/publish.yml`] — Group key now `publish-${{ github.event_name }}-${{ ... }}`; release and dispatch occupy separate groups.
- [x] [Review][Patch] **Concurrency group fragility on bad event / empty input** [`.github/workflows/publish.yml`] — Resolved as a side-effect of the previous patch (event_name in key prevents empty-input collapse on any unexpected future trigger).
- [x] [Review][Patch] **AC8 verbatim violation: "Cutting a release" header text** [`docs/contributing/release.md`] — Header swapped to spec-literal `## Cutting a release (≤5 minutes, target NFR13 + 5-min-from-merge-to-PyPI)`.
- [x] [Review][Patch] **Add `if: success()` on build/publish steps** [`.github/workflows/publish.yml`] — Added `if: success()` on Build, Upload, and Publish steps.
- [x] [Review][Patch] **`uv build` doesn't pin index strategy** [`.github/workflows/publish.yml`] — Added `env.UV_INDEX_URL: https://pypi.org/simple/` at the job level.
- [x] [Review][Patch] **Runbook lacks post-release `[project.version]` policy** [`docs/contributing/release.md`] — Step 2 of "Cutting a release" now states the bump is required for every release; `[project.version]` on `main` between releases reflects the previous release.
- [x] [Review][Patch] **Partial-upload PyPI 400 recovery path is undocumented** [`docs/contributing/release.md`] — Added a troubleshooting bullet: bump `[project.version]` patch number and re-tag; do NOT delete the partial PyPI artifact.
- [x] [Review][Patch] **Runbook references nonexistent `CHANGELOG.md` and Story 4.6** [`docs/contributing/release.md`] — Rewritten to use a one-line release-note in the GitHub release body until Story 4.6 lands.
- [x] [Review][Patch] **≤5min SLO contradicts the runbook's required-reviewers recommendation** [`docs/contributing/release.md`] — Added a one-line caveat that the budget excludes human-approval wait when required reviewers is enabled.

#### Patches from resolved decisions (applied 2026-05-30)

- [x] [Review][Patch] **Strict SemVer §9/§10 regex** [`publish.yml`] — Pre-release identifiers now reject leading-zero numerics and empty dot-segments; build metadata enforces dot-separated `[0-9A-Za-z-]+` per §10.
- [x] [Review][Patch] **Pin uv version + explicit build/publish args + upload-artifact** [`publish.yml`] — `setup-uv.with.version: "0.5.31"`; `uv build --out-dir dist`; `uv publish dist/*`; new `actions/upload-artifact` step retains `dist/` for 30 days.
- [x] [Review][Patch] **Release ancestry check** [`publish.yml`] — New guard step asserts `github.event.release.target_commitish == 'main'` on release events.
- [x] [Review][Patch] **`<org>` placeholder instruction** [`docs/contributing/release.md`] — One-time setup section gains a `> Note:` instructing the maintainer to replace `<org>` with the real GitHub owner before first release.

#### Pre-merge action items (all closed)

- [x] **Pin `actions/upload-artifact` to a vetted v4 SHA.** Resolved 2026-05-30: pinned to `ea165f8d65b6e75b540449e92b4886f43607fa02` (`gh api repos/actions/upload-artifact/git/refs/tags/v4`). The SHA is unique to `publish.yml` — `actions/upload-artifact` is not used in `dependency-update.yml`, so it is not part of the Task 3.4 cross-workflow SHA grep canary. Noted: action's currently-published major series is v7.0.1; v4 retained for now to match this workflow's conservative pin cadence — bump in a follow-up if/when the architecture's pinning policy is widened.
- [x] **Verify the pinned uv version.** Resolved 2026-05-30: `gh api repos/astral-sh/uv/releases/latest` returned `0.11.17` (2026-05-28). Bumped `setup-uv with.version` from the placeholder `0.5.31` to `0.11.17`.
- [x] **Re-run AC7 credential grep canary.** `grep -E 'PYPI_TOKEN|PYPI_API_TOKEN|TWINE_USERNAME|TWINE_PASSWORD|secrets\.PYPI_|--token|--username|--password' .github/workflows/publish.yml` → no matches (clean post-patch).
- [x] **Re-run gates end-to-end.** `yaml.safe_load` clean; `just lint-ci` clean (eof-fixer + ruff format + ruff check + ty check); `mkdocs build --strict` clean (0.20s); `just test` → 425 passed in 1.51s; strict-SemVer regex smoke (17 cases) all PASS.

#### Defer (pre-existing or non-blocking)

- [x] [Review][Defer] **`actions/checkout` fetch-depth=1 latent for VCS-derived versioning** [`.github/workflows/publish.yml:43`] — `pyproject.toml` has a static version today, so fetch-depth 1 is fine. If the project moves to `hatch-vcs` / `setuptools-scm`, fetch-depth needs to be 0. Pre-existing; will be flagged again if/when versioning strategy changes.
- [x] [Review][Defer] **`uv build` is not reproducible (no `SOURCE_DATE_EPOCH`)** [`.github/workflows/publish.yml:90-91`] — Re-running an old tag months later produces a wheel with different mtime/byte content. Combined with PyPI's filename-collision-on-content-hash policy, partial-upload retries can be unrecoverable. Reproducibility hardening can land in a follow-up story.
- [x] [Review][Defer] **`uv.lock` not used during publish — audited lockfile ≠ published wheel's runtime deps** — `uv build` doesn't consume `uv.lock`; published wheel's `Requires-Dist` comes from `pyproject.toml`'s unbounded specifiers. Pre-existing architecture decision; pip-audit's signal applies to the lockfile, not the published wheel.
- [x] [Review][Defer] **Future files in `docs/contributing/` will break `mkdocs --strict`** [`mkdocs.yml`] — Adding any orphan file under `docs/contributing/` without updating the nav will fail `mkdocs build --strict` in CI. Future trap created by this PR but not blocking now.
- [x] [Review][Defer] **Publish uses Python 3.13 only; CI matrix tests 3.10–3.14** [`.github/workflows/publish.yml:49`] — For a pure-Python `py3-none-any` wheel this is fine. If `[tool.uv.build-backend]` ever adds native code, the wheel will be tagged 3.13-only. Latent.

#### Dismissed as noise

`B8` cwd-relative pyproject path (speculative future `cd`), `B9` "Refusing to publish" wording trap (accurate today), `B12` SHA visual-verify (AC7 grep canary already covers this and Acceptance Auditor confirmed it passes), `B13` no per-step timeout (job-level 15min is bounded), `E5` case-sensitive `v` strip (`V1.0.0` correctly rejected with arguably-confusing message; SemVer convention is lowercase `v`), `E6` `--no-project` would fail on future `requires-python >=3.14` (speculative), `E7` `grep -Eq` exit code 2 on binary input (safe by accident; theoretical UI concern only), `E25` Contributing nav parent has no index page (polish nit), `E27` 15-minute timeout below uv's worst-case PyPI-retry window (speculative).

## Dev Notes

### Story framing

Story 4.2 is the **second story of Epic 4** (Public-Launch Readiness) and the second slice of the "Trust-surface scaffolding" implementation-sequence step 9 (`architecture.md:594`). Where 4.1 polished `ci.yml` + added `dependency-update.yml`, 4.2 lands the **third workflow file** that the architecture's `.github/workflows/` shape mandates (`architecture.md:1058-1060`):

```
.github/workflows/
├── ci.yml                              # Stories 1.1 + 4.1
├── dependency-update.yml               # Story 4.1
└── publish.yml                         # Story 4.2 (this story)
```

The work is **entirely under `.github/workflows/`** plus a new `docs/contributing/release.md` runbook and a minimal `mkdocs.yml` nav addition — zero changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, or any existing workflow file.

The epic ACs (`epics.md:723-747`) are 4 narrative G/W/T triplets covering:
1. The workflow exists, fires on `release: published`, runs `uv build` + `uv publish` with `id-token: write`, no `PYPI_TOKEN` reference.
2. With PyPI-side trusted-publisher set up, the publish succeeds without explicit credentials.
3. A pre-publish guard fails on tag/`[project.version]` mismatch.
4. A release runbook supports a ≤5-min flow with an explicit v1.0+ Story 4.8 shadow-mode gate.

These four narratives expand to 14 dev-facing ACs above (mirrors Story 4.1's granularity discipline).

### Critical architectural constraints

1. **No source-code changes — workflow YAML + docs + nav-line only.** Story 4.2 is **NOT** a refactor, **NOT** a feature, **NOT** a test addition. The dev should resist any temptation to "while we're in there" tidy `pyproject.toml`, `Justfile`, or `semvertag/`. If a workflow change surfaces a `pyproject.toml` change (e.g., a `[tool.uv] trusted-publishing = "always"` key) it MUST be flagged as a NEW story or a deferred item — not slipped in.

2. **`uv publish` (not `pypa/gh-action-pypi-publish`, not `twine`).** The architecture explicitly names `uv publish` at line 1347 ("PyPI via `uv publish` with PyPI trusted publishing"). The uv canonical workflow (Context7-confirmed against `docs.astral.sh/uv/guides/integration/github`) uses `uv publish` directly and relies on uv's built-in trusted-publishing detection. Adding `pypa/gh-action-pypi-publish` would:
   - Introduce a third-party action with `id-token: write` — supply-chain attack surface increase.
   - Duplicate uv's native capability for no functional gain.
   - Diverge from the architecture's stated invocation pattern.
   **Decision:** stay with `uv publish`.

3. **SHA-pin every action in this workflow.** Story 4.1's `dependency-update.yml` established the precedent: write-scope workflows SHA-pin. `publish.yml` has `id-token: write` — the OIDC token exchanged with PyPI confers PyPI write scope on this repo. Tag retargeting on `astral-sh/setup-uv@v3` would yield code execution with PyPI publishing privileges. Blast radius is **asymmetric** vs. `ci.yml`'s read-only context. The SHAs MUST match `dependency-update.yml`'s vetted set verbatim (no new SHA lookups; Story 4.1 already did the work).

4. **GitHub Environment `pypi` (job-level) is non-negotiable.** The PyPI trusted-publisher configuration **requires** an environment name to bind against (per PyPI's "Add a trusted publisher" UI: Owner + Repo + Workflow + Environment). Without `environment: name: pypi` on the publish job, the OIDC subject claim will lack the `environment:` segment and PyPI will reject the token exchange. Story 4.2 MUST add `environment: name: pypi` at the **job level** (not workflow level — top-level environments don't exist in GitHub Actions schema).

5. **Permissions are scoped to exactly two: `id-token: write` + `contents: read`.** NO `actions: write`, NO `issues: write`, NO `pull-requests: write` — none are required by `release: published` triggers or trusted publishing. Each additional permission widens the OIDC token's claims and the workflow's blast radius. AC2's explicit minimal-permission set is the security floor.

6. **`Justfile` MUST NOT gain a `publish` recipe.** Modern-di's `Justfile:25-29` ships a `publish` recipe that uses `uv publish --token $PYPI_TOKEN` — **exactly** the long-lived-token model NFR13 forbids. If a future contributor copies the modern-di pattern wholesale into semvertag's `Justfile`, NFR13 is silently violated the next time someone runs `just publish` from a developer machine with `PYPI_TOKEN` in their shell. The cleanest defense is to **never have a `Justfile` publish recipe at all**: the only publish path is the trusted-publishing workflow. The runbook (AC8) reinforces this by naming "GitHub Releases → Draft → Publish release" as the publish trigger, not "run `just publish`".

7. **No `[tool.uv] trusted-publishing = "always"` in `pyproject.toml`.** This key forces uv to require trusted publishing (and error if not detected) — useful defense-in-depth, but `pyproject.toml` is do-not-touch in this story. Defer to a later story (or fold into Story 4.6 trust-surface markdown if it lands `pyproject.toml` adjustments).

8. **`uv build` is invoked directly in `publish.yml`, not via `just build`.** Story 4.1's Constraint 3 ("Justfile is the single source of truth for code-quality / build / test invocations") had a documented exception for `uv build` in the `lint` job because no `Justfile` recipe exists for it. Same applies here. NOT adding a `just build` recipe in this story preserves the recipe surface at `default / install / lint / lint-ci / test / test-branch / test-branch-strategies / test-cc-strategies / test-doctor` (10 recipes — matches Story 4.1's anti-recipe-bloat discipline). If a future story needs `just build` for an automation hook, that's a separate decision.

9. **Pre-publish tag-guard semantics: `[project.version]` is canonical, the tag is checked against it.** AC4 codifies a model where the maintainer (a) bumps `[project.version]` in `pyproject.toml`, (b) tags `v<X.Y.Z>`, (c) clicks "Publish release". The workflow asserts `tag == [project.version]`. This is **different** from modern-di's pattern (`uv version $GITHUB_REF_NAME` at workflow-time, which would let the tag drive the version write). Semvertag's model is:
   - The `[project.version]` value is authoritative; it survives in git history.
   - The tag asserts equality, doesn't mutate.
   - Pre-release versions (e.g., `v1.0.0-rc.1`) require pre-bumping `[project.version]` to `1.0.0-rc.1` first.

   This trades release-prep ergonomics (one extra PR per release) for git-history clarity (version moves are auditable PR diffs). Architecture-amendment territory if maintainers find the friction unacceptable.

10. **The workflow does NOT smoke-test the built artifact.** The uv canonical workflow (Context7) shows two optional smoke-test steps (`uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py` and `... dist/*.tar.gz ...`). Story 4.2 omits them because:
    - No `tests/smoke_test.py` file exists (would require a `tests/**/*.py` change — Constraint 1).
    - The `ci.yml` pytest matrix on Python 3.10–3.14 already validates installation/import shape at PR time.
    - A wheel/sdist install smoke is high-value but is its own contained AC + test fixture decision — defer to a follow-up story.

    See OQ5 for the deferral logic.

11. **`mkdocs.yml` gets a 2-line nav addition only.** Story 4.4 owns the full mkdocs nav redesign (Quick Start + CLI reference + strategies + providers + doctor pages). Story 4.2 adds the single `Contributing → Release runbook` entry because `ci.yml`'s `mkdocs build --strict` step would fail on an orphan doc page — registering it is the minimum-viable nav touch. Do NOT introduce additional nav structure speculatively.

12. **`<org>` placeholder preserved in the runbook.** Per Story 4.1 + Story 1.1 + the project's pre-launch convention, `<org>` is left literal across `pyproject.toml`, `mkdocs.yml`, `README.md`, and now `docs/contributing/release.md`. Story 4.7 owns the concrete substitution pass (Launch Decisions Pending).

13. **No `actionlint` install step in CI.** Inherits Story 4.1's Constraint 12 — local linting only (AC12); a CI `actionlint` gate is a separate story. The local fallback to `yaml.safe_load` is acceptable.

14. **No `workflow_run` chain to `ci.yml`.** Unlike `dependency-update.yml` (which triggers `gh workflow run ci.yml --ref <branch>` to re-fire CI on the bot PR), `publish.yml` operates on a *tag*, not a branch — there is no PR-to-re-trigger and the artifact validation already happened on `main` before tagging. NO `gh workflow run ci.yml` step is added.

15. **Comment policy in YAML.** YAML comments at step level are allowed and encouraged for non-obvious lines: the SHA-pin justification (Task 3.2 comment block), the `id-token: write` purpose (AC2 inline comment), the `cancel-in-progress: false` rationale (per-tag group). The CLAUDE.md "only WHY when non-obvious" rule applies to Python; YAML conditional expressions and OIDC permissions are notoriously cryptic so WHY comments are a courtesy to future maintainers.

### Files this story touches

| File | Action | Notes |
|---|---|---|
| `.github/workflows/publish.yml` | **NEW** | `release: published` trigger + `workflow_dispatch` (tag input); `permissions: id-token: write + contents: read`; `environment: pypi` job-level; SHA-pinned actions; pre-publish tag guard; `uv build` + `uv publish`. ~90 LOC of YAML. |
| `docs/contributing/release.md` | **NEW** | Release runbook: one-time PyPI trusted-publisher setup; cutting-a-release steps; v1.0+ Story 4.8 shadow-mode pre-release gate; troubleshooting. ~70 LOC markdown. |
| `mkdocs.yml` | **UPDATE** | Add 3-line `Contributing → Release runbook` nav entry; preserve rest verbatim. |
| `_bmad/sprint-status.yaml` | **UPDATE** | `4-2-publish-workflow-via-trusted-publishing: backlog → ready-for-dev → in-progress → review`; `last_updated` + `last_updated_note`. Epic-4 already `in-progress` (set by Story 4.1's create-story). |
| `_bmad/4-2-publish-workflow-via-trusted-publishing.md` (this file) | **UPDATE** | Status, all task/subtask checkboxes, Dev Agent Record, File List, Change Log. |
| `_bmad/deferred-work.md` | **UPDATE** (post-review only) | Append `## Deferred from: code review of 4-2-…` for any non-blocking decisions / discovered edge cases. |
| **Do-not-touch** (Epic 4.2 scope guardrails) | — | All `semvertag/**/*.py`, all `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `.gitignore`, `docs/index.md`, `docs/requirements.txt`, `context7.json`, `LICENSE`, `CLAUDE.md`, `.github/workflows/ci.yml`, `.github/workflows/dependency-update.yml`. |

### Anti-patterns to avoid

(Architecture §Anti-Patterns + uv-canonical-workflow patterns + Story 4.1 inherited discipline.)

- **`uv publish --token $PYPI_TOKEN` / `secrets.PYPI_TOKEN`** — direct NFR13 violation. The whole point of this story is to **remove** the token-publishing path. If the dev writes `--token`, the AC7 grep canary catches it; if it slips past, NFR13 holds only by maintainer-discipline rather than by structural impossibility.
- **`pypa/gh-action-pypi-publish@v1` instead of `uv publish`** — Constraint 2 above. Adds a third-party action with `id-token: write`. Stay with `uv publish`.
- **`environment: name: pypi` at the workflow level** — invalid schema. `environment:` is a **job-level** key in GitHub Actions. Workflow-level placement is silently ignored, which means the OIDC subject claim lacks the `environment:` segment and PyPI rejects the token.
- **`id-token: write` at the workflow level instead of step/job level** — works, but widens the OIDC permission scope to **all** jobs in the workflow. Currently there's only one job (`publish`), so the difference is moot — but if a future story adds a second job (e.g., a "post-publish" notification job), workflow-level permissions accidentally extend `id-token: write` to that job. Job-level placement is the defense.
- **Adding `actions: write` / `issues: write` / `pull-requests: write` "just in case"** — Constraint 5 above. Each additional permission widens OIDC claims and blast radius. NFR14 (`SECURITY.md`) and NFR13 (no tokens) are both backstops; this is the front gate.
- **A `Justfile` `publish` recipe** — Constraint 6 above. The only publish path is the trusted-publishing workflow. Maintainers MUST NOT have a `just publish` shortcut that uses a local token.
- **`uv publish --trusted-publishing always` in the workflow** — redundant; uv's default in a detected GitHub Actions OIDC environment is "use trusted publishing if available." Adding the flag is harmless but verbose; the canonical uv workflow omits it.
- **`twine upload` anywhere** — twine is the legacy path; we use uv. Twine would also need credentials, which we're explicitly avoiding.
- **`on: push: tags: ['v*']`** instead of `release: published`** — the spec is explicit (`release: published`). Tag-push triggers fire on **every** tag push (including non-release tags); release-published fires only when a maintainer clicks "Publish release" through the GitHub UI (or API). The latter is the desired human gate.
- **Auto-bumping `[project.version]` in the workflow** (modern-di's `uv version $GITHUB_REF_NAME` pattern) — Constraint 9 above. Semvertag's model is "version moves are PR diffs." Auto-bumping inside the workflow leaves the released artifact's version disagreeing with `main`'s `pyproject.toml` until a follow-up commit lands — confusing for git-history-readers.
- **Smoke-test step that fails the publish if the wheel doesn't import semvertag cleanly** — high-value gate, but introducing it now requires a `tests/smoke_test.py` file (Constraint 1 prohibits). Defer.
- **`continue-on-error: true`** on any step — masks real failures. The tag guard's `exit 1` is hard-fail by design.
- **Tag-pinning actions in this workflow** — Constraint 3 above. SHA-pinning is structurally required because the workflow has write scope to PyPI.
- **Putting trusted-publisher setup *into* the workflow** (e.g., an action that calls PyPI's API to register the publisher) — out of scope per the epic AC's "manual one-time setup step documented in the release runbook, not in this workflow" (`epics.md:736`). The runbook documents it; the workflow assumes it's been done.
- **Adding a `dependabot.yml` for `.github/workflows/`** — could be valuable, but it's a separate decision (the SHA-pin discipline currently makes dependabot bumps noisy). Defer to a future supply-chain story.

### Deferred-work items relevant to this story (lineage)

The following items from `_bmad/deferred-work.md` are **adjacent** to Story 4.2's surface; the dev should be aware of them but most are NOT closed by this story:

| Deferred item | Story 4.2 relationship | Resolves? |
|---|---|---|
| `_bmad/deferred-work.md §1-1` (line 21): `[tool.uv.build-backend]` no sdist `source-exclude` — `_autosemver_reference/`, `_bmad/`, `docs/`, top-level dotfiles may ship inside the sdist | Story 4.2's `uv build` produces the first real artifact eligible for inspection. Post-merge action: `tar -tzf dist/*.tar.gz \| grep -E '(_autosemver_reference\|_bmad)'` should be empty. If not, OPEN a NEW deferred item for a `source-exclude` pyproject.toml hardening story. | PARTIAL — verifies, may open follow-up |
| `_bmad/deferred-work.md §1-7` (line 103): `--version` falls back to `'0'` silently on PackageNotFoundError; "Story 4.2 (PyPI trusted publishing) will land a real version" | Story 4.2 ships the publish PIPELINE, not the first release itself. `[project.version]` stays at `"0"` per AC11. The pre-publish guard correctly REFUSES any non-`0` tag, forcing the maintainer to bump on first release per the runbook. | NO — deferred to first-release operation |
| `_bmad/deferred-work.md §1-1` (line 20): Production dependencies (`typer`, `rich`, `semver`, `pydantic-settings`, `modern-di-typer`, `httpx2`) carry no version pins or lower bounds — NFR12 only partially protected by uv.lock | NOT addressed in 4.2; flagged in Story 4.1's review section as `_bmad/deferred-work.md §4-1` (line 135). 4.2 does not modify `pyproject.toml`. | NO |
| `_bmad/deferred-work.md §1-1` (line 12): `<org>` URL placeholders in `pyproject.toml [project.urls]` and `mkdocs.yml repo_url`/`extra.social` — pre-launch resolution per Launch Decisions Pending | Story 4.2 ADDS `<org>` placeholders to `docs/contributing/release.md` and uses the existing `<org>` placeholder in `mkdocs.yml`. Convention preserved; Story 4.7 owns the substitution pass. | NO — convention preserved |

The following items from prior reviews are **out of scope** for Story 4.2:

- All Story 1.4 / 1.5 / 1.6 / 2.1 / 3.1 / 3.2 deferred items (Python code; this story is YAML + docs).
- Story 4.1's `OQ7` (semvertag LOC over 1500): the LOC gate is in `ci.yml`'s `lint` job; `publish.yml` does not consume it. No movement.
- Story 4.1 review deferred items at `_bmad/deferred-work.md §4-1` (lines 133-143) — orthogonal: `dependency-update.yml` polish, codecov v5 token-vs-with form, README `<org>` placeholder.

### Learnings from Story 4.1 (carried forward)

[Source: `_bmad/4-1-ci-workflow-polish.md` Dev Agent Record + Review Findings; `_bmad/deferred-work.md §4-1`]

- **Write-scope workflows SHA-pin actions** (Story 4.1 dependency-update.yml Decision 3). Story 4.2 inherits this verbatim — `id-token: write` is a write-scope permission against PyPI. SHA pins MUST match `dependency-update.yml`'s vetted set so a reviewer can verify with a single `grep`.
- **Explicit event/schedule allowlists fail loud on unexpected triggers** (Story 4.1 dependency-update.yml MODE routing — Decision-needed P5). Story 4.2's pre-publish guard (Task 4.1) follows the same pattern: explicit `release` / `workflow_dispatch` allowlist, `exit 1` on anything else.
- **Per-job `timeout-minutes`** (Story 4.1 AC6). Story 4.2's publish job gets `timeout-minutes: 15` — same value as `dependency-update.yml`'s `lock-upgrade` job (the runner spends most of its time on `uv build` + network round-trips to PyPI; 15min is comfortable).
- **`yaml.safe_load` is the accepted `actionlint` fallback** (Story 4.1 AC12). Story 4.2 inherits this.
- **Pre-existing E501 regression discipline** (Epic 3 retro B14). Story 4.2's post-review patch cycle (if any) MUST re-run the full `just lint-ci` + `just test` + `uv build` gate, not just targeted checks. (No Python in this story, so the risk surface is narrower — but the discipline holds.)
- **`<org>` placeholder convention** (Story 1.1 + Story 4.1). Carry forward; Story 4.7 substitutes.
- **Architecture-mandated action pins are non-negotiable in implementation** (Stories 1.1 / 1.7 / 2.1 / 3.x / 4.1 all respected the `@v3` / `@v2` discipline). Story 4.2 inherits — the SHA-pin discipline is *additive* to architecture's tag pins, not a replacement.
- **No comment policy violation in YAML** (Story 4.1 Constraint 13). Story 4.2 inherits.
- **`_bmad/deferred-work.md` lineage cross-linking** (Stories 3.2 + 4.1). Story 4.2 follows the convention (Task 11.2 cross-link block).

### Learnings from Epic 3 retrospective (forward-looking, applies to 4.2)

[Source: `_bmad/epic-3-retro-2026-05-29.md`]

- **C1 — Story 4.2 introduces a new token surface that doctor doesn't yet check.** Quoting the retro verbatim: *"PyPI Trusted Publishing uses an OIDC token in the publish workflow. Doctor v1.0 only checks GitLab tokens. If a future doctor variant wants to validate publish-time tokens (`semvertag doctor --check pypi-publishing`?), it would require a new `Provider.check_*` method and corresponding `_checks.py` / `_render.py` wiring. **Out of v1.0 scope**; flag as v1.x consideration."* Story 4.2 honors this — the doctor module is NOT extended.
- **B7 (Epic 3 retro action item)** — "Publish doctor JSON envelope schema in Story 4.4 mkdocs content." Adjacent to 4.2: the runbook references `[project.version]` discipline but does not document the JSON schema. Story 4.4 owns the doctor schema publishing.
- **B14 (Epic 3 retro action item)** — post-review patches re-run the FULL gate. Story 4.2's review cycle inherits this.

### Web research — uv publish + trusted publishing best practices

[Source: Context7 `/websites/astral_sh_uv` against `docs.astral.sh/uv/guides/integration/github` and `docs.astral.sh/uv/reference/cli`, retrieved 2026-05-30]

- **Canonical uv-recommended publish workflow** uses:
  - `on: push: tags: ['v*']` (semvertag uses `release: published` instead per architecture; both are valid GitHub-Actions-side triggers).
  - `environment: name: pypi` at job level.
  - `permissions: id-token: write, contents: read`.
  - SHA-pinned `astral-sh/setup-uv` (e.g., `08807647e7069bb48b6ef5acd8ec9567f424441b  # v8.1.0` in the canonical example).
  - `uv python install 3.13`.
  - `uv build` then `uv publish` (no `--token`, no explicit `--trusted-publishing` flag).
  - Optional smoke-test steps (`uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py`) — semvertag defers per Constraint 10 / OQ5.
- **`uv publish` trusted-publishing detection**: by default checks for trusted publishing in supported environments (GitHub Actions, GitLab CI/CD); ignores if not configured. The `[tool.uv] trusted-publishing = "always"` in `pyproject.toml` forces it. Semvertag accepts the default-detect behavior (Constraint 7).
- **PEP 740 attestations** are uploaded by default (`uv publish` auto-discovers attestation files alongside the dist files; `--no-attestations` disables). Semvertag's `pyproject.toml` does not declare attestations and `uv build` does not generate them; PyPI's trusted-publishing path will accept the upload regardless. Future attestation discipline is a separate trust-surface decision (potentially Story 4.6 territory).
- **`astral-sh/setup-uv` current stable** is `v8.1.0` (April 2026 research; carried forward from Story 4.1 OQ3). Architecture-mandated `@v3` is 5 majors behind. Semvertag preserves `@v3` per Story 4.1 Constraint 2 (architecture-amendment required to bump).
- **`actions/checkout` current stable** is `v6` (Context7 canonical example uses `@v6`). Architecture mandates `@v4`; semvertag preserves `@v4` per architecture pinning discipline.
- **Trusted publisher configuration on PyPI side**: Owner + Repository + Workflow filename + Environment name. All four must match the GitHub-side config exactly. The runbook (AC10) names all four.

### Testing standards

(No Python tests are added by this story. The "tests" for this story are CI-run validations + local-validation gates.)

- **`actionlint`** (or `yaml.safe_load` fallback) — AC12 local validation gate.
- **`mkdocs build --strict`** — AC9 + AC12 local validation gate; catches the new `release.md` being orphaned from nav.
- **Green CI run on the PR** — AC14 acceptance gate. All `ci.yml` jobs (`lint`, `pytest` × 5 matrix cells, `pip-audit`) end in `success` with the new file present.
- **AC7 grep canary** — `grep -E 'PYPI_TOKEN|...|--token|--username|--password' .github/workflows/publish.yml` returns no matches.
- **AC13 byte-exact preservation check** — `git diff HEAD -- .github/workflows/ci.yml .github/workflows/dependency-update.yml pyproject.toml Justfile README.md` returns empty.
- **AC11 do-not-touch check** — `git diff HEAD -- semvertag/ tests/` returns empty.
- **NO `tests/**/*.py` additions** — Constraint 1.
- **NO new pytest recipes in `Justfile`** — Constraint 1.
- **OPTIONAL `workflow_dispatch` smoke** — AC14 explicitly bounds this to static-validation only; do NOT actually publish.

### Project Structure Notes

After this story:

- `.github/workflows/` grows from 2 files (`ci.yml` + `dependency-update.yml`) to 3 (`+ publish.yml`). Matches `architecture.md:1058-1060` directory shape in full.
- `publish.yml` is ~90 lines of YAML (NEW).
- `docs/contributing/release.md` is ~70 lines of markdown (NEW).
- `docs/contributing/` directory is created (NEW; first sub-page under `docs/`).
- `mkdocs.yml` grows by 3 nav lines (`Contributing:` section + nested `Release runbook:` entry).
- No Python source-LOC change → NFR21 LOC count post-this-story is unchanged from Story 4.1's measurement (1535 LOC; gate continues to emit `::warning::` per OQ7 in `_bmad/deferred-work.md §4-1`).
- The next story in `sprint-status.yaml` is `4-3a-github-actions-marketplace-wrapper` (currently `backlog`). Story 4.2 does **not** auto-promote it.
- Epic-4 retrospective remains **optional** per `sprint-status.yaml:79`.

### Open questions / dev assumptions

The dev should resolve these during implementation or escalate to architecture review:

**OQ1 — `release: published` vs `release: released`.**
The GitHub Actions event taxonomy distinguishes `release: published` (fires on initial publish OR un-prerelease) from `release: released` (fires only on prerelease→stable transition). Semvertag's spec says "published" verbatim (`epics.md:732, 740-742`; `architecture.md:250, 1060`). **Assumption:** `released` (subset of `published`) is more restrictive but excludes prerelease cuts (`v1.0.0-rc.1`); the spec wording is "published" → use it. If the maintainer wants prerelease publishes to skip CI fire, swap to `released` in a follow-up.

**OQ2 — `actions/checkout` is `@v4` per architecture; canonical uv workflow uses `@v6`.**
Carries forward Story 4.1 OQ3. Story 4.2 preserves `@v4` (architecture-mandated). Architecture-amendment story needed for the bump; do NOT bump in this story.

**OQ3 — `uv python install 3.13` vs `3.10` for the build step.**
The canonical uv workflow installs 3.13; the project's floor is 3.10. Building on 3.13 produces an artifact that should be Python-version-agnostic (it's a pure-Python project; the wheel tag is `py3-none-any`), so the build Python version is cosmetic. **Assumption:** 3.13 matches the uv-canonical pattern and the latest test cell; preferred. Reviewer may request 3.10 for floor-version parity.

**OQ4 — `pyproject.toml` ships `[project.version] = "0"`; the first release requires a bump.**
This story does NOT bump it (per AC11). The pre-publish guard will REFUSE any tag != `"0"`. The first release MUST come with a release-prep PR that bumps `[project.version]` to a real value (e.g., `0.1.0`). Documented in the runbook (AC8 "Cutting a release" step 2). **Assumption:** this is the correct scope boundary — Story 4.2 is the PIPELINE story; first-release is an operation. Flag if reviewer wants the bump folded into 4.2.

**OQ5 — Build-artifact smoke test (uv canonical pattern) deferred.**
The uv canonical workflow includes two smoke-test steps: `uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py` and `... dist/*.tar.gz ...`. These require:
- A `tests/smoke_test.py` file (Constraint 1 prohibits `tests/**/*.py` changes).
- A decision on smoke-test scope (CLI invocation? Import check? semvertag-version assertion?).

**Assumption:** defer to a follow-up story (could be 4.2.1, or fold into 4.6 trust-surface markdown if it touches `tests/`). Document in deferred-work post-review.

**OQ6 — PEP 740 attestations: enable, disable, or accept default?**
`uv publish`'s default is "upload attestations if found." Semvertag's `uv build` does not generate attestations by default (uv reads them from disk; the action that *generates* them is upstream of `uv build`). Effective default: no attestations uploaded. Generating attestations would require additional sigstore/cosign tooling. **Assumption:** accept the default (no attestations uploaded for v1.0); future attestation discipline is Story 4.6 territory. The runbook's "Troubleshooting" section documents `--no-attestations` only as an emergency lever.

**OQ7 — Trusted publisher setup uses ENVIRONMENT name `pypi`; PyPI also supports trusted publishing WITHOUT an environment.**
Per PyPI's trusted-publisher docs, the Environment field is optional. Omitting it would let the OIDC subject claim be `repo:<org>/semvertag:ref:refs/tags/v*` (or similar) without an `environment:` segment. **Assumption:** use environment `pypi` for two reasons: (a) GitHub Environment supports required-reviewers gating (defense-in-depth on accidental publishes); (b) the uv-canonical workflow uses an environment, and aligning with it eases future contributor onboarding. Flag if reviewer prefers no-env for simplicity.

**OQ8 — `_redact.py` regex potential collision with version strings.**
The pre-publish guard prints `[project.version]` and `EFFECTIVE_TAG` to stderr/`$GITHUB_OUTPUT`. Neither is a secret. The values flow through GitHub-Actions logging, not through semvertag's `_redact.py` (that lives in the Python package; the workflow is shell). **Assumption:** no redaction concern; `[project.version]` is public and intentional.

**OQ9 — `workflow_dispatch` enables manual re-runs; should it require a reviewer?**
The `workflow_dispatch` trigger is gated by repo-write permission by default. The `environment: pypi` job-level config adds GitHub Environment guardrails (required reviewers, wait timers, etc.) for the publish step but NOT for the workflow-dispatch event itself. **Assumption:** out of scope for this story (repo Settings → Environment config is documented in the runbook as a recommended one-time setup; no workflow code mediates it).

**OQ10 — `[tool.uv] trusted-publishing = "always"` for defense-in-depth.**
Setting this key forces `uv publish` to require trusted publishing and error if not detected. Useful belt-and-braces against a future workflow tweak that accidentally drops `id-token: write`. **Assumption:** Constraint 7 — don't touch `pyproject.toml` in this story; add the key in a follow-up that also bumps version (Story 4.6 or first-release prep PR).

## References

- [Source: epics.md#Story 4.2 lines 723–747] — Story 4.2's verbatim ACs and framing
- [Source: epics.md#Epic 4 lines 689–722] — Epic 4 framing; Story 4.1's verbatim ACs as the directly-prior story
- [Source: prd.md#NFR13 line 588] — Released PyPI artifacts signed via PyPI trusted publishing; no long-lived API tokens in CI secrets
- [Source: prd.md#NFR9 line 581] — Shadow-mode parity gate referenced from the v1.0+ pre-release section of the runbook
- [Source: prd.md#NFR12 line 587] — pip-audit clean-report at every release (not directly in 4.2's scope but adjacent — release readiness)
- [Source: prd.md "Trust surface" line 129] — "Publish workflow on GitHub release: `uv build` + `uv publish` (trusted-publishing preferred over token)"
- [Source: architecture.md#CI & Release lines 248–250] — "GitHub Actions; … Publish on release: published via PyPI trusted publishing (NFR13)"
- [Source: architecture.md#Deltas vs. modern-di line 265] — "PyPI trusted publishing replaces token publishing (NFR13)"
- [Source: architecture.md#Directory Structure lines 1058–1060] — `.github/workflows/{ci.yml, publish.yml}` shape
- [Source: architecture.md#External boundaries table line 1179] — "PyPI (publish) | CI → external | trusted publishing via OIDC | .github/workflows/publish.yml"
- [Source: architecture.md#Deployment line 1347] — "PyPI via `uv publish` with PyPI trusted publishing (no long-lived PYPI_TOKEN; NFR13)"
- [Source: architecture.md#Implementation Sequence line 594] — step 9 (Trust-surface scaffolding) — 4.1 + 4.2 sequencing
- [Source: architecture.md#PRD-Touch-Up backlog item #5] — (if applicable) any PRD-edit affecting publish; none currently
- [Source: .github/workflows/ci.yml — post-Story 4.1 verbatim] — byte-identical preservation requirement (AC13)
- [Source: .github/workflows/dependency-update.yml — post-Story 4.1 verbatim] — SHA-pin precedent + comment-block style (Task 3.2)
- [Source: pyproject.toml lines 1–94] — `[project.version] = "0"` placeholder; `[tool.uv.build-backend]` declares the build backend; do-not-touch per AC11
- [Source: mkdocs.yml lines 1–63] — current minimal nav; AC9 adds the Contributing → Release runbook entry
- [Source: README.md lines 1–7] — current top-of-file shape; do-not-touch per AC11
- [Source: Justfile lines 1–33] — recipe surface; NO `publish` recipe (per Constraint 6)
- [Source: docs/index.md] — only existing doc page; release.md is the second
- [Source: _bmad/4-1-ci-workflow-polish.md (Status: done)] — most-recent landed story; SHA-pin discipline, MODE allowlist pattern, scope-discipline Constraint 1, AC granularity discipline
- [Source: _bmad/deferred-work.md §1-1 line 21] — sdist `source-exclude` follow-up surface (Task 11.2)
- [Source: _bmad/deferred-work.md §1-7 line 103] — `--version` falls back to `'0'` until first release (Task 11.2)
- [Source: _bmad/deferred-work.md §4-1 lines 133-143] — Story 4.1 deferred items (orthogonal; none addressed here)
- [Source: _bmad/epic-3-retro-2026-05-29.md C1 line 165-166] — "Story 4.2 introduces a new token surface that doctor doesn't yet check" — explicit out-of-scope guidance
- [Source: _bmad/epic-3-retro-2026-05-29.md B14 line 191] — post-review patches re-run the full gate
- [Source: _bmad/sprint-status.yaml line 71] — `4-2-publish-workflow-via-trusted-publishing: backlog` → `ready-for-dev` transition target
- [Source: _bmad/sprint-status.yaml line 69] — `epic-4: in-progress` (set by Story 4.1's create-story; no transition required)
- [Source: docs.astral.sh/uv/guides/integration/github (via Context7 `/websites/astral_sh_uv`)] — canonical uv publish workflow pattern: `environment: name: pypi`, `permissions: id-token: write + contents: read`, `uv build` → `uv publish`, smoke tests optional
- [Source: docs.astral.sh/uv/reference/cli (via Context7)] — `uv publish` flags surface: `--token` (forbidden in 4.2), `--no-attestations` (acceptable emergency lever), trusted-publishing auto-detect default
- [Source: docs.astral.sh/uv/reference/settings (via Context7)] — `[tool.uv] trusted-publishing = "always"` defense-in-depth key (not added in 4.2 per Constraint 7)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — bmad-dev-story workflow, 2026-05-30

### Debug Log References

- YAML syntax validation: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"` → `YAML OK`.
- `actionlint` unavailable locally (Go binary; not on PyPI); used AC12's explicit `yaml.safe_load` fallback per Story 4.1 precedent.
- Tag-guard regex smoke (Task 4.2): 5 SemVer-valid cases ACCEPT, 7 invalid cases REJECT. Initial spec regex `^[0-9]+\.[0-9]+\.[0-9]+(?:-.+)?$` would accept `01.0.0` and lacks the `+build` branch — Task 4.2 verification mandates rejecting `01.0.0`, so implementation tightened to SemVer-2.0-correct `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$`.
- Tag-guard TOML read smoke: `uv run --no-project python -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])"` → `0` (matches placeholder `[project.version] = "0"`). uv emitted warning that `--no-sync` is redundant with `--no-project` → dropped `--no-sync` from the workflow.
- SHA cross-reference: all three SHAs (`34e1148…`, `dd310ad…`, `caf0cab…`) appear in both `publish.yml` and `dependency-update.yml` (Task 3.4 grep canary).
- AC7 credential grep canary: `grep -E 'PYPI_TOKEN|PYPI_API_TOKEN|TWINE_USERNAME|TWINE_PASSWORD|secrets\.PYPI_|--token|--username|--password' .github/workflows/publish.yml` → no matches.
- Source-tree drift check: `git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md` → empty (AC11). `git diff HEAD -- .github/workflows/ci.yml .github/workflows/dependency-update.yml` → empty (AC13).
- Regression suite (Python 3.13): `just test` → 425 passed in 1.16s (matches Story 4.1 baseline byte-exact).
- Coverage gates: `just test-branch-strategies` (26/26, 100% branch on `branch_prefix`); `just test-cc-strategies` (44/44, 100% branch on `conventional_commits`); `just test-doctor` (56/56, 100% branch on `doctor`).
- `uv run ty check` → clean. `just lint-ci` → clean (eof-fixer, ruff format, ruff check, ty check).
- `uv build` → `dist/semvertag-0.tar.gz` + `dist/semvertag-0-py3-none-any.whl` built; pre-existing `uv_build` unbounded-version warning is `_bmad/deferred-work.md §1-1` template-inherited item, out of scope per Constraint 1.
- sdist source-exclude inspection: `tar -tzf dist/semvertag-0.tar.gz | grep -E '_autosemver_reference|_bmad|docs/|site/'` → empty. `uv_build` default excludes already keep the sdist clean of `_autosemver_reference/`, `_bmad/`, `docs/`, `site/`. Closes `_bmad/deferred-work.md §1-1` line 21 ("`[tool.uv.build-backend]` declares no sdist `source-exclude`") — to be recorded in deferred-work post-review per Task 11.2.
- `uv run --with-requirements docs/requirements.txt -- mkdocs build --strict` → built in 0.15s, no warnings/errors against the new `docs/contributing/release.md` + nav addition.

### Completion Notes List

- **AC1 (publish.yml exists with `release: published` trigger)** — verified: new `publish.yml:1-19` declares `on: release: types: [published]` and `workflow_dispatch:` with a single required `tag` input. No `push:`, no `pull_request:`, no `schedule:`.
- **AC2 (top-level shape: permissions, environment, concurrency, timeout)** — verified: `permissions: id-token: write + contents: read` at workflow level (`publish.yml:13-15`); `environment: { name: pypi, url: ... }` at **job** level (`publish.yml:33-35`); `concurrency: publish-${{ github.event.release.tag_name || inputs.tag }}` with `cancel-in-progress: false` (`publish.yml:17-19`); `timeout-minutes: 15` (`publish.yml:32`).
- **AC3 (SHA-pinning + architectural pins)** — verified: `actions/checkout@34e1148…  # v4`, `extractions/setup-just@dd310ad…  # v2`, `astral-sh/setup-uv@caf0cab…  # v3` — SHAs all match `dependency-update.yml`'s vetted set verbatim (Task 3.4 grep confirms each appears in both workflows ≥2×). SHA-pin justification comment block added at top of `jobs:` mirroring `dependency-update.yml:23-27`. No third-party publish action introduced.
- **AC4 (pre-publish tag-vs-`[project.version]` guard)** — verified: `id: tag_guard` step `publish.yml:45-78` resolves effective tag from `release`/`workflow_dispatch` event with an explicit-allowlist + fail-loud (Story 4.1 routing-pattern carry-forward); strips leading `v`; asserts SemVer 2.0 form via the tightened `(0|[1-9][0-9]*)` regex; reads `[project.version]` via stdlib `tomllib` over `uv run --no-project python -c` (no venv sync); fails fast on mismatch with a `::error::` message that names both values and the resolution path. **Deviation from spec literal** documented at Task 4.2: AC4 narrative regex `^[0-9]+\.[0-9]+\.[0-9]+(?:-.+)?$` and Task 4.1's heredoc regex both fail Task 4.2's verification cases for `01.0.0` rejection. Implementation uses the SemVer-2.0-correct regex; behavior matches Task 4.2 verification + AC4 narrative description ("SemVer 2.0 form").
- **AC5 (build step)** — verified: single-line `uv build` step (`publish.yml:80-81`). No `rm -rf dist` (runner is fresh); no `just publish` recipe (Constraint 6); no `python -m build` / `twine`.
- **AC6 (publish step via trusted publishing)** — verified: single-line `uv publish` step (`publish.yml:83-84`). No `--token`, no `--username`, no `--password`, no env credential, no third-party action wrapper. `pyproject.toml` unchanged (no `[tool.uv] trusted-publishing = "always"` key added — Constraint 7 + AC6 explicit).
- **AC7 (zero credential references)** — verified via grep canary: `grep -E 'PYPI_TOKEN|PYPI_API_TOKEN|TWINE_USERNAME|TWINE_PASSWORD|secrets\.PYPI_|--token|--username|--password' .github/workflows/publish.yml` returns no matches. `secrets.GITHUB_TOKEN` is not referenced anywhere (the OIDC token is implicit from `permissions: id-token: write`).
- **AC8 (release runbook)** — verified: new `docs/contributing/release.md` (135 lines) ships sections: "One-time setup (already done; documented for posterity)", "Cutting a release (≤5 minutes from merged PR to PyPI artifact live)", "v1.0 (and any subsequent major) pre-release gate", "Manual / emergency re-runs", "Troubleshooting".
- **AC9 (mkdocs nav)** — verified: `mkdocs.yml` `nav:` gained the 3-line `Contributing → Release runbook: contributing/release.md` entry; theme, palette, markdown_extensions, extra blocks all preserved byte-identical; `mkdocs build --strict` exits 0.
- **AC10 (PyPI trusted-publisher setup documented)** — verified: runbook "One-time setup" section names all four required fields (Owner = `<org>`, Repository = `semvertag`, Workflow filename = `publish.yml`, Environment name = `pypi`) plus the GitHub-side Environment + recommended required-reviewers gate. No GitHub Action attempts to provision the trusted publisher — manual web-UI setup per epic AC2 (`epics.md:736`).
- **AC11 (no source/test/pyproject/Justfile/README/ci.yml/dependency-update.yml changes)** — verified: `git diff HEAD -- semvertag/ tests/ pyproject.toml Justfile README.md .github/workflows/ci.yml .github/workflows/dependency-update.yml` returns empty.
- **AC12 (local YAML validation + lint-ci)** — verified via the `yaml.safe_load` fallback path that AC12 explicitly permits when `actionlint` is unavailable (Story 4.1 precedent). `just lint-ci` clean. `mkdocs build --strict` clean.
- **AC13 (existing workflows preserved byte-identical)** — verified: `ci.yml` and `dependency-update.yml` empty diff; `pyproject.toml`, `Justfile`, `README.md` empty diff (subset of AC11).
- **AC14 (green CI run on PR)** — N/A locally; gates pass on local mirrors (`just lint-ci`, `just test` → 425 pass, `just test-branch-strategies/cc-strategies/doctor` 100% branch, `uv run ty check`, `uv build`, `mkdocs build --strict`). On-PR CI verification is the maintainer's job at land time. **AC14 worked-example correction:** the spec's `inputs.tag: "0"` smoke example is broken under the tightened SemVer regex (the placeholder `[project.version] = "0"` is not a valid SemVer-2.0 tag, so the regex rejects at step 3 of the guard before the comparison step). The dispatch smoke still demonstrates the guard works — it correctly refuses to publish. For a comparison-step smoke, use `inputs.tag: "0.0.0"` instead; the comparison step will reject because `0.0.0` ≠ `0`. Either path validates the guard end-to-end without proceeding to the publish step.
- **Closes `_bmad/deferred-work.md §1-1` line 21** (sdist source-exclude): `uv_build`'s default excludes already keep the sdist clean of `_autosemver_reference/`, `_bmad/`, `docs/`, `site/`. Verified via `tar -tzf dist/semvertag-0.tar.gz | grep -E '...'` → empty. To be recorded post-review in Task 11.2.
- **Open questions / assumptions** (carry to code-review):
  - OQ1 (`release: published` vs `released`) — assumption preserved per spec verbatim wording.
  - OQ2 (`actions/checkout@v4` vs canonical `@v6`) — preserved per architecture pinning discipline; carries forward Story 4.1 OQ3 (architecture-amendment territory).
  - OQ3 (`uv python install 3.13` vs `3.10` floor) — implementation: 3.13 per uv canonical workflow + latest test cell parity.
  - OQ4 (`pyproject.toml` ships `"0"` placeholder) — implementation: not bumped per AC11; the tightened guard now refuses every release until `[project.version]` is bumped to a real SemVer value.
  - OQ5 (build-artifact smoke test deferred) — confirmed deferred; flag for follow-up if reviewer requests.
  - OQ6 (PEP 740 attestations: accept default) — confirmed; uv's default upload-if-found behavior preserved; no attestation generation in this story.
  - OQ7 (trusted publisher uses environment `pypi`) — implementation: included per uv canonical workflow + required-reviewers UX win.
  - OQ8 (`_redact.py` collision with version strings) — N/A; workflow does not invoke semvertag's Python redaction layer.
  - OQ9 (`workflow_dispatch` reviewer gate) — out of scope (Repo Settings → Environment config; documented in runbook).
  - OQ10 (`[tool.uv] trusted-publishing = "always"`) — not added per Constraint 1; defer to a `pyproject.toml`-touching follow-up story.
  - **NEW OQ11 — Tightened SemVer regex deviates from spec literal.** The AC4 narrative regex and Task 4.1 heredoc regex both accept `01.0.0` / `0` and lack the `+build` branch. Implementation uses the SemVer-2.0-correct regex per Task 4.2's verification cases. If a reviewer prefers byte-strict spec adherence, the alternative is amending Task 4.2's verification to remove the `01.0.0` rejection requirement (regression-causing — `01.0.0` is not valid SemVer). Recommend keeping the implementation regex and flagging the spec mismatch as resolved by tightening rather than loosening.
  - **NEW OQ12 — `workflow_dispatch` `tag` input is `required: true`.** This forces a maintainer to type a tag even for an emergency re-run, but means a dispatch can't accidentally proceed with an empty tag. Trade-off accepted; flag if reviewer wants `required: false` + a default derivation step.

### File List

<!-- Fill at land time. -->

| File | Action | Notes |
|---|---|---|
| `.github/workflows/publish.yml` | NEW | 84 lines. `release: published` + `workflow_dispatch (tag)` triggers; `permissions: id-token: write + contents: read`; per-tag `concurrency` group; `environment: pypi` job-level with informational `url:`; SHA-pinned `actions/checkout@34e1148`, `extractions/setup-just@dd310ad`, `astral-sh/setup-uv@caf0cab` (matching `dependency-update.yml`'s vetted set); `uv python install 3.13`; pre-publish `tag_guard` step (event-allowlist + leading-`v` strip + SemVer-2.0 regex + `tomllib`-based `[project.version]` read + byte-equal compare); `uv build`; `uv publish`. |
| `docs/contributing/release.md` | NEW | 135 lines. Sections: One-time setup (PyPI + GitHub Environment), Cutting a release ≤5min, v1.0+ pre-release gate (NFR9 + Story 4.8), Manual / emergency re-runs (`workflow_dispatch`), Troubleshooting (5 failure modes). `<org>` placeholder preserved. |
| `mkdocs.yml` | UPDATE | 3-line `Contributing → Release runbook: contributing/release.md` nav addition. Theme, palette, markdown_extensions, extra all preserved byte-identical. |
| `_bmad/sprint-status.yaml` | UPDATE | `4-2-publish-workflow-via-trusted-publishing: ready-for-dev → in-progress → review`; `last_updated: 2026-05-30`; `last_updated_note` refreshed with dev-cycle summary. |
| `_bmad/4-2-publish-workflow-via-trusted-publishing.md` (this file) | UPDATE | Status `ready-for-dev → review`; Tasks 1-10 all checked; Task 11 intentionally left unchecked (post-review gate); Dev Agent Record (Agent Model, Debug Log, Completion Notes, File List, Change Log) filled. |
| `_bmad/deferred-work.md` | NO-CHANGE | Task 11 is post-review; deferred to code-review-time per spec. |
| `semvertag/**/*.py` | NO-CHANGE | Explicitly forbidden per Constraint 1. Verified empty diff (AC11). |
| `tests/**/*.py` | NO-CHANGE | Explicitly forbidden per Constraint 1. Verified empty diff (AC11). |
| `pyproject.toml` | NO-CHANGE | Constraint 1 + AC11 + Constraint 7 (no `[tool.uv]` key). Verified empty diff. |
| `Justfile` | NO-CHANGE | Constraint 1 + Constraint 6 (no `publish` recipe). Verified empty diff. |
| `.github/workflows/ci.yml` | NO-CHANGE | AC13 byte-identical preservation. Verified empty diff. |
| `.github/workflows/dependency-update.yml` | NO-CHANGE | AC13 byte-identical preservation. Verified empty diff. |
| `README.md` | NO-CHANGE | Story 4.7 owns README hero. Verified empty diff. |

### Change Log

- 2026-05-30 — Created `.github/workflows/publish.yml`: `release: published` + `workflow_dispatch (required tag input)` triggers; `permissions: id-token: write + contents: read`; per-tag `concurrency` group with `cancel-in-progress: false`; `environment: pypi` job-level with informational `url:`; SHA-pinned `actions/checkout@34e1148`, `extractions/setup-just@dd310ad`, `astral-sh/setup-uv@caf0cab` (matching `dependency-update.yml`'s vetted set verbatim); `uv python install 3.13`; pre-publish `tag_guard` step (event-allowlist + leading-`v` strip + SemVer-2.0 regex + `tomllib`-based `[project.version]` read + byte-equal compare); `uv build`; `uv publish` (no `--token`, no env credentials). [AC1, AC2, AC3, AC4, AC5, AC6, AC7]
- 2026-05-30 — Created `docs/contributing/release.md` (135 lines): one-time PyPI trusted-publisher setup (Owner / Repo / Workflow / Environment); cutting-a-release ≤5min flow; v1.0+ pre-release Story 4.8 shadow-mode gate (NFR9); manual / emergency `workflow_dispatch` flow; 5-section troubleshooting. `<org>` placeholder preserved per pre-launch convention. [AC8, AC10]
- 2026-05-30 — Updated `mkdocs.yml` nav: 3-line `Contributing → Release runbook` entry added; theme, palette, markdown_extensions, extra blocks preserved byte-identical. [AC9]
- 2026-05-30 — **Tightened tag-guard regex from spec literal.** AC4 narrative regex `^[0-9]+\.[0-9]+\.[0-9]+(?:-.+)?$` and Task 4.1 heredoc regex both accept `01.0.0` (leading zero), `0` (no dots), and lack the `+build` branch — failing Task 4.2's verification cases. Implementation uses the SemVer-2.0-correct `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$`. Behavior matches AC4 narrative description ("SemVer 2.0 form") and Task 4.2 verification cases; flagged in NEW OQ11 for code-review confirmation.
- 2026-05-30 — Dropped redundant `--no-sync` flag from the tag-guard's `uv run` invocation per uv warning ("`--no-sync` has no effect when used alongside `--no-project`"). Functionally identical; quiets the runtime warning.
- 2026-05-30 — Verified zero changes to `semvertag/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Justfile`, `README.md`, `.github/workflows/ci.yml`, `.github/workflows/dependency-update.yml` via `git diff HEAD`. [AC11, AC13]
- 2026-05-30 — Local validation gates: `yaml.safe_load` clean on `publish.yml`; `just lint-ci` clean; `mkdocs build --strict` clean (0.15s build); `just test` → 425 passed in 1.16s; `just test-branch-strategies` (26/26, 100% branch); `just test-cc-strategies` (44/44, 100% branch); `just test-doctor` (56/56, 100% branch); `uv run ty check` clean; `uv build` clean (sdist + wheel). [AC12, AC14 readiness]
- 2026-05-30 — AC7 grep canary clean: no `PYPI_TOKEN` / `PYPI_API_TOKEN` / `TWINE_USERNAME` / `TWINE_PASSWORD` / `secrets.PYPI_` / `--token` / `--username` / `--password` substrings in `publish.yml`.
- 2026-05-30 — sdist source-exclude inspection: `uv_build`'s default excludes already keep the sdist clean of `_autosemver_reference/`, `_bmad/`, `docs/`, `site/`. Closes `_bmad/deferred-work.md §1-1` line 21 ("Revisit at first PyPI publish (Story 4.2)") — to be recorded in deferred-work post-review per Task 11.2.
- 2026-05-30 — Sprint status: `4-2-publish-workflow-via-trusted-publishing` ready-for-dev → in-progress → review.
- 2026-05-30 — **Maintainer follow-up (post-merge)**: (a) configure PyPI trusted publisher per runbook (Owner / Repo / Workflow / Environment); (b) create GitHub Environment `pypi` with optional required-reviewers; (c) plan the first release-prep PR that bumps `[project.version]` from `"0"` to a real SemVer-2.0 value per OQ4.
