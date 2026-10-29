"""Tests for the ODI error hierarchy."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from agentic_odi_core.errors import (
    ConflictError,
    NotFoundError,
    OdiError,
    RateLimitError,
    SerializationError,
    StoreError,
    ValidationError,
    error_status,
)
from agentic_odi_core.services import (
    CustomerOutcomeNotFoundError,
    EvidenceNotFoundError,
    JobNotFoundError,
    OutcomeNotFoundError,
    StepNotFoundError,
    ValueOutOfRangeError,
)

ALL_ERROR_TYPES = (
    ValidationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    StoreError,
    SerializationError,
)


@pytest.mark.parametrize("error_type", ALL_ERROR_TYPES)
def test_every_error_type_is_an_odi_error(error_type: type[OdiError]) -> None:
    """Every dedicated error type is catchable through the common base class."""
    assert issubclass(error_type, OdiError)
    assert issubclass(error_type, Exception)


@pytest.mark.parametrize("error_type", ALL_ERROR_TYPES)
def test_every_error_type_can_be_instantiated(error_type: type[OdiError]) -> None:
    """Every dedicated error type is constructible with its documented arguments."""
    err: OdiError
    if error_type is NotFoundError:
        err = error_type("abc", "job")
    elif error_type is RateLimitError:
        err = error_type("slow down", retry_after=1.5)
    else:
        err = error_type("boom")
    assert isinstance(err, OdiError)
    assert str(err)


def test_error_status_maps_each_type() -> None:
    assert error_status(ValidationError("bad")) == 400
    assert error_status(NotFoundError("abc", "job")) == 404
    assert error_status(ConflictError("clash")) == 409
    assert error_status(RateLimitError("slow down")) == 429
    assert error_status(StoreError("disk")) == 500
    assert error_status(SerializationError("wire")) == 502


def test_error_status_falls_back_to_500_for_unknown_odi_error() -> None:
    class MysteryError(OdiError):
        pass

    assert error_status(MysteryError("?")) == 500


def test_not_found_error_exposes_resource_id_and_kind() -> None:
    err = NotFoundError("abc-123", "job")

    assert err.resource_id == "abc-123"
    assert err.kind == "job"
    assert "job not found: abc-123" in str(err)


def test_rate_limit_error_exposes_retry_after() -> None:
    err = RateLimitError("slow down", retry_after=2.5)

    assert err.retry_after == 2.5
    assert str(err) == "slow down"


def test_validation_error_is_also_a_value_error() -> None:
    """The ODI validation error stays catchable as a plain ``ValueError``."""
    assert issubclass(ValidationError, ValueError)
    with pytest.raises(ValueError):
        raise ValidationError("bad input")


@pytest.mark.parametrize(
    ("error_type", "resource_id", "kind"),
    [
        (JobNotFoundError, "job-1", "job"),
        (StepNotFoundError, "step-1", "step"),
        (OutcomeNotFoundError, "outcome-1", "outcome"),
        (CustomerOutcomeNotFoundError, "co-1", "customer_outcome"),
        (EvidenceNotFoundError, "ev-1", "evidence"),
    ],
)
def test_domain_not_found_errors_join_the_hierarchy(
    error_type: Callable[[str], NotFoundError], resource_id: str, kind: str
) -> None:
    """Domain not-found errors are catchable as ``NotFoundError`` and ``OdiError``."""
    err = error_type(resource_id)

    assert isinstance(err, NotFoundError)
    assert isinstance(err, OdiError)
    assert err.resource_id == resource_id
    assert err.kind == kind
    assert error_status(err) == 404


def test_value_out_of_range_error_is_a_validation_error() -> None:
    err = ValueOutOfRangeError()

    assert isinstance(err, ValidationError)
    assert isinstance(err, OdiError)
    assert error_status(err) == 400
