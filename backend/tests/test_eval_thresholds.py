"""Turns the eval harness into a regression floor.

Measured on the rule-based path (no API key, no network), the numbers at the
time these thresholds were set were:

    field accuracy   95.9%   (was 86.3%)
    status accuracy  100%    (was 81.2%)
    wrong            0       (was 2)
    hallucinated     0       (was 1)

The floors sit slightly below the measured values so ordinary refactors do not
trip them, but any real regression does. If you improve the extractor, raise
them.
"""
import pytest

from tests.eval.runner import HALLUCINATED, WRONG, report, run_eval

FIELD_ACCURACY_FLOOR = 0.93
STATUS_ACCURACY_FLOOR = 1.0


@pytest.fixture(scope="module")
def rep():
    return report(run_eval(use_ai=False))


def test_field_accuracy_does_not_regress(rep):
    assert rep["field_accuracy"] >= FIELD_ACCURACY_FLOOR, (
        f"field accuracy fell to {rep['field_accuracy']:.1%}; "
        f"run `python -m tests.eval.runner` for the per-field breakdown"
    )


def test_eligibility_status_accuracy_does_not_regress(rep):
    assert rep["status_accuracy"] >= STATUS_ACCURACY_FLOOR, (
        f"status accuracy fell to {rep['status_accuracy']:.1%}; "
        f"run `python -m tests.eval.runner` for the mismatches"
    )


def test_no_field_is_extracted_wrong(rep):
    """A WRONG value is the worst outcome: it silently misleads the operator,
    where a null at least surfaces as a missing field."""
    assert rep["field_counts"][WRONG] == 0


def test_nothing_is_hallucinated(rep):
    """An invented fact changes which entitlements a citizen is offered."""
    assert rep["field_counts"][HALLUCINATED] == 0


def test_confidence_is_low_when_the_input_says_nothing(rep):
    assert rep["confidence_violations"] == []
