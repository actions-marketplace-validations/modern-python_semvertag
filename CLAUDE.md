# semvertag — Claude project guide

## Workflow

This project uses **Superpowers** (brainstorm → plan → TDD → review).

- Brainstorm specs live in `planning/specs/YYYY-MM-DD-<topic>-design.md`.
- Implementation plans live in `planning/plans/YYYY-MM-DD-<topic>.md`.
- Use TDD by default: red, green, refactor. Tests before implementation.
- Use git worktrees for feature isolation (`superpowers:using-git-worktrees`).
- Use the verification gate before claiming work complete
  (`superpowers:verification-before-completion`).
- Request code review via a subagent before landing
  (`superpowers:requesting-code-review`).

## Commit messages

Imperative present-tense, scoped where helpful:

- `providers: add HttpClient wrapper`
- `docs: update README hero section`
- `fix: handle empty default branch in GitLab provider`

No story-numbered prefixes (`land story X.Y`, `contextualise story X.Y`). Those
belong to the retired BMad workflow.

## Reference directories (do not edit)

- `_archive/bmad/` — retired BMad workspace. Historical specs, PRD,
  architecture, retrospectives, and 14 dense story files. Read for context;
  do not extend, do not delete.
- `_autosemver_reference/` — the original Raiffeisen-internal `autosemver`
  package. Behavioral reference only — port logic and test shapes from it
  but never `git mv` files in or take it as a starter.

## Test stack and lint

See `Justfile` for the canonical commands. Quick reference:

- `just lint-ci` — eof-fixer, ruff format check, ruff check, ty check
- `just test` — pytest with coverage
- `just test-branch` — pytest with branch coverage
- `just test-branch-strategies` / `just test-cc-strategies`
  — 100% branch coverage gates on specific modules
- `mkdocs build --strict` — docs build gate

## What the codebase ships

`semvertag` is a public-OSS auto-tagger for GitLab/GitHub/Bitbucket
repositories. Two strategies (`branch-prefix`, `conventional-commits`), one
provider implemented today (GitLab), distributed as a Python CLI plus a
GitHub Actions wrapper (`action.yml`) and a GitLab CI Catalog component
(`templates/semvertag.yml`).
