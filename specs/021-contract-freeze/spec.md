# Feature Specification: Contract Freeze for 1.0

**Feature Branch**: `021-contract-freeze`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Freeze the adopter-facing contracts for 1.0: publish the stability policy for persisted formats, JSON envelopes, and exit codes; add contract tests that lock the frozen shapes; define the post-1.0 versioning and migration obligations; and cut 1.0.0-rc once the real-usage criterion is met — no new capabilities, no alias removals."

## Clarifications

### Session 2026-07-28

- Q: The exit-code contract in code is `0`=success, `1`=blocking gate/REJECTED, `2`=infra/data/usage error, but constitution Principle VI names only `0`/`1`. What does the freeze lock, and does it amend the constitution? → A: **Freeze the actual three-value scheme (`0`/`1`/`2`) and amend Principle VI in the same change set** to document exit `2`, so the governing principle and the frozen contract agree. (This also corrects the swapped `1`/`2` meanings previously written in Assumptions.)
- Q: JSON versioning is heterogeneous — several report outputs carry `output_version: 1`, but the base command-result envelope (class/status/exit) has none. What does the freeze do about the base envelope? → A: **Add an explicit `output_version` to the base command-result envelope** (the feature's single sanctioned additive code delta) so every `--json` consumer has one detectable version signal; existing per-report `output_version` fields are retained unchanged.
- Q: Which adopter-facing surfaces are frozen at 1.0 versus still-evolving? → A: **All seven named surfaces are frozen.** The FR-003 sweep only adds any *additional* surface it discovers, which defaults to **frozen** unless a stated reason records it as still-evolving.
- Q: The rc tag is gated on the release strategy's "real-usage criterion", which the spec doesn't define. What is this feature's relationship to it? → A: **Reference only — external decision.** This feature neither defines nor evaluates the criterion; declaring it met is the release owner's judgment. The freeze, policy, and contract tests land independently of the rc tag.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An adopter can rely on the frozen surfaces (Priority: P1)

An adopter who builds automation against SpecOps — scripts that parse the JSON output envelope, CI jobs that branch on exit codes, tools that read `status.yaml`, `specops.json`, `lane.yaml`, gate-profile files, or ingest findings through the input contract — can read one published stability policy that tells them, for each surface, whether it is frozen, what an additive (non-breaking) change to it looks like, and how any breaking change would be versioned and announced. Every surface named as frozen carries a documented stability class so the adopter knows exactly what they are allowed to bind to before 1.0.

**Why this priority**: this is the feature's headline deliverable and the precondition for cutting a 1.0.0-rc. The whole point of a 1.0 is a promise adopters can build on; without a written, per-surface stability policy there is nothing to freeze and nothing to test against. It is the one outcome an adopter can consume directly.

**Independent Test**: can be fully tested by reading the published stability policy and confirming that every adopter-facing surface (persisted formats `specops.json`, `status.yaml`, `lane.yaml`, gate-profile files; the JSON output envelopes; the exit-code contract; the findings-input contract) appears with an explicit stability class and a stated additive-change rule — with no surface adopters currently bind to left unclassified.

**Acceptance Scenarios**:

1. **Given** the published stability policy, **When** an adopter looks up any of the named surfaces, **Then** it carries an explicit stability class (frozen vs. still-evolving) and a one-line statement of what additive change means for that surface.
2. **Given** the set of surfaces adopters can observe today (persisted files, JSON envelopes, exit codes, findings-input contract), **When** they are cross-checked against the policy, **Then** every one of them is classified — none is silently omitted.
3. **Given** the policy, **When** it is read for any frozen surface, **Then** it states how a future breaking change to that surface would be versioned and announced (e.g. schema-version bump, envelope version field, deprecation window).

---

### User Story 2 - A breaking change to a frozen surface is caught mechanically (Priority: P1)

A maintainer who accidentally changes a frozen shape — renames or drops a key in the JSON output envelope, alters the meaning of an exit code, changes a persisted-format field without bumping its version, or breaks the findings-input contract — has that change fail the test suite immediately, with a message that names the surface and the broken guarantee. The freeze is not a document that can silently drift from the code; it is enforced by contract tests that assert the exact frozen shapes.

**Why this priority**: a stability policy that is only prose rots the moment code changes. The mechanical lock is what makes the freeze a real guarantee rather than an aspiration, and it is equally essential to a trustworthy 1.0 — hence also P1. It protects every adopter in User Story 1 continuously, not just at release time.

**Independent Test**: can be tested by introducing a deliberate breaking change to each frozen surface (drop an envelope key, change an exit code's meaning, mutate a persisted field without a version bump, alter the findings-input contract) on a throwaway branch and confirming the corresponding contract test fails with a message identifying the surface; and, conversely, confirming a correctly versioned change does not falsely fail.

**Acceptance Scenarios**:

1. **Given** the contract tests, **When** a key is removed or renamed in a frozen JSON output envelope, **Then** a contract test fails and names the affected envelope.
2. **Given** the contract tests, **When** a persisted-format field is changed without an accompanying schema/format version bump, **Then** a contract test fails and identifies the format and the unversioned change.
3. **Given** the contract tests, **When** an exit code's documented meaning changes, **Then** a contract test fails.
4. **Given** the contract tests, **When** a change is additive and correctly versioned per the policy, **Then** the contract tests pass (no false positive).

---

### User Story 3 - Post-1.0 evolution has defined obligations (Priority: P2)

A maintainer planning a change after 1.0 can read a versioning-and-migration policy that tells them what they owe for each kind of change: which persisted-format changes require a schema-version bump and a forward migration (with a migration test), what the output-envelope version field means and when it must change, and how the Feature 017 alias/deprecation discipline extends to any future rename. The policy makes the difference between an allowed additive change and a breaking change unambiguous, and ties each breaking change to a concrete obligation.

**Why this priority**: the freeze is only half the contract; the other half is knowing how to evolve safely without breaking adopters. Valuable and necessary for 1.0, but it governs *future* work rather than being consumed at release time, so it ranks below the freeze itself and its enforcement.

**Independent Test**: can be tested by confirming the policy states, for each persisted format, the version-bump-plus-migration obligation and points at the existing migration-test mechanism; defines the semantics of the output-envelope version field (when it must increment); and references the Feature 017 alias/deprecation window as the required discipline for any post-1.0 rename.

**Acceptance Scenarios**:

1. **Given** the versioning policy, **When** a maintainer plans a persisted-format change, **Then** the policy tells them whether it is additive or breaking and, if breaking, requires a version bump plus a forward migration covered by a migration test.
2. **Given** the versioning policy, **When** the output-envelope version field is consulted, **Then** its semantics — what it identifies and the conditions under which it must increment — are stated unambiguously.
3. **Given** the versioning policy, **When** a post-1.0 rename of any user-facing surface is planned, **Then** the policy requires the same alias-plus-deprecation-window discipline established by Feature 017.

---

### User Story 4 - The release is cut and documented when the criterion is met (Priority: P3)

A maintainer preparing the release finds the CHANGELOG and both the English and Portuguese documentation stating the contract freeze — which surfaces are frozen and where the stability policy lives — kept behaviorally equivalent across the two languages. The 1.0.0-rc is cut only once the real-usage criterion of the milestone-based release strategy is satisfied, and the documentation makes the freeze discoverable to any adopter reading the release notes.

**Why this priority**: valuable release-hygiene work that surfaces the freeze to adopters and records it in the changelog, but it is the packaging of the substance delivered by the earlier stories rather than the substance itself, so it ranks last. The rc tag is gated on an external readiness criterion, not on this feature's code.

**Independent Test**: can be tested by confirming the CHANGELOG records the freeze and points to the stability policy, that the EN and PT documentation both describe the freeze and remain behaviorally equivalent, and that the rc is cut only when the release strategy's real-usage criterion is documented as met (not automatically by this feature).

**Acceptance Scenarios**:

1. **Given** the merged change set, **When** the CHANGELOG is read, **Then** it records the contract freeze and links to the stability policy.
2. **Given** the EN and PT documentation, **When** they are compared, **Then** both describe the freeze and the frozen surfaces and remain behaviorally equivalent.
3. **Given** the release strategy's real-usage criterion, **When** it is documented as satisfied, **Then** the 1.0.0-rc is cut with the stability policy published; until then, the freeze and tests land but the rc is not forced by this feature.

### Edge Cases

- A surface adopters bind to today that is **not** in the roadmap's named list (`specops.json`, `status.yaml`, `lane.yaml`, gate-profile files, JSON output envelopes, exit codes, findings-input contract) — the classification sweep MUST surface it and either freeze it or explicitly record it as still-evolving; nothing observable is left unclassified by omission.
- A persisted format that is currently versioned (the ledger is schema v7; the findings-input contract carries a contract version) — the freeze pins the *current* version as the frozen baseline and defines the bump obligation forward; it does not rewrite existing migration history.
- An **additive** change to a frozen surface after the freeze (a new optional key, a new gate-profile field) — must be allowed by the policy and must NOT trip the contract tests, so the tests assert presence/shape of the frozen fields without forbidding new optional ones.
- A deprecated alias still inside its window (e.g. `specops review` from Feature 017) — freezing contracts MUST NOT remove it; alias removal is explicitly out of scope for this feature.
- The **base** command-result envelope has no explicit version field today (several richer report outputs already carry `output_version: 1`) — the freeze adds an explicit `output_version` to the base envelope (an additive change under the policy) and the policy defines the increment semantics for it and for the existing per-report version fields.
- A JSON envelope that is intentionally allowed to carry command-specific extra fields — the contract test must lock the *stable* envelope keys (class/status/exit and any documented common fields) without forbidding documented per-command extensions.
- The real-usage criterion is **not** yet met at merge time — the freeze, the policy, and the contract tests still land; only the rc tag waits. This feature must not force a premature 1.0.0-rc.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A published stability policy MUST enumerate every adopter-facing surface — the persisted formats `specops.json`, `status.yaml`, `lane.yaml`, and gate-profile files; the JSON output envelopes; the exit-code contract; and the findings-input contract — and MUST classify all seven as **frozen** at 1.0, each with a one-line additive-change rule. (The "still-evolving" class is reserved for any *additional* surface the FR-003 sweep may surface.)
- **FR-002**: The policy MUST define, for each frozen surface, what constitutes an **additive (non-breaking)** change versus a **breaking** change, so the distinction is unambiguous for a future maintainer.
- **FR-003**: All seven surfaces named in FR-001 are frozen at 1.0. A classification sweep MUST identify any *additional* surface adopters can currently observe that is not in that named list; a newly-found surface defaults to **frozen** unless a stated reason records it as still-evolving. No observable surface may be left unclassified.
- **FR-004**: Contract tests MUST lock the frozen shapes of the persisted formats and the JSON output envelopes at schema level, asserting the presence and shape of every frozen field and failing on any unversioned removal, rename, or type change of a frozen field.
- **FR-005**: Contract tests MUST lock the three-value exit-code contract — `0` success, `1` blocking gate result / review `REJECTED`, `2` infrastructure/data/usage error — failing if the documented meaning of any of the three codes changes.
- **FR-006**: Contract tests MUST lock the findings-input contract shape and its contract version, failing on any unversioned breaking change to it.
- **FR-007**: The contract tests MUST allow correctly versioned and additive changes to pass (no false positive): a new optional key, a new documented per-command envelope field, or a properly version-bumped persisted format MUST NOT fail the frozen-shape tests.
- **FR-008**: A versioning-and-migration policy MUST state the obligations for post-1.0 evolution: which persisted-format changes require a schema/format version bump and a forward migration covered by a migration test, reusing the existing ledger migration-test mechanism rather than inventing a new one.
- **FR-009**: The base command-result envelope (the shared `--json` object carrying class/status/exit) MUST gain an explicit `output_version` field — the feature's single sanctioned additive code delta — so every `--json` consumer has one detectable version signal; the existing per-report `output_version` fields (trace, handoff, context, gate-profile outputs) are retained unchanged. The policy MUST define the semantics of each version field — what it identifies and the exact conditions under which it must increment.
- **FR-010**: The policy MUST require that any post-1.0 rename of a user-facing surface follow the Feature 017 alias-plus-deprecation-window discipline (ship the alias, keep it for its defined window, remove no earlier than the next MINOR and never in a patch).
- **FR-011**: The CHANGELOG MUST record the contract freeze and link to the stability policy; the English and Portuguese documentation MUST both describe the freeze and the frozen surfaces and remain behaviorally equivalent.
- **FR-012**: This feature MUST add no new user-facing capability, command, or option, and MUST NOT remove any deprecated alias; its deliverables are the policy, the contract tests, and the documentation. The only sanctioned code delta is adding the explicit `output_version` field to the base command-result envelope (FR-009), governed by the policy as an additive change.
- **FR-013**: The 1.0.0-rc MUST be cut only once the milestone-based release strategy's real-usage criterion is documented as satisfied by the release owner. This feature does **not** define or evaluate that criterion — it only references it; the freeze, policy, and contract tests MUST land independently of that tag and MUST NOT force a premature rc.
- **FR-014**: Constitution Principle VI (Exit Codes as Gates), which today names only `0`/`1`, MUST be amended in the same change set to document the frozen three-value scheme (adding exit `2` for infrastructure/data/usage error), so the governing principle and the frozen exit-code contract (FR-005) agree.

### Key Entities

- **Adopter-facing surface**: any shape an external consumer binds to — a persisted file (`specops.json`, `status.yaml`, `lane.yaml`, gate-profile files), a JSON output envelope, an exit code, or the findings-input contract.
- **Stability class**: the per-surface designation (frozen vs. still-evolving) together with its additive-change rule, published in the stability policy.
- **Stability policy**: the published document that classifies every surface and states the additive-vs-breaking distinction and the announcement discipline for breaking changes.
- **Versioning-and-migration policy**: the published rules for post-1.0 evolution — version-bump-plus-migration obligations for persisted formats, output-envelope version semantics, and the alias/deprecation discipline for renames.
- **Contract test**: a schema-level assertion that locks a frozen surface's shape and fails on any unversioned breaking change while permitting additive and correctly versioned changes.
- **Frozen baseline**: the current shape/version of each surface pinned as the starting point the freeze protects going forward — the ledger schema (v7), the findings-input contract version, the three-value exit-code scheme (`0`/`1`/`2`), and the base command-result envelope with its newly-added `output_version`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of adopter-facing surfaces — the seven named in FR-001 plus any additional surface found by the FR-003 sweep — carry an explicit stability class in the published policy; the count of observable-but-unclassified surfaces is zero.
- **SC-002**: Every frozen surface has at least one contract test locking its shape; the count of frozen surfaces without a corresponding contract test is zero.
- **SC-003**: A deliberate breaking change injected into each frozen surface (envelope key drop/rename, exit-code meaning change, unversioned persisted-field change, findings-input contract break) causes at least one contract test to fail and name the surface — demonstrated for every frozen surface.
- **SC-004**: A correctly versioned or additive change to each frozen surface (new optional key, version-bumped format) passes the contract tests with zero false failures.
- **SC-005**: The versioning-and-migration policy states, for every persisted format, its bump-plus-migration obligation and points at the existing migration-test mechanism; the output-envelope version semantics and the rename alias/deprecation discipline are both stated.
- **SC-006**: The CHANGELOG records the freeze and links to the policy; the EN and PT documentation both describe the freeze and remain behaviorally equivalent, verified by manual EN/PT review and by the presence of the freeze description in both README entry points (`README.md` and `README.pt-br.md`). No automated bilingual-equivalence check exists in the repository, and this feature does not build one.
- **SC-007**: The full test suite — including the new contract tests — passes at the repository thresholds on every CI platform, with no schema bump forced by this feature (the frozen baselines are pinned as-is).
- **SC-008**: The 1.0.0-rc is cut only after the real-usage criterion is documented as met by the release owner; at merge time the freeze, policy, and tests are present and the rc tag is not forced. This feature contains no code or test that defines or evaluates the criterion.
- **SC-009**: Constitution Principle VI documents the three-value exit-code scheme (adds exit `2` for infrastructure/data/usage error), landing in the same change set as the exit-code contract test; the count of exit codes named in the principle matches the count locked by the contract test (three).
- **SC-010**: The base command-result envelope carries an explicit `output_version`, locked by a contract test; the existing per-report `output_version` fields are unchanged (count of report outputs whose version field changed value or shape is zero).

## Assumptions

- The roadmap's named surface list (`specops.json`, `status.yaml`, `lane.yaml`, gate-profile files, JSON output envelopes, exit codes, findings-input contract) is the authoritative starting set; the FR-003 sweep is a completeness check over it, not a signal that the list is expected to be wrong.
- The current versions of already-versioned surfaces are the frozen baselines: the ledger is schema v7 and the findings-input contract carries its current contract version; this feature pins them, it does not bump them.
- The exit-code contract is the existing three-value scheme actually emitted by the code — `0` success, `1` blocking gate result / review `REJECTED`, `2` infrastructure/data/usage error; the freeze locks these meanings. Constitution Principle VI currently names only `0`/`1`, so it is amended in the same change set to document exit `2` (FR-014).
- The JSON output envelope is the shared command-result object every `specops` command renders under `--json`; the freeze locks its stable common keys while permitting documented per-command extensions.
- The Feature 017 alias/deprecation window is the established discipline for renames and is reused verbatim by the post-1.0 policy; no new deprecation mechanism is invented.
- The existing ledger migration-test mechanism is the sanctioned way to satisfy the forward-migration obligation; the versioning policy references it rather than defining a parallel mechanism.
- Cutting the 1.0.0-rc is gated on the milestone-based release strategy's real-usage criterion, which is an external human judgment recorded in the release process — not a condition this feature's code can assert — so the rc tag may follow the merge rather than coincide with it. This feature neither defines nor evaluates the criterion; it only references it.
- No Self-Application (constitution) continues to hold: the contract tests exercise the frozen shapes against fixtures and the feature's own test artifacts, never by running `specops` against this repository.
- This is a freeze, not a redesign: no new capability, no alias removal, and no behavior change to any command; the only sanctioned code change is adding an explicit `output_version` to the base command-result envelope (an additive change under the policy), and the only sanctioned governance change is amending constitution Principle VI to document the frozen exit-`2` code (FR-014).
