# Release runbook

This document describes how to cut a new `semvertag` release to PyPI via the
trusted-publishing pipeline at `.github/workflows/publish.yml`. The pipeline
exchanges a GitHub OIDC token with PyPI — there is no long-lived `PYPI_TOKEN`
in the repo's secrets, and no maintainer needs PyPI credentials on a laptop
to ship a release (NFR13).

## One-time setup (already done; documented for posterity)

> **Note:** Replace `<org>` below with the actual GitHub organization or user
> name that owns this repository. The literal string `<org>` will not match
> PyPI's OIDC subject claim and the first publish will fail.

The trusted-publisher binding between this repo and PyPI is configured once,
before the first release. If this is being repeated (account migration, fork,
or recovery), all four fields below MUST match the workflow exactly.

- **PyPI side:** project page → Publishing → Add a trusted publisher
  - Owner: `<org>`
  - Repository: `semvertag`
  - Workflow filename: `publish.yml`
  - Environment name: `pypi`

- **GitHub side:** Settings → Environments → New environment, name: `pypi`
  - Recommended for v1.0 and beyond: enable **required reviewers** so the
    publish step waits for a human "Approve" before deploying to the `pypi`
    environment. The OIDC token is only issued after approval, which adds a
    human gate on top of the tag-guard step.
  - No environment secrets are required — trusted publishing does not use any.

## Cutting a release (≤5 minutes, target NFR13 + 5-min-from-merge-to-PyPI)

> The ≤5min budget covers the automated path (release-prep PR merge →
> `publish.yml` finishes uploading to PyPI). It does **not** include any
> human-approval wait when the `pypi` Environment is configured with
> required reviewers — that gate is unbounded and unaffected by this SLO.

1. Land all PRs intended for the release on `main`. Verify CI is green
   (`lint`, `pytest` matrix, `pip-audit`).
2. Open a release-prep PR that:
   - Bumps `[project.version]` in `pyproject.toml` to the target SemVer 2.0
     value (e.g. `0.1.0`, `1.0.0`). Leading-zero numerics (e.g. `01.0.0`)
     are rejected by the publish workflow's tag guard. **This bump is
     required for every release**, including the second release onward —
     `[project.version]` on `main` between releases reflects the most
     recently released version, so a missed bump will tag against the
     previous version and the guard will refuse to publish.
   - Adds a one-line release note to the GitHub release body when drafting
     the release (Story 4.6 will introduce `CHANGELOG.md`; this step expands
     when 4.6 lands).
3. Merge the release-prep PR.
4. On GitHub → Releases → **Draft a new release**:
   - Tag: `v<X.Y.Z>` (must match `[project.version]` byte-equal after
     stripping the leading `v`).
   - Title: `v<X.Y.Z>`.
   - Body: one-line release note (until `CHANGELOG.md` lands via Story 4.6),
     or use GitHub's auto-generated notes.
   - Click **Publish release**.
5. The `publish.yml` workflow auto-fires on `release: published`:
   - Verifies the release tag matches `[project.version]` (refuses to publish
     on any mismatch — see Troubleshooting below).
   - Runs `uv build` → produces wheel + sdist in `dist/`.
   - Runs `uv publish` → uv detects the GitHub Actions OIDC environment,
     exchanges the token with PyPI, and uploads the wheel + sdist (plus any
     PEP 740 attestations found alongside the dist files).
6. Verify on <https://pypi.org/project/semvertag/> that the new version is
   listed and the wheel + sdist are downloadable.

## v1.0 (and any subsequent major) pre-release gate

**Do not release v1.0 or any subsequent major release without first:**

- Re-running Story 4.8's shadow-mode parity validation against
  `raif-autosemver` in `pypelines` for the current `main` HEAD: ≥2 weeks,
  100% byte-identical tag outcomes per **NFR9**.
- Recording the parity sign-off in the GitHub release notes (or linking from
  them to a permanent gist / release-asset artifact).

This gate is non-negotiable per the Epic 4 spec for Story 4.2 and PRD NFR9.
A release that cannot demonstrate the parity sign-off MUST be blocked.

## Manual / emergency re-runs

The `publish.yml` workflow also accepts a `workflow_dispatch` event with a
single input, `tag`, used in lieu of `github.event.release.tag_name` for the
version-guard check. This is intentionally narrow:

- Use it to re-run a publish that failed at the upload step (e.g. transient
  PyPI 503) without recreating the GitHub release.
- Do NOT use it for first-time publishes — go through the GitHub Release UI
  so the tag, release notes, and changelog all land at the same git commit.

## Troubleshooting

- **"Release tag (X) does not match pyproject.toml [project.version] (Y)"** —
  the tag-guard step caught a mismatch. Resolve by either:
  1. Bumping `[project.version]` in a follow-up PR and re-cutting the tag, or
  2. Deleting the GitHub release + tag and recreating with the matching tag.

  Do NOT edit the tag without bumping `[project.version]` to match — the next
  release will have the same problem and the released artifact will disagree
  with `main`'s `pyproject.toml`.

- **"Effective tag 'X' is not strict SemVer 2.0"** — the tag doesn't match
  the guard's regex (`MAJOR.MINOR.PATCH` with optional dot-separated
  `-prerelease` and `+build` identifiers per SemVer §9/§10; no leading zeros
  in any numeric identifier; no empty identifiers). Examples that fail:
  `1.0`, `01.0.0`, `1.0.0-`, `1.0.0+`, `1.0.0-01`, `1.0.0-foo..bar`.
  Examples that pass: `1.0.0`, `0.1.0`.

  > **Caveat for pre-release / build-metadata tags:** the guard validates
  > SemVer 2.0, but PyPI enforces PEP 440. SemVer-valid forms like
  > `1.0.0-rc.1` and `1.0.0+build.123` will pass the guard and then be
  > rejected by `uv build` (PEP 440 normalization) or `uv publish` (PyPI
  > rejects `+local` versions on public uploads). Until the workflow's tag
  > language is aligned to PEP 440, stick to plain `MAJOR.MINOR.PATCH` tags
  > for every release.

- **OIDC token exchange fails on `uv publish`** — usually a setup mismatch.
  Verify on PyPI: Owner = `<org>`, Repository = `semvertag`, Workflow
  filename = `publish.yml`, Environment name = `pypi`. All four MUST match
  the workflow byte-equal. If any differs, the OIDC subject claim won't
  match PyPI's binding and the token exchange is refused.

- **PyPI rejects attestations** — workaround: temporarily add
  `--no-attestations` to the `uv publish` invocation in `publish.yml`. This
  is an emergency lever, not a default; the underlying attestation rejection
  is a PyPI-side regression that should be reported upstream.

- **`uv publish` fails partway (e.g. sdist uploaded, wheel did not)** — PyPI
  rejects re-upload of an already-uploaded filename, even byte-identical.
  A `workflow_dispatch` retry of the same tag will hit HTTP 400 on the
  already-present sdist. Recovery: bump `[project.version]` to the next
  patch number (e.g. `1.0.0` → `1.0.1`) in a fresh release-prep PR and
  re-cut the tag. Do NOT delete the partial PyPI artifact — PyPI does not
  permit re-uploading the same version even after deletion.

- **First-release `[project.version] = "0"`** — the project ships with a
  placeholder version `"0"`. No SemVer-2.0 tag can match `"0"` (the
  guard's regex requires `MAJOR.MINOR.PATCH`), so the publish workflow
  refuses every release against the placeholder. The release-prep PR for
  the first release MUST bump `[project.version]` to a real SemVer value
  (e.g. `0.1.0`).

- **"Trusted publisher not configured"** from PyPI — the one-time setup at
  the top of this document hasn't been done, or the PyPI project doesn't
  yet exist. The first publish creates the PyPI project record; before that
  point the trusted-publisher config can be set up as a "pending publisher"
  (PyPI → Your Projects → Publishing → Add a pending publisher). Once the
  first publish lands, the binding becomes a regular trusted publisher.
