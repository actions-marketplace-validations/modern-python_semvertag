---
validationTarget: 'prd.md'
validationDate: '2026-05-26'
inputDocuments:
  - 'prd.md'
  - 'product-brief-semvertag.md'
  - 'product-brief-semvertag-distillate.md'
validationStepsCompleted: ['step-v-01-discovery', 'step-v-02-format-detection', 'step-v-03-density-validation', 'step-v-04-brief-coverage-validation', 'step-v-05-measurability-validation', 'step-v-06-traceability-validation', 'step-v-07-implementation-leakage-validation', 'step-v-08-domain-compliance-validation', 'step-v-09-project-type-validation', 'step-v-10-smart-validation', 'step-v-11-holistic-quality-validation', 'step-v-12-completeness-validation', 're-validation-pass-2026-05-26-post-touch-ups', 're-validation-pass-2026-05-26-fr13-fr16-tagging']
validationStatus: COMPLETE
holisticQualityRating: '5/5 — Excellent'
overallStatus: Pass
revalidatedAt: '2026-05-26'
revalidationTrigger: '8-item PRD touch-up pass (architecture.md §PRD Touch-Ups Required)'
---

# PRD Validation Report

**PRD Being Validated:** `prd.md` (semvertag Product Requirements Document)
**Validation Date:** 2026-05-26
**Validator:** BMad Validate-PRD workflow

## Input Documents

- `prd.md` — semvertag PRD (status: complete, 12 build steps recorded)
- `product-brief-semvertag.md` — full product brief (status: complete)
- `product-brief-semvertag-distillate.md` — LLM distillate of the brief

## PRD Frontmatter Summary

- workflowType: `prd`
- classification: `cli_tool` / `general` / `low` complexity / `greenfield-with-transferable-code`
- releaseMode: `phased`
- documentCounts: 2 briefs, 0 research, 0 brainstorming, 0 project docs
- Author: Artur Shiriev
- Date: 2026-05-25

## Validation Findings

### Format Detection

**PRD Structure (Level 2 headers in order):**
1. Executive Summary
2. Project Classification
3. Success Criteria
4. Product Scope
5. User Journeys
6. CLI Tool Specific Requirements
7. Project Scoping & Phased Development
8. Functional Requirements
9. Non-Functional Requirements
10. Traceability

**BMAD Core Sections Present:**
- Executive Summary: Present
- Success Criteria: Present
- Product Scope: Present
- User Journeys: Present
- Functional Requirements: Present
- Non-Functional Requirements: Present

**Format Classification:** BMAD Standard
**Core Sections Present:** 6/6

**Additional BMAD-aligned sections present:**
- Project Classification (recommended when domain/type/complexity are classified in frontmatter)
- CLI Tool Specific Requirements (project-type-specific requirements section)
- Project Scoping & Phased Development (release-mode-aware scoping section)
- Traceability (explicit Vision → SC → Journeys → FR/NFR mapping — exceeds template baseline)

**Verdict:** Structurally exemplary. Skipping parity check (step 2b) and proceeding to density validation.

### Information Density Validation

**Anti-Pattern Scan Results (660 lines scanned):**

| Category | Patterns checked | Hits |
|---|---|---|
| Conversational filler | "the system will allow", "it is important to note", "in order to", "for the purpose of", "with regard/respect to", "it should be noted", "please note" | 0 |
| Wordy phrases | "due to the fact that", "in the event of", "at this point in time", "in a manner that", "in light/spite of the fact", "with the exception of" | 0 |
| Redundant phrases | "future plans", "past history", "absolutely essential", "end result", "advance planning", "exact same", "free gift", "added bonus", "basic fundamentals", "new innovation" | 0 |
| Hedge words / passive bloat | "perhaps", "might", "maybe", "somewhat", "sort/kind of", "basically", "essentially", "generally speaking", "in general", "will/should/would be able to" | 0 |
| Empty intensifiers | "extremely", "highly", "quite", "fairly", "very", "really" | 0 |
| Redundant qualifiers | "actual fact", "true fact", "first and foremost", "each and every", "one and the same" | 0 |

**FR/NFR Style Conformity:**
- 46/46 FRs (100%) use the capability-form preamble (`User can…` / `System…` / `A contributor…`) per BMAD guidance.
- 0 uses of "shall" in FR/NFR section (BMAD allows but does not require it; capability-form is preferred and used consistently).
- Single `will` occurrence (line 493) is in a section preamble, not a requirement — not a violation.

**Total Violations:** 0
**Severity Assessment:** Pass

**Recommendation:** PRD demonstrates exceptional information density. Every sentence carries weight; zero filler. This is the BMAD density ideal in practice.

### Product Brief Coverage

**Briefs scanned:** `product-brief-semvertag.md`, `product-brief-semvertag-distillate.md`

#### Coverage Map

| Brief item | Coverage | PRD location |
|---|---|---|
| Vision (small, opinionated CLI; boring & reliable; uncontroversial pick) | Fully | Exec Summary L29–47; Vision L154–161 |
| Primary user (platform/DevOps/SRE on GitLab) | Fully | Exec Summary L31; Journey 1 (Petr) L167–183 |
| Secondary users (Terraform, Helm, Python lib authors, GH Actions users) | Fully | Exec Summary L31; Journey 3 (Dani Terraform) L205–223 |
| Problem statement — pain 1: workflow lock-in | Fully | Exec Summary L33; differentiation legs L37–43 |
| Problem statement — pain 2: GitLab second-class | Fully | Exec Summary L33; FR17, FR40, NFR15 |
| Problem statement — pain 3: existing tools over-reach | Partial (implicit) | Anti-goals L103–107; CLI scope L319–322 ("not in v1.0 command surface"); Out-of-scope subtext throughout. Not labeled as a "problem" explicitly. |
| Key feature: two strategies, one binary | Fully | FR11, FR12, FR14, FR15, FR16; Config schema L356–402 |
| Key feature: zero-install (uvx) | Fully | FR42; NFR1, NFR2, NFR29 |
| Key feature: GitLab-first multi-provider | Fully | FR17–22, NFR15 |
| Key feature: auto-detect context | Fully | FR20, FR33 |
| Key feature: does one job well | Fully | CLI command structure L297–322; Journey 3 capabilities |
| Key feature: modern Python typed | Fully | NFR23, NFR27 |
| Differentiator: migration-aware dual-mode | Fully | Exec Summary L37–43; Traceability L625 |
| Differentiator: GitLab-native and alive | Fully | Exec Summary L40; Traceability L626 |
| Differentiator: zero-install runtime-minimal | Fully | Exec Summary L41; Traceability L627 |
| Aha-moment language | Fully | Exec Summary L45 (verbatim from brief) |
| Brand voice ("boring and reliable") | Fully | Exec Summary L47 (direct quote); Vision L161 |
| Worked example (30 legacy + 5 pilot repos) | Exceeded | Journey 2 (Marina) L185–203 expands worked example into a journey |
| Success criteria — 6-month signals | Fully | L66–73 (with 2026-11-25 absolute date) |
| Success criteria — 12-month signals | Fully | L75–79 (with 2027-05-25 absolute date) |
| Success criteria — anti-goals | Exceeded | L103–107 (brief's 2 anti-goals + 2 added: raif-autosemver deprecation, paid promotion) |
| Scope — v1.0 deliverables | Fully | L111–141 (granular checklist; mirrors distillate L100–135) |
| Scope — v1.x roadmap | Fully | L143–152 |
| Scope — explicit out-of-scope | Fully | Anti-goals L103–107; Out of v1.0 command surface L319–322 |
| Risks — name collision | Fully | Market risk row L479 |
| Risks — differentiation durability | Fully | Market risk row L476 |
| Risks — bus factor | Fully | Resource risk row L485 |
| Risks — IP/legal clearance | Fully | Resource risk row L486 |
| Risks — internal vendoring | Fully | Resource risk row L487 |
| Risks — GitLab native auto-tagging | Fully | Market risk row L478 |
| Risks — Python 3.10+ floor breaking enterprises | Added by PRD | Technical risk row L470 |
| Edge cases (zero tags, non-semver tags, squash-merge, shallow clones, non-main default, empty default) | Fully | L119; FR3, FR4, FR7, FR8, FR9, FR10 |
| Token/credential UX (CI_JOB_TOKEN, scopes, specific errors) | Fully | FR26, FR29, FR30; config schema L383–397 |
| Vision (2–3 yr) | Fully | L154–161 |

#### Brief's Open-Questions-for-PRD Resolution

The brief explicitly handed five open questions to the PRD (brief L155–161; distillate L163–171). Resolution status:

| Open question | Resolved? | Where |
|---|---|---|
| Config surface (TOML in pyproject vs `.semvertag.toml` vs env-only) | **Resolved** | L358–402: all three supported, pyproject.toml preferred |
| Strategy switching granularity (per-repo vs per-branch) | **Resolved** | L151: per-repo in v1.0, per-branch in v1.x |
| Internal mirroring path (direct/Artifactory/vendored — who owns?) | **Punted with rationale** | L487: explicitly out of scope as a success metric; "separate internal-vendoring path can run on its own timeline" — but the *ownership* question from the brief is left unanswered |
| GitHub org (personal / `semvertag-dev` / Raiffeisen public) | **Not resolved** | L141 references "GitHub org" generically; specific choice not made |
| Sunset signal for dormant PyPI `autosemver` (ignore vs contact) | **Partially resolved** | L479 says migration docs link predecessors; the contact-the-maintainer-or-not question is not addressed |
| (Distillate-only) Raiffeisen-in-README question | **Not resolved** | No mention of whether the "used in production at Raiffeisen" line appears in README |

#### Coverage Summary

**Overall Coverage:** ~95% (excellent)
**Critical Gaps:** 0
**Moderate Gaps:** 0
**Informational Gaps:** 4
  1. Pain 3 ("existing tools over-reach") is implicit in scope discipline but not labeled as a problem in the Executive Summary's problem statement. Could be added as a third bullet.
  2. GitHub org choice not made (informational — affects bus-factor narrative and handle reservation list at L141).
  3. Dormant PyPI `autosemver` sunset action not specified (informational — low priority since rename makes this largely moot).
  4. Whether the "in production at Raiffeisen" line appears in the README is not decided (informational — likely a launch-week decision dependent on IP review).

**Recommendation:** Coverage is exceptional. The four informational gaps are launch-meta decisions that don't block implementation. Consider adding a short "Launch Decisions Pending" subsection (or a TODO comment in the relevant scope items) for traceability if desired — otherwise leave as-is and resolve before announcement.

### Measurability Validation

#### Functional Requirements

**Total FRs Analyzed:** 46

**Format Compliance:** 46/46 (100%)
- 46 FRs use the BMAD `[Actor] can [capability]` / `System [verb]` pattern
- Actors clearly identified: `User`, `System`, `A contributor`
- Every capability is actionable and testable from the description alone

**Subjective Adjectives:** 0
- Scanned: easy, simple, intuitive, user-friendly, responsive, quick, efficient, nice, robust, seamless, clean, smooth
- Zero hits in the FR section

**Vague Quantifiers:** 0
- Scanned: multiple, several, some, many, various, number of, a few
- Zero hits in the FR section

**Implementation Leakage:** 0 hard violations; 1 borderline note
- **FR46** names concrete tool commands (`uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check`, `requests-mock`). This is borderline: the named commands *are* the contributor contract, so they belong to the capability surface, but they're tool-specific and would need to be updated if the project switched stacks. See Step 7 (implementation leakage) for the deeper read.

**FR Violations Total:** 0

#### Non-Functional Requirements

**Total NFRs Analyzed:** 30

Per-NFR measurability audit (every NFR has a defined criterion):

| NFR | Criterion | Threshold / observable | Measurement method |
|---|---|---|---|
| NFR1 | End-to-end CI runtime | ≤30 s @ p95 | Provider-API timing, warm uvx cache |
| NFR2 | Cold-start `--help` | ≤5 s | Fresh CI runner |
| NFR3 | First-tag time | <5 min median | Migration-doc telemetry |
| NFR4 | `doctor` runtime | ≤10 s | Direct measurement |
| NFR5 | Idempotency | binary (no duplicate tag) | Re-invocation test |
| NFR6 | Benign no-op exits 0 | binary | Exit-code observation |
| NFR7 | Retry policy | 3 retries, ≤30 s total | Test harness |
| NFR8 | Fail-closed on auth | binary + named cause | Exit-code 3 with structured error |
| NFR9 | No regressions on internal pipelines | byte-identical tag outcomes | Shadow mode for ≥1 release cycle (~2 wk) |
| NFR10 | Token redaction | binary (regex match) | Stdout/stderr/log scan |
| NFR11 | No remote config | binary | Config-loader behavior test |
| NFR12 | Dependency audit | pip-audit clean | Attached to releases |
| NFR13 | Signed PyPI artifacts | trusted-publishing | uv.lock hash verification |
| NFR14 | Vulnerability-disclosure path | SECURITY.md exists, 90-day timeline | Artifact existence + content |
| NFR15 | GitLab CE/EE support | 15.0+ | CI matrix current + previous major |
| NFR16 | GitHub support | github.com + GHE 3.10+ | CI matrix |
| NFR17 | Bitbucket Cloud only | binary | Documented scope |
| NFR18 | CI env support | GitLab 16.0+, GH Actions any, BB Pipelines v1.x | Documented + tested |
| NFR19 | Provider-native context auto-detection | 4 named scenarios | Integration tests |
| NFR20 | JSON schema versioning | `schema_version: "1.0"` | Output inspection |
| NFR21 | Core LOC | <1500 LoC | Soft target, CI-visible |
| NFR22 | Test coverage | ≥85% line, 100% branch on bump logic | pytest-cov, CI-gated |
| NFR23 | Type + lint clean | `ty` + `ruff check` pass | CI |
| NFR24 | Issue first-response | ≤7 days mean, 12 months | Monthly self-audit in MAINTENANCE.md |
| NFR25 | API stability | one-minor-version deprecation | Process check |
| NFR26 | Dependency cadence | quarterly | CI cron PR |
| NFR27 | Python support | 3.10–3.13 | CI matrix |
| NFR28 | OS support | Ubuntu canonical | CI matrix |
| NFR29 | uv version floor | 0.5+ | Documented |
| NFR30 | EOL policy | EOL+12 months | Process check |

**Missing Metrics:** 0
**Incomplete Template:** 0
**Missing Context:** 0
- Every NFR includes a criterion + threshold/observable + measurement method (or, for binary/process NFRs, an unambiguous artifact or behavior to observe).

**NFR Violations Total:** 0

#### Overall Assessment

**Total Requirements:** 76 (46 FRs + 30 NFRs)
**Total Violations:** 0

**Severity:** Pass

**Recommendation:** Requirements demonstrate exceptional measurability. Every FR has a clear actor + testable capability; every NFR has a quantifiable threshold or unambiguous binary observation paired with a documented measurement method. This is unusual rigor — downstream test generation will benefit directly.

### Traceability Validation

#### Chain Validation

**Executive Summary → Success Criteria:** Intact
- Exec Summary identifies three differentiation legs (migration-aware, GitLab-native, zero-install) plus brand voice (boring/reliable). Every leg has a corresponding success measure:
  - Migration-aware → "Strategy switching with one config change" (L62)
  - GitLab-native → "Listed in awesome-gitlab / GitLab CI Catalog component" (L77–78)
  - Zero-install → "First-tag time <5 min median" (L60, NFR3)
  - Boring/reliable brand → Vision L161
- Aha-moment confirmation (L64) directly maps to Exec Summary L45.

**Success Criteria → User Journeys:** Intact
- First-tag time → Journey 1 (Petr, 18-second CI run)
- Strategy switching → Journey 2 (Marina) — central to the journey
- Doctor passes on first run → Journey 1 (Petr runs doctor pre-flight)
- Specific error feedback → Journey 1 (token/scope errors) + Journey 3 (named `contents: write` permission)
- Aha-moment confirmation → Journey 2 worked example
- 6-month adoption signals → Journey 4 (external contributor PR merged)
- 12-month GitHub provider with prod user outside Raiffeisen → Journey 3 (Dani, Terraform on GitHub)
- 12-month awesome-list listing → Journey 3 ("listed in awesome-ci under tag-only")
- 12-month co-maintainer → Journey 4 (Sasha follow-on contributions)
- Technical-success criteria (zero regressions, coverage, type-check) are appropriately *not* journey-coverable — they're inherent quality bars covered by NFRs (NFR9, NFR22, NFR23).

**User Journeys → Functional Requirements:** Intact
- Each journey ends with a "Capabilities this journey requires" enumeration (L178–183, L197–203, L216–222, L236–243).
- Journey Requirements Summary (L246–278) aggregates the per-journey capability lists across four themes (first-five-minutes, migration-aware, tag-only audience, contributor enablement).
- Each capability bullet maps cleanly to one or more FRs.

**Scope → FR Alignment:** Intact
- Every MVP scope bullet (L113–141) has at least one corresponding FR.
- Out-of-scope items (Anti-Goals L103–107; "Explicitly NOT in v1.0 command surface" L319–322) align with FR boundaries (no init/migrate/lint subcommands, no remote-config loading via FR28, no plugin system).

#### Orphan Element Analysis

**Orphan FRs (no traceable source):** 0

The published Traceability matrices (L621–636) explicitly cite 23 of 46 FRs as "Primary FRs" per journey/differentiation-leg. The remaining 23 FRs are not absent from traceability — they trace to other documented antecedents in the PRD:

| Un-cited-in-matrix FR | Traces to |
|---|---|
| FR2 (read most recent commit) | Exec Summary L29; Journey 1 |
| FR4 (skip if already tagged), FR6 (idempotency) | Journey 1 + Scope L119 edge cases + Brief edge-case list |
| FR7 (zero existing tags) | Scope L119 + Brief edge cases |
| FR8 (non-semver tags ignored) | Scope L119 + Brief edge cases |
| FR9 (default-branch detection) | Scope L119; Brief edge cases |
| FR10 (shallow clones) | Scope L119; Brief edge cases |
| FR13 (override branch-prefix mappings) | Config schema L367–374 |
| FR21 (override auto-detected provider) | CLI surface L299–301 |
| FR25 (no config file) | Config schema L362 (resolution order) |
| FR26 (provider-native credentials) | Config schema L386–397 |
| FR27 (precedence) | CLI surface L313–317 |
| FR28 (forbid templating/remote loading) | Scope L399–402; NFR11 cross-link |
| FR31 (`doctor --json`) | Scripting Support L411 |
| FR32 (doctor reports config source) | Journey 1 implicit (doctor's named outputs) |
| FR34 (`--project-id` override) | CLI surface L299 |
| FR35 (`--json`) | Output Formats L333–337 |
| FR36 (`--quiet`) | Output Formats L339 |
| FR37 (exit codes) | Output Formats L347–353 |
| FR38 (stream discipline) | Output Formats L340–343 |
| FR39 (shell completion) | CLI surface L311 |
| FR43 (migration guides) | Scope L135 |
| FR44 (API stability policy) | Scope L137; cross-links to NFR25 |

The CLI Tool Specific Requirements section (L279–424) and the Project Scope section act as the antecedent layer for these. The Phase coverage table (L654–660) covers all 46 FRs in range notation (FR1–FR17, FR20–FR46) for v1.0 and FR18, FR19 for v1.x.

**Unsupported Success Criteria:** 0
**User Journeys Without FRs:** 0 (each of the 4 journeys has explicit capability bullets backed by FRs)

#### Traceability Matrix Summary

| Chain | Status |
|---|---|
| Vision → Success Criteria | Intact |
| Success Criteria → Journeys | Intact (technical SCs appropriately NFR-mapped) |
| Journeys → FRs | Intact via per-journey capability lists + summary |
| Scope → FRs | Intact |
| FR ↔ NFR cross-links | Present (Traceability L625–627 maps legs to FR+NFR pairs) |

**Total Traceability Issues:** 0 (no orphans, no broken chains)

**Severity:** Pass

**Note (informational, not a defect):** The journey/leg matrices at L621–636 enumerate only the *Primary* FRs per journey. A reader who wants a complete `FR → source` lookup must consult the per-journey capability lists, the CLI Tool Specific Requirements section, and the Scope sections in addition to the matrix. If the author wants a single canonical "every FR with its primary source" table for downstream tooling, that could be added as a separate matrix — but no chain is actually broken.

**Recommendation:** Traceability chain is intact. The PRD's explicit Traceability section (already a step beyond the BMAD template baseline) could optionally be extended with a per-FR antecedent table for downstream tooling friendliness — but this is a nice-to-have, not a defect.

### Implementation Leakage Validation

**Scope of scan:** `## Functional Requirements` and `## Non-Functional Requirements` sections only. The `## CLI Tool Specific Requirements` section contains explicitly-labeled `Technical Architecture Considerations` and `Implementation Considerations` subsections (L288–294, L417–424) — these are architecture content, not requirements, and were intentionally excluded from leakage scoring. (See Step 11 for an organizational observation about this section.)

#### Leakage by Category (FR + NFR sections)

| Category | Patterns scanned | Hits |
|---|---|---|
| Frontend frameworks | React, Vue, Angular, Svelte, Next.js, Nuxt | 0 |
| Backend frameworks | Express, Django, Rails, Spring, Laravel, FastAPI | 0 |
| Databases | PostgreSQL, MySQL, MongoDB, Redis, DynamoDB, Cassandra | 0 |
| Cloud platforms | AWS, GCP, Azure, Cloudflare, Vercel, Netlify | 0 |
| Infrastructure | Docker, Kubernetes, Terraform, Ansible | 0 |
| JS libraries | Redux, Zustand, axios, lodash, jQuery | 0 |
| Internal stack | Typer, modern-di, pydantic-settings, rich (in FR/NFR only) | 0 |
| Tool names (borderline) | uv, ruff, ty, pytest, pytest-cov, requests-mock | 3 occurrences (see below) |

#### Borderline Occurrences

**FR46 (L563):** Names `uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ty check`, `requests-mock`.
- *Capability framing:* "A contributor can set up a development environment using documented commands in CONTRIBUTING.md (...) and run the full test suite offline using requests-mock fixtures."
- *Assessment:* Borderline. The named commands are the literal contributor contract; the brief and distillate committed to this exact toolchain. Could be abstracted to "≤4 documented commands and offline-runnable test suite without live API calls", but the current form is more directly testable and matches the brief.
- *Verdict:* Acceptable as-is. Not flagged as a violation.

**NFR22 (L604):** Names `pytest-cov` as the measurement tool.
- *Capability framing:* "Test coverage is ≥85% line coverage overall; bump-strategy parsing logic is 100% branch coverage; measured by pytest-cov and gated in CI."
- *Assessment:* The BMAD NFR template explicitly calls for a measurement method (`[metric] [condition] [measurement method]`). `pytest-cov` is the measurement method. This is template-compliant, not leakage.
- *Verdict:* Compliant. Not flagged.

**NFR23 (L605):** Names `ty`, `# ty: ignore`, `ruff check`, `pyproject.toml`.
- *Capability framing:* "`ty` type-check passes with no `# ty: ignore` comments outside of documented external-API boundaries; `ruff check` passes with the `ALL` ruleset..."
- *Assessment:* The names refer to the *verification* tools that produce the binary pass/fail observation. This is structurally the same as NFR22's "measurement method" — the named tools are the observability mechanism.
- *Verdict:* Acceptable. The PRD's choice to name specific verifier tools is a stronger contract than abstracting to "type checker" / "linter", and aligns with the brief's tool commitments.

#### Summary

**Total Implementation Leakage Violations:** 0 (3 borderline occurrences all defensible as capability-contract or measurement-method)

**Severity:** Pass

**Recommendation:** No significant implementation leakage in FRs/NFRs. The three tool-name occurrences are either contributor-contract surface (FR46) or BMAD-template-compliant measurement methods (NFR22, NFR23). Internal architecture details (`Typer`, `modern-di`, `pydantic-settings`, `rich`) are properly compartmentalized into the explicitly-labeled `Technical Architecture Considerations` and `Implementation Considerations` subsections, not FRs/NFRs.

### Domain Compliance Validation

**Domain:** `general` (per PRD frontmatter `classification.domain`)
**Complexity:** Low (per PRD frontmatter `classification.complexity`)

**Assessment:** N/A — No special domain compliance requirements.

**Notes:**
- The PRD self-classifies as general developer-tooling: no Healthcare/HIPAA, Fintech/PCI-DSS, GovTech/FedRAMP/Section 508, or other regulated-industry overlay applies.
- The Project Classification section (L49–54) explicitly states "Domain: General developer tooling — no regulated industry, no compliance overlay, no novel research domain. Standard software practices apply."
- The Project Classification section also notes "elevated *strategic* complexity" (name collision, dual-mode positioning, multi-provider roadmap, GitLab CI Catalog distribution path, Raiffeisen IP-clearance dependency) — but strategic-launch complexity is not regulatory complexity and is appropriately handled via the Risk Mitigation Strategy section (L463–489), not a compliance section.
- One quasi-compliance theme is present and appropriately scoped: supply-chain security (NFR10 token redaction, NFR11 no remote config, NFR12 dependency audit, NFR13 trusted publishing, NFR14 vulnerability disclosure path, FR28 forbidden config behaviors). These are general software-security best practices, not domain-mandated regulation — and the PRD treats them as standard security NFRs, which is correct.
- Raiffeisen IP-clearance is internal organizational compliance, not regulatory; properly handled as a resource-risk row (L486).

**Severity:** Pass (N/A — out of scope by classification)

### Project-Type Compliance Validation

**Project Type:** `cli_tool` (primary) + `developer_tool` (secondary, per L51)

#### Required Sections — cli_tool

| Section | Status | Location |
|---|---|---|
| command_structure | Present | `### Command Structure` (L296–322): primary invocation forms, subcommands, flag precedence, explicit "not in v1.0" surface |
| output_formats | Present | `### Output Formats` (L324–353): human/JSON/quiet modes, stream discipline, exit codes table |
| config_schema | Present | `### Config Schema` (L356–402): file locations + resolution order, minimal example, env-var table, forbidden-in-config rules |
| scripting_support | Present | `### Scripting Support` (L404–415): non-interactive guarantee, stable exit codes, versioned JSON schema, composability examples, shell-completion support |

**Required Sections Present (cli_tool): 4/4**

#### Required Sections — developer_tool (secondary)

| Section | Status | Notes |
|---|---|---|
| language_matrix | N/A (single-language) | Python-only project; NFR27 documents Python 3.10–3.13 support |
| installation_methods | Present | FR40, FR41, FR42; CLI Tool section L292–293 (uvx + pip + Marketplace + CI Catalog) |
| api_surface | Present (with explicit scope) | CLI flag/config/exit-code/JSON-schema surface fully documented; Python-package API explicitly *not* covered by stability policy (L285) |
| code_examples | Present | GitLab CI snippet, JSON output example (L334–336), shell pipeline example (L410–412), `.semvertag.toml` config example (L364–381) |
| migration_guide | Present | Three migration guides committed in scope L135; FR43 codifies the user-facing capability |

**Required Sections Present (developer_tool): 4/5 (1 N/A because single-language)**

#### Excluded Sections — cli_tool

| Section | Status |
|---|---|
| visual_design | Absent ✓ |
| ux_principles | Absent ✓ (User Journeys section is the BMAD core, not "UX principles") |
| touch_interactions | Absent ✓ |

#### Excluded Sections — developer_tool

| Section | Status |
|---|---|
| visual_design | Absent ✓ |
| store_compliance | Absent ✓ |

**Excluded Sections Present: 0 (no violations)**

#### Compliance Summary

**Required Sections:** 8/9 present (1 N/A — language_matrix not applicable to single-language project)
**Excluded Sections Present:** 0
**Compliance Score:** 100% (excluding N/A)

**Severity:** Pass

**Recommendation:** Project-type coverage is exemplary. All four required `cli_tool` sections are present and substantive. The secondary `developer_tool` classification (acknowledged in the PRD's own Project Classification section) is appropriately covered via FR40–42, the API stability policy, and the migration guides. No excluded sections are present. Note: the same "CLI Tool Specific Requirements" section contains `Technical Architecture Considerations` (L287–294) and `Implementation Considerations` (L417–424) subsections that are arguably architecture-content rather than requirements-content — see Step 11 (Holistic Quality) for an organizational observation.

### SMART Requirements Validation

**Total Functional Requirements scored:** 46

**Scoring scale per criterion (1–5):**
- Specific: clarity and unambiguity
- Measurable: testability with quantifiable or binary criteria
- Attainable: realistic given known constraints
- Relevant: alignment with user needs / business objectives
- Traceable: explicit link to journey, scope, or business objective

#### Scoring Summary

| Metric | Result |
|---|---|
| Total FRs | 46 |
| FRs with all scores ≥ 3 | 46/46 (100%) |
| FRs with all scores ≥ 4 | 45/46 (97.8%) |
| FRs scoring perfect 25/25 | 38/46 (82.6%) |
| Lowest individual score | 3 (single occurrence: FR45 Attainable) |
| Overall average score across 230 slots | ≈ 4.85/5 |

#### FRs Not at Perfect 25/25

All 8 non-perfect FRs still pass the threshold (every individual criterion ≥3). Listed with reason:

| FR | Score deltas | Reason |
|---|---|---|
| FR13 | T=4 | Override of branch-prefix mappings traces to config schema (L367–374) and Journey 2 implicitly, but is not in the explicit Journey/Leg matrices |
| FR16 | T=4 | Same as FR13 for Conventional Commits mappings |
| FR22 | M=4 | "Adds a new provider in a single file" is testable; the underlying `Provider` protocol's documentation is an implicit pre-requisite, slight ambiguity |
| FR40 | A=4 | GitLab CI Catalog publishing depends on GitLab's external acceptance/process — partially outside the team's direct control |
| FR41 | A=4 | GitHub Actions Marketplace publishing depends on GitHub's external review — partially outside the team's direct control |
| FR44 | M=4 | API stability policy is binary (broken vs. honored) but enforcement is a process measure across maintainers, not a single code test |
| FR45 | S=4, M=4, A=3 | "SEO-tuned README" is concrete via the named keywords; awesome-list acceptance is outside the team's direct control (rate-limits Attainable to 3); discoverability outcome is fuzzy in part |
| (no others) | | |

#### Improvement Suggestions for Sub-5 Scores

**FR13, FR16 (Traceable=4):** Optional — add a row to the Traceability matrix mapping config-customization FRs to Journey 2 (Marina's per-repo config edit is the only journey that exercises mapping customization).

**FR22 (Measurable=4):** Optional — add a sub-requirement that "the `Provider` protocol is documented in `CONTRIBUTING.md` with the GitLab provider source linked as the reference implementation" to make the dependency explicit. The current wording assumes the protocol documentation exists.

**FR40, FR41 (Attainable=4):** These dependencies are real and are honestly modeled. Consider reframing as "User can adopt semvertag in GitLab CI via the published GitLab CI Catalog component, **once accepted into the Catalog**" — making the external-acceptance dependency explicit in the FR text. Alternatively, leave as-is and rely on the Risk Mitigation Strategy section to capture the dependency.

**FR44 (Measurable=4):** Consider adding a self-audit point: e.g., "the changelog includes a `Breaking Changes` section with at least one minor-version deprecation entry preceding each removal." This converts the policy from process-only to artifact-checkable.

**FR45 (Attainable=3):** Strongest candidate for refinement. Split into two FRs:
- FR45a: "User can discover semvertag via SEO-tuned README content containing the keywords 'GitLab CI', 'auto tag', 'semver', and via published presence on the GitHub Actions Marketplace and GitLab CI Catalog." (fully attainable — directly controlled)
- FR45b (or move to Success Criteria — already there at L77): "Listed in ≥1 `awesome-gitlab` or `awesome-ci` curated list." (outcome metric — appropriately a Success Criterion, not an FR)

#### Overall Assessment

**Flagged FRs (any score <3):** 0
**Severity:** Pass

**Recommendation:** Functional Requirements demonstrate excellent SMART quality. 82.6% of FRs are perfect (25/25), 97.8% are at ≥4 on every criterion, and 100% pass the threshold. The eight non-perfect FRs all involve real-world dependencies (external acceptance into catalogs/lists, multi-maintainer process enforcement) that are honestly modeled rather than papered over. The single Attainable=3 (FR45) is the only suggestion worth acting on if the author wants a 100% perfect set — splitting it into a controllable FR + a success-criteria outcome would push the whole set to ≥4 on every criterion.

### Holistic Quality Assessment

#### Document Flow & Coherence

**Assessment:** Excellent

**Strengths:**
- Narrative arc holds across 660 lines: Exec Summary → Classification → Success Criteria → Scope → Journeys → CLI specifics → Scoping → FRs → NFRs → Traceability. Each section advances the prior.
- The four user journeys (Petr, Marina, Dani, Sasha) are voice-driven with specific personas, concrete numbers (15 repos, 18-second CI run, 30 legacy + 5 pilot repos), and authentic friction. This is rare PRD craft — most journeys read as bulleted stages; these read as short stories with embedded capability requirements.
- The "Trust-and-Adoption MVP" framing at L429–434 is genuinely thoughtful — it identifies that for an open-source tool replacing established alternatives, the binding constraint is trust artifacts (docs, badges, marketplace presences), not feature count. Most PRDs miss this distinction.
- Anti-goals at L103–107 and the "Explicitly NOT in v1.0 command surface" block at L319–322 do real work — they tell downstream agents what *not* to build, which is as important as what to build.
- The explicit Traceability section (L617–660) is a feature most BMAD PRDs lack outright; here it's three matrices and a phase-coverage table.

**Areas for Improvement:**
- The `## CLI Tool Specific Requirements` section bundles four kinds of content (project overview, architecture considerations, command-surface contracts, implementation considerations) under one heading. Subsections labeled `Technical Architecture Considerations` (L287–294) and `Implementation Considerations` (L417–424) are honestly named, but a casual reader scanning section headers won't expect architecture in a section whose title ends in "Requirements." Consider extracting these into a separate `## Architecture Notes` section or referencing a sibling `architecture.md` file.

#### Dual Audience Effectiveness

**For Humans:**
- **Executive-friendly:** Exec Summary delivers vision, problem, differentiation, brand voice in ~50 lines. An exec who reads only L29–47 has the essentials.
- **Developer clarity:** 46 FRs + 30 NFRs + concrete config schema + exit-code table + JSON schema versioning. A developer can implement against this without further discovery.
- **Designer clarity:** Limited applicability (CLI tool, no visual UI), but Output Formats (L324–353) and the journey vignettes serve the equivalent role for terminal-UX expectations.
- **Stakeholder decision-making:** Anti-goals, risk matrices (Technical/Market/Resource), and explicit Success Criteria with absolute dates (2026-11-25, 2027-05-25) give stakeholders clean go/no-go criteria.

**For LLMs:**
- **Machine-readable structure:** Level-2 headers consistent throughout; FRs/NFRs are individually IDed (FR1–FR46, NFR1–NFR30); tables used for matrices and exit codes.
- **UX readiness:** N/A for visual UX; for stream/terminal UX, the explicit JSON schema versioning + exit-code table is generation-ready.
- **Architecture readiness:** Technical Architecture Considerations and Implementation Considerations give the architecture agent a strong starting point (Provider protocol + BumpStrategy protocol + settings layer + output layer + distribution).
- **Epic/Story readiness:** FRs are atomic and IDed; journey-to-FR mappings exist; phase coverage explicitly slices v1.0 vs. v1.x. Decomposition into epics is mechanical from here.

**Dual Audience Score:** 5/5

#### BMAD PRD Principles Compliance

| Principle | Status | Notes |
|---|---|---|
| Information Density | Met | 0 anti-pattern hits across 660 lines (Step 3) |
| Measurability | Met | 76/76 requirements measurable (Step 5) |
| Traceability | Met | Explicit Traceability section + per-journey capability lists + per-phase coverage (Step 6) |
| Domain Awareness | Met | General/low classification explicit; security NFRs included; no spurious regulatory sections (Step 8) |
| Zero Anti-Patterns | Met | Filler / wordy / hedge / intensifier scans all clean (Step 3) |
| Dual Audience | Met | IDed atomic FRs + narrative journeys + tables (this step) |
| Markdown Format | Met | Consistent ## structure; tables; fenced code blocks; explicit absolute dates |

**Principles Met:** 7/7

#### Overall Quality Rating

**Rating:** 5/5 — Excellent

This PRD is at the high end of the BMAD quality scale. It is structurally complete (6/6 core sections + 4 optional sections), exceptionally dense (zero anti-patterns), comprehensively measurable, traceable end-to-end, project-type-compliant, and SMART-clean at 100%. The journey vignettes and trust-and-adoption MVP framing show craft beyond template adherence.

#### Top 3 Improvements

1. **Extract architecture content from the "CLI Tool Specific Requirements" section.**
   *Why:* `Technical Architecture Considerations` (L287–294) and `Implementation Considerations` (L417–424) describe HOW, not WHAT. They're labeled accurately within their subsections, but the parent section title contains "Requirements," which sets a "specifies behavior" expectation. A downstream architecture agent reading the section will treat this content as input; a developer reading FRs may skim past it.
   *How:* Either (a) move both subsections into a new `## Architecture Notes` section after CLI specifics, or (b) extract them into `architecture.md` and reference from the PRD. Option (b) is more BMAD-canonical (PRD feeds architecture), option (a) is the smaller edit.

2. **Split FR45 into controllable and outcome components.**
   *Why:* FR45 currently combines internally-controlled discovery surfaces (README SEO keywords, Marketplace presence, CI Catalog presence) with externally-gated outcomes (acceptance into awesome-lists). The latter is already a 12-month Success Criterion at L77; including it in an FR forces FR45 to score Attainable=3 (the only sub-4 score in the entire FR set).
   *How:* Reframe FR45 as: "User can discover semvertag via SEO-tuned README content containing 'GitLab CI', 'auto tag', 'semver', and via published presence on the GitHub Actions Marketplace and GitLab CI Catalog." Drop the awesome-list mention; it remains a Success Criterion outcome.

3. **Add a "Launch Decisions Pending" subsection capturing the 4 informational gaps.**
   *Why:* The brief explicitly handed 5 open questions to the PRD; 3 were resolved cleanly, 2 were left unanswered (GitHub org choice, dormant-PyPI sunset signal), plus 2 PRD-internal gaps (pain-3 not labeled as a problem, Raiffeisen-in-README decision). None block implementation, but unresolved launch-meta decisions tend to get improvised under pressure two days before announcement.
   *How:* Add a 4–6-line subsection at the bottom of the Project Scoping section listing each pending decision with a target resolution date (e.g., "decide GitHub org before handle reservation"). Alternatively, add a row each to the existing risk matrices.

#### Honorable-Mention Improvements (not in top 3)

- **Per-FR antecedent table.** The published Journey→FR matrix at L632 cites only "Primary FRs"; 23 of 46 FRs are not enumerated in any traceability table (though all are documented antecedents elsewhere — Journey capability lists, Scope, CLI section). A single canonical `FR → primary source` table would simplify downstream tooling but isn't a defect.
- **Asterisk-marker consistency for v1.x items.** Currently mixes `(*v1.x*)` inline and bare `*` suffixes (e.g., `FR18*` in traceability table L635). Pick one form.
- **NFR21 LOC soft-target audit method.** "<1,500 lines of Python" is explicit but the audit method is "soft target visible in CI." Specifying which tool reports the count (e.g., `tokei` or `scc`) would mirror the measurement-method pattern used by NFR22.

#### Summary

**This PRD is:** an exemplary BMAD PRD that exceeds template baselines on traceability, journey craft, and anti-goal discipline — and could become unimprovable with three small edits.

**To make it great:** It already is. The three improvements above polish a strong document.

### Completeness Validation

#### Template Completeness

**Template Variables Found:** 0
- Scanned for: `{variable}`, `{{variable}}`, `[PLACEHOLDER]`, `[TBD]`, `TODO`, `TBD`, `XXX`, `FIXME`, `[insert...]`
- Zero hits. No unresolved scaffolding.

#### Content Completeness by Section

| Section | Status | Notes |
|---|---|---|
| Executive Summary | Complete | Vision, dual-problem framing, three differentiation legs, brand voice — all present (L27–47) |
| Project Classification | Complete | Type, domain, complexity (with strategic-complexity caveat), greenfield context (L49–54) |
| Success Criteria | Complete | User / Business (6m + 12m) / Technical / Anti-Goals + outcomes table (L56–107) |
| Product Scope | Complete | MVP / Growth / Vision tiers (L109–161) |
| User Journeys | Complete | 4 named journeys with capability requirements + cross-cutting summary (L163–278) |
| CLI Tool Specific Requirements | Complete | Overview, architecture, command structure, output formats, config schema, scripting support, implementation considerations (L279–424) |
| Project Scoping & Phased Development | Complete | MVP philosophy + feature set + post-MVP + risk mitigation (L426–489) |
| Functional Requirements | Complete | 46 FRs in 8 thematic groups with v1.0/v1.x markers (L491–563) |
| Non-Functional Requirements | Complete | 30 NFRs in 6 thematic groups (L565–615) |
| Traceability | Complete | 4 matrices + phase coverage (L617–660) |

**Sections complete: 10/10**

#### Section-Specific Completeness

| Check | Result |
|---|---|
| Success-criteria measurability | All — every criterion has a threshold or absolute-dated target |
| User journeys cover all user types | Yes — primary (Petr), primary mid-migration (Marina), secondary (Dani), contributor (Sasha) |
| FRs cover MVP scope | Yes — Phase coverage table maps every MVP-scope item to one or more FRs (L656) |
| NFRs have specific criteria | All — every NFR has a measurement method or unambiguous binary observable (Step 5 table) |

#### Frontmatter Completeness

| Field | Status |
|---|---|
| stepsCompleted | Present (14 build steps recorded) |
| classification (projectType / domain / complexity / projectContext) | Present (all four sub-fields populated) |
| inputDocuments | Present (2 documents) |
| date (completedAt) | Present (2026-05-26) |
| status | Present (`complete`) |
| workflowType | Present (`prd`) |
| releaseMode | Present (`phased`) |
| documentCounts | Present (briefs:2, research:0, brainstorming:0, projectDocs:0) |

**Frontmatter completeness:** 4/4 required fields + 4 useful extras

#### Completeness Summary

**Overall Completeness:** 100% (10/10 sections complete)

**Critical Gaps:** 0
**Minor Gaps:** 0

**Severity:** Pass

**Recommendation:** PRD is complete. All sections present and substantive, no template scaffolding remaining, frontmatter fully populated. Ready for downstream consumption (UX design, architecture, epic/story breakdown).

---

## Final Summary

**Overall Status:** Pass

### Quick Results

| Check | Result |
|---|---|
| Format Detection | BMAD Standard (6/6 core sections + 4 optional) |
| Information Density | Pass (0 anti-pattern hits) |
| Brief Coverage | ~95% — 4 informational gaps (launch-meta decisions) |
| Measurability | Pass (76/76 requirements measurable) |
| Traceability | Pass (0 orphans, all chains intact) |
| Implementation Leakage | Pass (0 violations; 3 defensible borderline occurrences) |
| Domain Compliance | N/A (general / low complexity by classification) |
| Project-Type Compliance | 100% (8/8 applicable required sections; 0 excluded-section violations) |
| SMART Quality | 100% pass threshold (97.8% ≥4 on every criterion; 82.6% perfect) |
| Holistic Quality | 5/5 — Excellent |
| Completeness | 100% (10/10 sections complete; 0 template variables) |

### Critical Issues: 0
### Warnings: 0
### Informational Observations: 4

1. **Pain-3 ("existing tools over-reach") not labeled as a problem** in Executive Summary's problem statement — implicit elsewhere via scope discipline and anti-goals.
2. **GitHub org choice not made** — affects bus-factor narrative and the L141 handle reservation list.
3. **Dormant PyPI `autosemver` sunset signal not specified** — the contact-the-maintainer-vs.-ignore question from the brief is not addressed.
4. **Raiffeisen-in-README question not resolved** — IP-clearance-dependent launch decision.

### Strengths

- Six of six BMAD core sections present, plus four optional sections (Project Classification, CLI Tool Specific Requirements, Project Scoping & Phased Development, Traceability).
- Zero information-density anti-patterns across 660 lines.
- All 76 requirements (46 FRs + 30 NFRs) are testable with documented measurement methods.
- Four narrative user journeys with specific personas, concrete numbers, and explicit per-journey capability requirements — exceptional craft.
- Trust-and-Adoption MVP framing identifies the real binding constraint (trust artifacts, not feature count) — rare strategic insight.
- Anti-goals and "explicitly not in v1.0" sections do active work for downstream agents.
- Risk Mitigation Strategy splits Technical / Market / Resource & Governance with mitigations for each row.
- Explicit Traceability section with four matrices — exceeds BMAD template baseline.
- Brief's open questions: 3/5 resolved cleanly; the 2 unresolved are launch-meta, not implementation blockers.

### Holistic Quality: 5/5 — Excellent

### Top 3 Improvements (from Step 11)

1. **Extract architecture content from "CLI Tool Specific Requirements".** The `Technical Architecture Considerations` (L287–294) and `Implementation Considerations` (L417–424) subsections describe HOW, not WHAT. Move them to a sibling `## Architecture Notes` section or to a separate `architecture.md`.
2. **Split FR45 to remove the awesome-list external-dependency dilution.** Keep the controllable surfaces (README SEO, Marketplace, CI Catalog) in the FR; rely on the existing 12-month Success Criterion at L77 for the awesome-list outcome.
3. **Add a "Launch Decisions Pending" subsection** capturing the 4 informational gaps (pain-3 framing, GitHub org choice, dormant-PyPI sunset signal, Raiffeisen-in-README decision) with target resolution dates.

### Recommendation

PRD is in excellent shape. None of the findings block downstream consumption — UX design (not strongly applicable for a CLI), architecture, and epic/story breakdown can all proceed today. The three improvements above polish a strong document but are not gating. The PRD demonstrates rare craft in journey writing, anti-goal discipline, and trust-MVP framing; it exceeds the BMAD template baseline on traceability.

**Ready for:** architecture, epic/story breakdown, implementation kickoff.

---

## Post-Validation Edits (Applied 2026-05-26)

All three top improvements from Step 11 were applied via the [F] Fix Simpler Items menu option.

### Edit 1: FR45 split (applied)

**Before:** `FR45` mixed controllable surfaces (README SEO, Marketplace, CI Catalog) with externally-gated outcomes (awesome-list acceptance).

**After (prd.md L579):** FR45 now lists only controllable surfaces. The awesome-list outcome remains tracked at L77 as a 12-month Success Criterion, with an inline note in FR45 cross-referencing this. Pushes the FR set to **100% ≥4 on every SMART criterion** (FR45 Attainable lifted from 3 → 5).

### Edit 2: Launch Decisions Pending subsection (applied)

**Added** at prd.md L497 inside `## Project Scoping & Phased Development`. Captures the 4 informational gaps as a table with source, target resolution, and status columns:
- GitHub org choice
- Dormant PyPI `autosemver` sunset signal
- "Used in production at Raiffeisen since [date]" line in README
- Frame "existing tools over-reach" as a third explicit problem bullet

All four marked `Open`. The author/owner is expected to update `Status` as decisions resolve before announcement.

### Edit 3: Architecture content extracted (applied)

**Moved** the `Technical Architecture Considerations` and `Implementation Considerations` subsections out of `## CLI Tool Specific Requirements` and into a new **`## Architecture Notes`** section (prd.md L411).

- New section sits between `## CLI Tool Specific Requirements` and `## Project Scoping & Phased Development`
- Includes a short intro paragraph clarifying that the section captures HOW (input to downstream architecture work), not WHAT
- Added a one-line pointer at the end of the CLI Tool Specific Requirements overview (L287) directing readers to the new section

Result: the `CLI Tool Specific Requirements` section now exclusively describes user-facing CLI contract content (command structure, output formats, config schema, scripting support). Architecture-content is in its own clearly-labeled section, which the downstream architecture agent should treat as primary input.

### Updated section count

PRD now has **11 ## sections** (was 10): the new `## Architecture Notes` is the addition.

### Re-validated quick results (post-edit)

| Check | Pre-edit | Post-edit |
|---|---|---|
| Format Detection | BMAD Standard (6/6 core + 4 optional) | BMAD Standard (6/6 core + 5 optional) |
| SMART Quality | 97.8% ≥4 on every criterion | **100% ≥4 on every criterion** (FR45 lifted) |
| Holistic Quality | 5/5 — Excellent | 5/5 — Excellent (with structural-clarity improvement) |
| Informational Gaps | 4 unresolved | 4 documented in `Launch Decisions Pending` with target resolution timing |

No new validation issues introduced by the edits.

---

## Re-Validation Pass — 2026-05-26 (Post Architecture Touch-Ups)

**Trigger:** 8-item PRD touch-up pass driven by architecture decisions (logged in `architecture.md` §"PRD Touch-Ups Required"). Items: FR9, FR22, FR23/FR24, FR27, FR28, FR36, FR46, Journey 2. Plus Exec-Summary "optional extras" leftover caught during re-validation.

**Scope:** Delta validation — confirm no regression in the 11 prior validation dimensions; identify any new issues introduced by the edits.

### Edit Summary (verified against `prd.md`)

| # | Item | Verified location |
|---|---|---|
| 1 | FR46 — `requests-mock` → `httpx2.MockTransport` | prd.md:562 (+ cascades at L54, L230, L239, L269, L473) |
| 2 | FR23/FR24 — tagged *(v1.x)*, relocated to v1.x in Growth Features | prd.md:527-528, L147 |
| 3 | FR27 — precedence simplified to CLI > env > defaults | prd.md:531 (+ CLI section L307-315) |
| 4 | Journey 2 — Marina flips `SEMVERTAG_STRATEGY` as a GitLab CI variable | prd.md:191-205 |
| 5 | FR28 — kept as forward-compat policy (trimmed) | prd.md:532 (+ NFR11 cross-ref at L586) |
| 6 | FR36 — `--quiet` clarified to compose with `--json` | prd.md:546 (+ Output Formats L334) |
| 7 | FR22 + cascades — `[github]`/`[bitbucket]` extras removed | prd.md:523, 519-520 (FR18, FR19), L145-146, L400-402, L412, L230-232, L239-240 |
| 8 | FR9 — symbolic-ref fallback trimmed; deferred to v1.x `--offline` | prd.md:504 (+ Risk row L457, Arch-Notes bullet L410) |
| +1 | Exec-Summary leftover — "via optional extras" replaced | prd.md:29 *(caught during re-validation)* |

### Validation Findings

#### Format Detection — Pass (no change)

- ## sections: **11** (was 11 post-first-edit pass; was 10 pre-edit).
- BMAD core sections: 6/6 present.
- Optional sections: 5 (Project Classification, CLI Tool Specific Requirements, Architecture Notes, Project Scoping & Phased Development, Traceability).

#### Information Density — Pass (no regression)

| Anti-pattern category | Hits across 659 lines |
|---|---|
| Conversational filler / wordy phrases / redundant phrases | 0 |
| Hedge words / empty intensifiers / redundant qualifiers | 0 |
| Subjective adjectives / vague quantifiers (FR/NFR lines) | 0 |

New text added by the touch-up pass (FR9 parenthetical, FR22 trailing clause, FR28 forward-compat rewrite, FR36 clarification, FR46 swap, NFR11 update, Config Schema rewrite, Journey 2 rewrite, Arch-Notes httpx2 bullet) introduced **zero** anti-patterns. Style of the existing PRD preserved.

#### FR/NFR Style Conformity — Pass

- 46/46 FRs use capability-form preamble. FR23 and FR24 lead with `*(v1.x)*` phase tag followed by `User can...` — the tag is metadata, the capability form is intact.
- FR28's new preamble is conditional ("When file-based configuration arrives in v1.x..."). This is BMAD-acceptable for a forward-compatibility policy; the capability described (loader rejects violations) is testable.
- 30/30 NFRs unchanged in form.

#### Brief Coverage — Pass with one shift

The brief's Open Question 1 ("Config surface — TOML in pyproject vs `.semvertag.toml` vs env-only") was previously logged as **Resolved**. After the touch-up pass, the resolution shifts to:

- v1.0: env vars + CLI flags only
- v1.x: file-based config (`[tool.semvertag]` in `pyproject.toml` and standalone `.semvertag.toml`) added under FR23/FR24

**Status:** still **Resolved**, now with phased delivery — the brief did not mandate v1.0 file-based config; it asked which surfaces are supported. The PRD answers: all three, with phasing. The brief's "one tool, two strategies, one config change" beat survives in v1.0 via the `SEMVERTAG_STRATEGY` CI variable mechanism, and survives in v1.x via the file-based key edit. No coverage regression.

Other brief items unaffected: vision, problem statement, three differentiation legs, success criteria, anti-goals, scope tiers, risk mitigation, all 4 journey personas — all unchanged.

#### Measurability — Pass (no regression)

- **Total Requirements:** 46 FRs + 30 NFRs = 76 (unchanged count)
- Each edited FR remains independently testable:
  - **FR9:** provider-API detection + `SEMVERTAG_DEFAULT_BRANCH` override — both have direct test paths.
  - **FR22:** "single file" + "no extras packaging" — verifiable by inspecting `providers/` structure and `pyproject.toml`.
  - **FR23, FR24:** v1.x-scoped; testable when the file loader ships.
  - **FR25:** v1.0 explicit "env+flags only" surface — testable by absence of file-loader code paths.
  - **FR27:** 3-layer precedence — testable via override-cascade matrix.
  - **FR28:** v1.x policy — testable when the loader ships (rejection behavior with exit code 2).
  - **FR36:** `--quiet --json` composition — testable by output capture.
  - **FR46:** `httpx2.MockTransport` — substitutes 1:1 for `requests-mock` as the offline-test contract.
- **NFR11** rewrite preserves measurability — the v1.0 portion is observable today (no remote-config behaviors exist); the v1.x portion is a documented constraint for the future loader.

#### Traceability — Pass (matrices updated, chains intact)

- Journey 2 matrix updated: `FR3, FR5, FR11, FR14, FR15, FR25 (v1.0 env/flag-only); FR23, FR24 (v1.x file-based)`.
- Success-Criteria "Strategy switching with one config change" updated to reflect v1.0 via CI variable + v1.x via file.
- Phase coverage table now correctly partitions: v1.0 = `FR1–FR17, FR20–FR22, FR25–FR46 (excl. v1.x-tagged)`; v1.x = `FR18, FR19, FR23, FR24`.
- No orphan FRs introduced; FR23/FR24 traceable to Journey 2 (v1.x form) and Growth Features bullet.

#### Implementation Leakage — Pass (one borderline carry-over, no new violations)

| Borderline | Status |
|---|---|
| FR46 names `httpx2.MockTransport` | Same status as the previous `requests-mock` reference — borderline-but-defensible (contributor contract / measurement method). Verdict: **acceptable**. |
| Architecture Notes names `httpx2` as the shared HTTP client | Properly compartmentalized into the explicitly-labeled `## Architecture Notes` section, not FR/NFR text. Not a leakage violation. |
| Journey 2 names "GitLab CI variable" + `SEMVERTAG_STRATEGY` | Journey-narrative surfaces are user-facing capability descriptions, not implementation. `SEMVERTAG_STRATEGY` is the documented config-schema contract. **Acceptable.** |

**Net new leakage:** 0.

#### Domain Compliance — Pass (N/A unchanged)

General/low classification preserved. No regulated-industry overlay introduced. Supply-chain security NFRs (NFR10–14) untouched.

#### Project-Type Compliance — Pass

All 4 `cli_tool` required sections present after the Config Schema rewrite:

| Section | Status |
|---|---|
| command_structure | Present (unchanged) |
| output_formats | Present; `--quiet` description updated for FR36 alignment |
| config_schema | Present — restructured to env+flags only for v1.0 with explicit v1.x deferral subsection; env-var table + provider-native fallbacks + deferred-collection-overrides subsection all present |
| scripting_support | Present (unchanged) |

#### SMART Quality — Pass (no regression)

All edited FRs retain ≥4 on every SMART criterion:

| FR | S | M | A | R | T | Notes |
|---|---|---|---|---|---|---|
| FR9 (revised) | 5 | 5 | 5 | 5 | 5 | Trim improved focus; v1.x deferral honestly modeled. |
| FR22 (extended) | 5 | 4 | 5 | 5 | 5 | "no extras packaging" clause adds testability; M=4 carryover for Provider-protocol-doc dependency. |
| FR23, FR24 (v1.x-tagged) | 5 | 5 | 5 | 5 | 5 | v1.x scope makes Attainable explicit; previously implicit. |
| FR25 (clarified) | 5 | 5 | 5 | 5 | 5 | "the only supported configuration surface in v1.0" sharpens the assertion. |
| FR27 (simplified) | 5 | 5 | 5 | 5 | 5 | 3-layer precedence with v1.x-slot note; cleaner than 4-layer with phantom file. |
| FR28 (forward-compat) | 5 | 5 | 5 | 5 | 5 | Conditional preamble is appropriate for a forward-compat policy; constraints are named and testable. |
| FR36 (clarified) | 5 | 5 | 5 | 5 | 5 | `--quiet --json` composition is explicitly testable. |
| FR46 (tool swap) | 5 | 5 | 5 | 5 | 5 | `httpx2.MockTransport` substitutes 1:1; capability shape unchanged. |

**Net:** still **100% ≥4 on every criterion** (the post-first-edit baseline).

#### Holistic Quality — Pass (5/5 retained)

- Document flow preserved across all 11 sections.
- Journey 2 rewrite retains voice-driven craft — Marina's narrative reads as concretely as before; the "five clicks per repo, no toolchain change, no config file to commit" beat reinforces the brand voice ("boring and reliable").
- Forward-compat language (FR28, FR27 parenthetical, FR9 parenthetical, Config Schema deferral subsection, Journey 2 footnote) is honestly modeled rather than hand-waved — explicit v1.x slots make the phased plan legible.
- Anti-goals + "Explicitly NOT in v1.0" surfaces still do active scoping work.

#### Completeness — Pass

- All 11 ## sections substantive.
- Zero template variables / placeholders / TODOs in the document.
- Frontmatter unchanged (still records 14 build steps, status `complete`).

### Re-Validated Quick Results

| Check | Pre-touch-ups | Post-touch-ups |
|---|---|---|
| Format Detection | BMAD Standard (6/6 core + 5 optional) | BMAD Standard (6/6 core + 5 optional) |
| Information Density | Pass (0 hits) | Pass (0 hits) |
| Brief Coverage | ~95% (Q1 fully resolved) | ~95% (Q1 resolved with phased delivery) |
| Measurability | Pass (76/76) | Pass (76/76) |
| Traceability | Pass (intact) | Pass (matrices updated, intact) |
| Implementation Leakage | Pass (3 borderline-defensible) | Pass (3 borderline-defensible; tool name updated) |
| Domain Compliance | N/A | N/A |
| Project-Type Compliance | 100% | 100% |
| SMART Quality | 100% ≥4 | 100% ≥4 |
| Holistic Quality | 5/5 | 5/5 |
| Completeness | 100% | 100% |

### New Findings / Observations

**Critical Issues:** 0
**Warnings:** 0
**Informational Observations:** 2

1. **FR13, FR16 phase-tag inconsistency (carried over, not introduced).** Both say "override … mappings via configuration," but with v1.0 having no file-based config layer, collection-shaped overrides aren't expressible as flat env vars. The Config Schema section's "Strategy-internal collection overrides (deferred)" subsection (prd.md:374-376) documents this explicitly and lists FR13/FR16 as v1.x-realized. The FR text itself does not carry a `*(v1.x)*` tag.

   *Recommendation (optional):* tag FR13 and FR16 with `*(v1.x)*` to match FR23/FR24's pattern, OR keep current state and rely on the Config Schema subsection + v1.x Growth Features bullet for disambiguation. Pre-existing minor inconsistency, not a touch-up regression.

2. **Brief was not synchronously updated.** Architecture-backlog item 7 listed "Brief" alongside PRD locations for the extras-removal cascade. The Brief (`product-brief-semvertag.md`) and distillate were not touched by the PRD-edit pass. If the Brief still mentions optional extras, a separate edit pass is warranted to keep upstream-document consistency.

   *Recommendation (optional):* scan the Brief and distillate for `[github]` / `[bitbucket]` / `optional extras` references and reconcile.

### Final Status

**Overall Status:** **Pass** (re-validated)

**Holistic Quality:** 5/5 — Excellent (preserved)

**Net delta from previous validation:** the 8 architecture-driven touch-ups (plus the Exec-Summary leftover) tighten the PRD's phasing story without regressing any of the 11 validation dimensions. Forward-compat language for v1.x is consistent across FRs, NFRs, Config Schema, Journey 2, and the Architecture Notes.

**Ready for:** architecture sign-off (the PRD-edit backlog in `architecture.md` is now marked applied) and epic/story breakdown.

---

## Re-Validation Pass — 2026-05-26 (FR13/FR16 v1.x tagging)

**Trigger:** Informational Observation #1 from the prior re-validation pass resolved — FR13 and FR16 explicitly tagged `*(v1.x)*` to match FR23/FR24's pattern.

**Scope:** Targeted delta — confirm FR13/FR16 tag consistency, traceability matrix update, no regression.

### Edits Verified

| Location | Before | After |
|---|---|---|
| FR13 (prd.md:511) | `User can override...` | `*(v1.x)* User can override... Requires the v1.x file-based config layer (FR23/FR24) — collection-shaped overrides are not expressible as flat env vars.` |
| FR16 (prd.md:514) | `User can extend or override...` | `*(v1.x)* User can extend or override... Requires the v1.x file-based config layer (FR23/FR24) — collection-shaped overrides are not expressible as flat env vars.` |
| Differentiation legs matrix (prd.md:624) | `FR11, FR12, FR14, FR15, FR16, FR3` | `FR11, FR12, FR14, FR15, FR3 (v1.0 with built-in mappings); FR13, FR16 (v1.x mapping overrides)` |
| Phase coverage v1.0 (prd.md:657) | `FR1–FR17, FR20–FR22, FR25–FR46 (excluding *v1.x*-tagged)` | `FR1–FR12, FR14, FR15, FR17, FR20–FR22, FR25–FR46 (i.e. all FRs not tagged *(v1.x)*)` |
| Phase coverage v1.x (prd.md:658) | `FR18, FR19 (...providers), FR23, FR24 (file-based...)` | `FR13, FR16 (collection-shaped mapping overrides), FR18, FR19 (...providers), FR23, FR24 (file-based...)` |

### Findings

| Check | Result |
|---|---|
| Anti-pattern scan (full doc) | 0 hits |
| FR/NFR count | 46 / 30 (unchanged) |
| Line count | 659 (unchanged) |
| Template/placeholder scan | 0 hits |
| FR13/FR16 tagging consistency | ✅ All 5 reference sites aligned (definitions, Config Schema subsection, Growth Features, Differentiation legs matrix, Phase coverage table) |
| Migration-aware-dual-mode leg still v1.0-realizable | ✅ FR11, FR12, FR14, FR15, FR3 remain v1.0; FR13/FR16 noted as v1.x mapping-overrides — built-in mappings cover the v1.0 dual-mode story |
| Journey 2 still v1.0-realizable | ✅ Marina's flow uses `SEMVERTAG_STRATEGY` (single-value env var, no collection override) — does not depend on FR13/FR16 |

**Brief Coverage impact:** none. The brief committed to "two strategies, one binary, one config change" — preserved by FR11 + the default mappings. Override-mapping customization was never a v1.0 brief requirement.

**SMART impact:** FR13 and FR16 lifted from Attainable=4-territory (when ambiguously v1.0-scoped) to fully attainable v1.x deliverables with named dependencies. **Net SMART score: still 100% ≥4 on every criterion**, with FR13/FR16 now scoring cleanly.

### Closed Observations

- ✅ **Observation #1** (FR13/FR16 phase-tag inconsistency) — **Resolved** by this pass.
- ⏳ **Observation #2** (Brief not synchronously updated) — still open; outside PRD-edit scope.

### Final Status

**Overall Status:** **Pass** (re-validated)
**Holistic Quality:** 5/5 — Excellent (preserved)
**Open Informational Observations:** 1 (was 2)

The PRD's phase tagging is now fully consistent across all v1.x-deferred FRs (FR13, FR16, FR18, FR19, FR23, FR24). Phase coverage table partitions the 46 FRs unambiguously into v1.0 (40 FRs) and v1.x (6 FRs).
