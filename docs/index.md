# semvertag

Auto-tag your GitLab repository with semantic version tags from CI —
one tool, two strategies.

semvertag reads the latest commit and tag history from your GitLab
project via the API, decides the appropriate semver bump based on the
strategy you've configured, and creates the new git tag — all from a
single command in your CI pipeline.

## Quick start

The recommended way to use semvertag in CI is via the
[GitLab CI Catalog component](providers/gitlab.md):

```yaml
include:
  - component: gitlab.com/modern-python/semvertag/semvertag@v0.1.0
    inputs:
      strategy: branch-prefix  # or: conventional-commits
```

For local testing or one-off invocations:

```sh
SEMVERTAG_TOKEN=<your-gitlab-token> \
SEMVERTAG_PROJECT_ID=<your-project-id> \
  uvx semvertag tag
```

## Strategies

semvertag ships with two bump-decision strategies:

- [**branch-prefix**](strategies/branch-prefix.md) — bump based on the
  source branch of the latest merge commit (`feature/` → minor,
  `bugfix/` / `hotfix/` → patch). The default.
- [**conventional-commits**](strategies/conventional-commits.md) —
  bump based on the latest commit's Conventional Commits header
  (`feat:` → minor, `fix:` / `perf:` → patch, `!` or
  `BREAKING CHANGE:` → major).

Both strategies are configurable via environment variables — see the
strategy pages for the full configuration surface.

## Contributing

- [Release runbook](contributing/release.md) — for maintainers cutting
  a new release of semvertag itself.
