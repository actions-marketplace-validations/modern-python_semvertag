# GitHub Actions

Use semvertag in GitHub Actions via the [Marketplace
action](https://github.com/marketplace/actions/semvertag). The action is a
thin composite wrapper around the `semvertag` CLI — it installs `uv`, then
runs `uvx semvertag` with the workflow-issued `GITHUB_TOKEN` and your chosen
strategy. No PyPI install in your repo, no maintained workflow YAML beyond
the seven lines below.

## Quick Start (7 lines)

The minimum useful workflow: auto-tag on every push to `main`.

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

> Replace `<org>` with the actual GitHub organization or user that owns the
> semvertag repository. The literal string `<org>` will not resolve to a
> valid action and the workflow will fail at `uses:` resolution.

The action runs against the commit that just landed on `main` and, if a bump
is warranted by the configured strategy, pushes a new tag to `origin`. If no
bump is warranted, the action exits 0 without pushing a tag.

## Inputs

The action accepts two optional inputs. Both have defaults that match what
most consumers want; you can omit the `with:` block entirely for the
default behavior.

| Input | Required | Default | Description |
|---|---|---|---|
| `strategy` | no | `branch-prefix` | Bump strategy. One of `branch-prefix` or `conventional-commits`. |
| `token` | no | `${{ github.token }}` | GitHub token with `contents: write` scope. Defaults to the workflow-issued token. |

The input names, defaults, and descriptions are sourced from
[`action.yml`](https://github.com/<org>/semvertag/blob/main/action.yml) — if
this table ever drifts from the action file, the action file wins.

## Required permissions

The action pushes a tag, so the job that runs it MUST have `contents: write`
permission. The default workflow token (`GITHUB_TOKEN`) is read-only unless
you opt in explicitly:

```yaml
permissions:
  contents: write
```

Omitting this is the most common first-run failure. The CLI surfaces it as:

```
Token missing 'contents: write' permission.
```

Add the block at either the job level (recommended; narrower blast radius)
or the workflow level. No other permissions are required.

## Token scope: pushing tags from PRs vs main

The default `${{ github.token }}` works for the common path — pushing a tag
from a job triggered by `push: branches: [main]`. Two cases where it does
not work, and how to mitigate:

- **Pushing to a protected branch.** Some org configurations prevent the
  default token from bypassing branch-protection rules even with
  `contents: write`. Use a [GitHub App token](https://docs.github.com/en/apps/creating-github-apps)
  or a Personal Access Token (PAT) stored in repo secrets, passed via
  `with: token:`.
- **Pull-request workflows.** The default token in a `pull_request:` event
  is intentionally restricted — it cannot push to the upstream repo, only
  to the PR's own fork. Auto-tagging from a PR therefore does not work with
  the default token; use a `push:` trigger on `main` instead, or use a PAT
  via `with: token:` if you genuinely need to tag at PR time.

For most consumers, the `push: branches: [main]` pattern with the default
token is the simplest correct setup.

## Branch-prefix vs conventional-commits

Pick `branch-prefix` if your team merges PRs with branch names that follow
a `fix/...`, `feat/...`, `chore/...` convention. The action reads the most
recent merge commit's source-branch prefix and bumps accordingly — `fix/`
bumps patch, `feat/` bumps minor, `chore/` bumps nothing. This is the
default. A dedicated per-strategy explainer page ships in a later docs
story.

Pick `conventional-commits` if your team writes
[Conventional Commits](https://www.conventionalcommits.org/) messages
directly on `main` (e.g. `feat: add X`, `fix: handle Y`, `feat!: drop Z`).
The action scans commits since the last tag and chooses the highest bump
implied by their type prefixes (`feat!` or `BREAKING CHANGE:` → major,
`feat:` → minor, `fix:` → patch, everything else → none).

Set the strategy per repo:

```yaml
- uses: <org>/semvertag@v1
  with:
    strategy: conventional-commits
```

## Troubleshooting

- **"GitHub provider not implemented yet"** — at v1.0, semvertag's GitHub
  provider is a stub. The Marketplace action exists for distribution and
  the composite wraps `uvx semvertag` correctly, but the underlying CLI's
  GitHub provider is scheduled for a v1.x release. Until then, the
  Marketplace action runs against a not-yet-functional provider and the
  CLI exits non-zero with this message. Track the GitHub provider story in
  the project's epic list.

- **"No tags found; refusing to bump from sentinel"** — the checkout step
  is the most common cause. The default `actions/checkout@v4` uses
  `fetch-depth: 1` and does not fetch tags, so semvertag sees an empty
  tag history. Add `fetch-depth: 0` and `fetch-tags: true` to the checkout
  step (the Quick Start snippet already does this).

- **"Detached HEAD; no current branch"** on a `release: published` trigger
  — release events check out the release tag's commit, which is a detached
  HEAD. The branch-prefix strategy needs a current branch name to read the
  merge-commit source; switch the trigger to `push: branches: [main]` or
  use `conventional-commits` instead.

- **`uses: <org>/semvertag@v1` fails to resolve** — `<org>` is a literal
  placeholder in this documentation. Replace it with the actual GitHub
  organization or user name that owns the semvertag repo (see the Quick
  Start callout). The Marketplace listing's `uses:` line will show the
  resolved org once the first release is published.
