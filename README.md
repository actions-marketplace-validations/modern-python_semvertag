# semvertag

[![CI](https://github.com/modern-python/semvertag/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/semvertag/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/modern-python/semvertag/branch/main/graph/badge.svg)](https://codecov.io/gh/modern-python/semvertag)

Auto-tag your GitLab or GitHub repository with semantic version tags from CI — one tool, two strategies, two providers.

## Install

```sh
uvx semvertag tag
```

## Use it in GitLab CI

Paste this job into your `.gitlab-ci.yml`:

```yaml
stages: [tag]

semvertag:
  stage: tag
  image: python:3.13-slim
  variables:
    SEMVERTAG_STRATEGY: branch-prefix  # or: conventional-commits
  before_script:
    - pip install --quiet 'uv>=0.4,<1'
  script:
    - uvx 'semvertag>=0.5.0,<1' tag
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
```

It runs `uvx semvertag tag` against your repo on the default branch.
semvertag inspects the latest commit + tag history, decides the
appropriate semver bump, and creates the new tag via the GitLab API.

> A one-line `include: - component: …` via the GitLab CI Catalog will
> replace this snippet once the component is published. For now, paste
> the job inline.

## Use it in GitHub Actions

Paste this workflow into `.github/workflows/semvertag.yml`:

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
      - uses: modern-python/semvertag@v0
```

semvertag auto-detects GitHub Actions, picks the bump from the latest
commit, and creates the tag ref via the GitHub API. `fetch-depth: 0`
matters — the default `1` misses tag-relative history. See
[GitHub Actions docs](docs/providers/github.md) for token scopes,
GitHub Enterprise setup, outputs, and troubleshooting.

## Strategies

- **branch-prefix** (default): the latest commit on the default branch
  must be a merge commit whose source branch starts with `feature/`
  (minor), `bugfix/`, or `hotfix/` (patch).
- **conventional-commits**: parses the latest commit's
  [Conventional Commits](https://www.conventionalcommits.org/)
  header (`feat:` minor, `fix:`/`perf:` patch, `!` or `BREAKING
  CHANGE:` major).

Both are configurable via env vars. See [docs](https://semvertag.modern-python.org)
for the full configuration surface.

## License

MIT
