# semvertag

[![CI](https://github.com/modern-python/semvertag/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/semvertag/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/modern-python/semvertag/branch/main/graph/badge.svg)](https://codecov.io/gh/modern-python/semvertag)

Auto-tag your GitLab repository with semantic version tags from CI — one tool, two strategies.

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
    - uvx 'semvertag>=0.1,<1' tag
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
```

It runs `uvx semvertag tag` against your repo on the default branch.
semvertag inspects the latest commit + tag history, decides the
appropriate semver bump, and creates the new tag via the GitLab API.

> A one-line `include: - component: …` via the GitLab CI Catalog will
> replace this snippet once the component is published. For now, paste
> the job inline.

## Strategies

- **branch-prefix** (default): the latest commit on the default branch
  must be a merge commit whose source branch starts with `feature/`
  (minor), `bugfix/`, or `hotfix/` (patch).
- **conventional-commits**: parses the latest commit's
  [Conventional Commits](https://www.conventionalcommits.org/)
  header (`feat:` minor, `fix:`/`perf:` patch, `!` or `BREAKING
  CHANGE:` major).

Both are configurable via env vars. See [docs](https://semvertag.readthedocs.io)
for the full configuration surface.

## License

MIT
