# Conventional Commits strategy

The `conventional-commits` strategy parses each commit's subject line
against the
[Conventional Commits](https://www.conventionalcommits.org/) grammar
and decides a per-commit bump. The orchestrator combines per-commit
bumps across the commit range and applies the highest one to the
release.

## Default type-to-bump mapping

| Commit marker | Bump |
|---|---|
| `BREAKING CHANGE:` or `BREAKING-CHANGE:` in commit body | major |
| `!` suffix on the type (e.g. `feat!:`, `fix!:`, `refactor!:`) | major |
| `feat:` (or `feat(scope):`) | minor |
| `fix:` (or `fix(scope):`), `perf:` (or `perf(scope):`) | patch |
| Any other type (`chore`, `docs`, `refactor`, `style`, `test`, `build`, `ci`, `revert`, ...) | none |
| Commits whose subject does not match the type-grammar at all | none |

The grammar checked is `^(type)(?:\((scope)\))?(!)?:`. Anything not
matching this pattern returns `none`. The `!` marker takes precedence
over the type — `chore!:` is a major bump even though `chore` is
otherwise unmapped.

## Customizing the type lists

The strategy reads its type lists from the application's settings
layer:

- `minor_types` — tuple of types that trigger a minor bump (default
  `("feat",)`).
- `patch_types` — tuple of types that trigger a patch bump (default
  `("fix", "perf")`).

Both lists are validated against the lowercase-letters-only regex
`^[a-z]+$`. Major bumps come from `BREAKING CHANGE:` / `!` markers
only and are not configurable.

## Commit scanning

The strategy decides a bump per-commit; the orchestrator scans the
commit range and takes the highest bump across all commits. One
`feat!:` (or `BREAKING CHANGE:` body) anywhere in the range promotes
the release to major even if every other commit is a patch.

Merge commits are scanned the same as any other commit — their
subject is matched against the type grammar. If your merge commits do
not follow Conventional Commits format (e.g. default `Merge branch
'foo' into main` subjects), they contribute `none` and the bump is
decided by the merged commits' types.

## When to pick a different strategy

If your team merges via short-lived prefixed branches (`feature/...`,
`bugfix/...`) and does not enforce Conventional Commits on each
commit, switch to [Branch prefix](branch-prefix.md) — it reads the
merge commit's source branch rather than the per-commit subject.

## Consumer integration

The strategy is selected per project via the `strategy:` input on the
relevant provider's component / action. See:

- [GitLab CI](../providers/gitlab.md) — set
  `strategy: conventional-commits` on the `include: - component:` block.
- [GitHub Actions](../providers/github.md) — set
  `strategy: conventional-commits` on the marketplace action's `with:`
  block.
