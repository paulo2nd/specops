# Delivery Revision

## Revision

## Work Item Reference

- Type: `feature` or `lightweight-fix`
- Path: `agents/features/<feature-name>/` or `agents/fixes/<fix-name>/`

## PR Reference

## PR Decision Mirror

- Decision Comment URL: ``
- Decision Comment Summary: ``

Every formal decision, including `APPROVED`, is born first in this artifact. When `Decision=APPROVED`, this block must point to the PR comment that mirrors the versioned decision and references the approved artifacts. A native `Approve` may exist for convenience, but it does not replace this record.

## Summary

## Non-Conformities

| # | Affected Artifact | Description | Severity | Expected Correction |
| :--- | :--- | :--- | :--- | :--- |

## Approved Items

- ``

When `Decision=APPROVED`, list only the versioned artifacts actually reconciled before the PR comment is published.

## Corrective Handoff

| Field | Value |
| :--- | :--- |
| Return Target | `implementer` or `fixer` |
| Scope Status | `approved_scope` or `scope_expanded_by_revision` |
| Authorized Files | `` |
| Expected Evidence Updates | `` |
| Handoff Criteria | `` |

`Authorized Files` define the initial corrective scope. If the implementation needs to expand scope within the same feature, the traceability of that expansion must appear in the artifacts listed under `Expected Evidence Updates`.

When `Decision=APPROVED`, this section must remain `N/A` and does not authorize a return to `implementer` or `fixer`.

When the reviewed item is a lightweight fix, `Authorized Files` may point to `fix.md`, the fix's `status.yaml`, and the strictly necessary product files. If any new exclusion trigger appears, the corrective package must require promotion to the full workflow instead of keeping the fix in the light lane.

## Required Actions

- ``

## Correction Evidence (Self-Report)

| # | NC Ref | Evidence (Tests/Logs/Links) | Commit Hash |
| :--- | :--- | :--- | :--- |

Section filled in by the `implementer` or `fixer` during the corrective round to prove the resolution of the Non-Conformities listed above.
