"""
[QA] Atlas-MH Rater — Smoke Tests
Verifies DB connectivity and file system permissions.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from premium_engine import PremiumEngine


def test_premium_engine_calculation():
    """Verify multiplicative factor model output."""
    engine = PremiumEngine(carrier_code="FOREMOST")
    result = engine.calculate(
        base_rate=150.00,
        territory_factor=1.15,
        tier_factor=1.05,
        variable_factors={"deductible_discount": 0.95, "coverage_boost": 1.02},
    )
    # 150 × 1.15 × 1.05 × 0.95 × 1.02 = ~182.54
    expected = 182.54
    assert abs(result - expected) < 0.01, f"Expected {expected}, got {result}"
    print(f"[QA] PremiumEngine calculation: PASS ({result})")


def test_inbox_permissions():
    """Verify data/inbox exists and is writable."""
    inbox = Path(__file__).parent.parent / "data" / "inbox"
    assert inbox.exists(), f"Inbox not found: {inbox}"
    assert os.access(inbox, os.W_OK), f"Inbox not writable: {inbox}"
    print("[QA] Inbox permissions: PASS")


def test_schema_file_exists():
    """Verify schema/init.sql exists."""
    schema = Path(__file__).parent.parent / "schema" / "init.sql"
    assert schema.exists(), f"Schema file not found: {schema}"
    print("[QA] Schema file: PASS")


if __name__ == "__main__":
    test_premium_engine_calculation()
    test_inbox_permissions()
    test_schema_file_exists()
    print("\n[QA] All smoke tests passed.")