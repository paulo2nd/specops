"""Unit tests for the hybrid safety core (Feature 013, US2).

Four categories are detected from the diff; two (root-cause, public-contract) are
attested, not detected here. Detection is a pure function → fully unit-testable.
"""
from __future__ import annotations

from specops import safety


def test_migration_detected_by_path():
    d = safety.detect([("A", "db/migrations/003_add.sql")])
    assert [x.category for x in d] == [safety.MIGRATION]


def test_secret_detected_by_filename():
    for path in (".env", "config/app.pem", "deploy/id_rsa", "svc.credentials.json"):
        d = safety.detect([("A", path)])
        assert safety.SECRET in {x.category for x in d}, path


def test_dependency_detected_by_manifest():
    for path in ("pyproject.toml", "svc/package.json", "go.mod", "Cargo.lock"):
        d = safety.detect([("M", path)])
        assert safety.DEPENDENCY in {x.category for x in d}, path


def test_destructive_detected_on_deletion():
    d = safety.detect([("D", "src/module.py")])
    assert [x.category for x in d] == [safety.DESTRUCTIVE]


def test_public_contract_is_not_diff_detected():
    # public-contract is language-specific → attested, never flagged by detect (C1).
    d = safety.detect([("M", "src/public_api.py"), ("A", "openapi.yaml")])
    assert safety.PUBLIC_CONTRACT not in {x.category for x in d}
    assert safety.ROOT_CAUSE not in {x.category for x in d}


def test_clean_change_flags_nothing():
    assert safety.detect([("M", "src/util.py"), ("A", "README.md")]) == []


def test_overrides_add_to_floor_but_cannot_remove_it():
    # An override adds a public-ish path to `dependency`, but the migration FLOOR still fires.
    overrides = {safety.DEPENDENCY: ["*/deps.cfg"]}
    d = safety.detect(
        [("A", "svc/deps.cfg"), ("A", "db/migrations/1.sql")], overrides
    )
    cats = {x.category for x in d}
    assert safety.DEPENDENCY in cats  # override addition
    assert safety.MIGRATION in cats   # non-removable floor still applies


def test_empty_overrides_keep_floor():
    d = safety.detect([("A", "db/migrations/1.sql")], {})
    assert [x.category for x in d] == [safety.MIGRATION]


def test_detections_deduped_and_category_order_stable():
    d = safety.detect([("A", "db/migrations/1.sql"), ("A", "db/migrations/1.sql")])
    assert len(d) == 1
    cats = safety.categories(
        safety.detect([("D", "x.py"), ("A", "pyproject.toml"), ("A", "m/migrations/2.sql")])
    )
    # deterministic order follows DETECTED_CATEGORIES
    assert cats == [safety.MIGRATION, safety.DEPENDENCY, safety.DESTRUCTIVE]
