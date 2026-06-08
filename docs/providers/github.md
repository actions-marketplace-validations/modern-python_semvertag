# GitHub Actions

Use semvertag in GitHub Actions via a small workflow that installs
`uv` and runs `uvx semvertag tag`. No composite action in your repo,
no maintained workflow YAML beyond the snippet below.

> **GitHub Actions composite wrapper pending.** A one-line
> `uses: modern-python/semvertag@v…` via a published composite
> action is the eventual delivery path — but it has not been
> published. Paste the workflow below into
> `.github/workflows/semvertag.yml` until then.

## Quick Start

The minimum useful workflow: auto-tag on every push to the default
branch.

> **Required setup.** Either rely on the workflow-scoped
> `GITHUB_TOKEN` (which is auto-issued per job and picked up via the
> alias chain) — in which case the workflow MUST declare
> `permissions: contents: write` — OR provide a fine-grained PAT with
> `contents: write` (single repo) or a classic PAT with `repo` /
> `public_repo` scope. Store the PAT as a repo secret named
> `SEMVERTAG_TOKEN`; the alias chain picks it up ahead of
> `GITHUB_TOKEN`.

```yaml
name: semvertag
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
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install --quiet --no-cache-dir 'uv>=0.4,<1'
      - run: uvx 'semvertag>=0.2,<1' tag
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

The job runs against the latest commit on the default branch and, if
a bump is warranted by the configured strategy, creates a new tag
ref via the GitHub API. If no bump is warranted, the job exits 0
without pushing.

> **Auto-detection.** semvertag detects GitHub Actions from the
> `GITHUB_ACTIONS=true` env var that GHA sets automatically. The
> `--provider` flag is therefore optional inside GHA — explicit
> `--provider github` is only needed when running outside GHA (e.g.
> on a developer laptop targeting a github.com repo).

> **`fetch-depth: 0`** matters: semvertag walks commit history to
> determine the bump. `actions/checkout@v4`'s default
> `fetch-depth: 1` only fetches the single tip commit and will miss
> tag-relative history.

## Strategy

Pass `--strategy` (or set `SEMVERTAG_STRATEGY`) to one of:

| Value | Description |
|---|---|
| `branch-prefix` (default) | Bump from the source-branch prefix of the latest merge commit. |
| `conventional-commits` | Bump from Conventional Commits headers since the last tag. |

```yaml
      - run: uvx 'semvertag>=0.2,<1' tag --strategy conventional-commits
```

## Required permissions

The job creates a tag ref, so the token it uses MUST carry write
access to the repository's contents. semvertag reads the token from
these env vars in order:
`SEMVERTAG_GITHUB__TOKEN`, `SEMVERTAG_TOKEN`, `GITHUB_TOKEN`. The
first set value wins.

## Token scope: `GITHUB_TOKEN` vs Personal Access Tokens

Three cases govern which token the job should use:

- **Workflow-scoped `GITHUB_TOKEN`** (preferred for most projects).
  GitHub Actions issues a fresh token per job; it inherits the
  workflow's `permissions:` block. Add `permissions: contents: write`
  at the workflow level (as in the snippet above). The token is
  auto-exported as `GITHUB_TOKEN` and picked up by the alias chain.
- **Fine-grained PAT scoped to the single repository.** Required
  scope: `Contents: Read and write`. Store as a repo secret named
  `SEMVERTAG_TOKEN`; the alias chain picks it up ahead of
  `GITHUB_TOKEN`. Use this when the workflow runs across
  organizations or needs scopes the workflow token can't grant.
- **Classic PAT.** Required scope: `repo` (private repos) or
  `public_repo` (public repos only). Same storage shape as the
  fine-grained PAT. Less preferred — classic PATs bleed scope
  across all of the user's repos.

> **Masking caveat.** Because the alias chain reads
> `SEMVERTAG_GITHUB__TOKEN` → `SEMVERTAG_TOKEN` → `GITHUB_TOKEN` in
> order and the first set value wins, a stale `SEMVERTAG_TOKEN` left
> over from a prior PAT-based setup will silently override the
> workflow's `GITHUB_TOKEN`. If you migrate from PAT →
> workflow-token, unset `SEMVERTAG_TOKEN` from the repo's secrets.

**GitHub Enterprise**: set `SEMVERTAG_GITHUB__ENDPOINT` (note the
double underscore — pydantic-settings uses `__` as the nested-key
delimiter, so `SEMVERTAG_GITHUB_ENDPOINT` with a single underscore is
silently ignored) as a workflow-level env or a repo secret pointing
to the instance's API root, e.g.
`https://github.example.com/api/v3`. The default is
`https://api.github.com`.

For most consumers on `github.com`-hosted repos with the
workflow-scoped `GITHUB_TOKEN`, the minimal workflow snippet above
is the entire setup.

## Branch-prefix vs conventional-commits

Pick `branch-prefix` if your team merges PRs with branch names that
follow a `fix/...`, `feat/...`, `chore/...` convention. semvertag
reads the most recent merge commit's source-branch prefix and bumps
accordingly — `fix/` bumps patch, `feat/` bumps minor, `chore/`
bumps nothing. This is the default. See
[Branch-prefix strategy](../strategies/branch-prefix.md) for the full
prefix-to-bump table and edge-case behavior.

Pick `conventional-commits` if your team writes
[Conventional Commits](https://www.conventionalcommits.org/) messages
directly on the default branch (e.g. `feat: add X`, `fix: handle Y`,
`feat!: drop Z`). semvertag scans commits since the last tag and
chooses the highest bump implied by their type prefixes (`feat!` or
`BREAKING CHANGE:` → major, `feat:` → minor, `fix:` → patch,
everything else → none). See
[Conventional Commits strategy](../strategies/conventional-commits.md)
for the full type-to-bump mapping.

## Troubleshooting

- **`Token rejected: 401. Verify SEMVERTAG_TOKEN is valid.`** — the
  token is malformed, expired, or revoked. Verify in GitHub UI
  (Settings → Developer settings → Personal access tokens) or
  rotate the workflow secret. For workflow-scoped tokens, this
  usually means `GITHUB_TOKEN` was not exported into the step's
  `env:` — add the `env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`
  line shown in the Quick Start.

- **`Token missing scope or insufficient permission: 403`** — the
  token lacks `contents: write` (fine-grained / workflow-scoped) or
  `repo` / `public_repo` (classic). For workflow-scoped tokens,
  add `permissions: contents: write` at the workflow level. For PATs,
  re-issue with the right scope.

- **`GitHub repo not found: repo='...'`** — `GITHUB_REPOSITORY` was
  not exported, or `--repo OWNER/REPO` was not passed. Inside GHA,
  `GITHUB_REPOSITORY` is auto-exported in every job; outside GHA,
  set it explicitly.

- **`Tag already exists: 'v...'`** — a previous run (or a concurrent
  run) already created this tag. semvertag refuses to silently
  succeed on a duplicate. Roll forward by pushing another commit
  that changes the bump, or delete the duplicate tag.

- **GitHub Enterprise, but the job connects to `api.github.com`** —
  the default endpoint is `https://api.github.com`. Set
  `SEMVERTAG_GITHUB__ENDPOINT` (note the double underscore) as a
  workflow-level env pointing to the instance's API root, e.g.
  `https://github.example.com/api/v3`.
