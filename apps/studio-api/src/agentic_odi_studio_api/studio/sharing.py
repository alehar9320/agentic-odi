"""Scoped, expiring, read-only share tokens for one artifact (issue #549).

The sidecar has no way to show one record to someone without handing over the
workspace. A share is the smallest honest capability: the owner mints a token
for exactly one record (an outcome, a segment, or a strategy), the reader gets
that record and its own evidence, and nothing else becomes reachable.

Design rules this module owns:

* The raw token is ``secrets.token_urlsafe(32)`` and is returned exactly once,
  at mint. The store keeps only its SHA-256 hash, so a reader of ``studio.db``
  cannot reconstruct the link.
* A read compares the stored hash in constant time and resolves only the named
  record from the local store. Memory, conversations, connectors, and the rest
  of the canvas are structurally out of reach — there is no query for them here.
* Unknown, expired, revoked, and malformed tokens are one failure. The caller
  turns it into a plain ``404``, so a probe cannot tell them apart.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from agentic_odi_core import ODIService
from agentic_odi_core.models import Evidence
from agentic_odi_core.repository import Repository

from agentic_odi_studio_api.studio.memory import Share, StudioMemory

#: The one artifact kinds a token may name. Nothing else is shareable.
ARTIFACT_KINDS: frozenset[str] = frozenset({"outcome", "segment", "strategy"})

DEFAULT_TTL_DAYS = 7
MAX_TTL_DAYS = 30

#: Namespaced so a token is recognisable in a log without being a secret.
TOKEN_PREFIX = "odi_sh_"  # nosec B105 - a token namespace, not a credential

#: Where a minted link points when nothing overrides it. #550 serves the page
#: that renders the payload; until then the link names the read endpoint.
DEFAULT_PUBLIC_BASE_URL = "http://127.0.0.1:8100"


class ShareError(ValueError):
    """Base class for recoverable share errors."""


class InvalidTTLError(ShareError):
    pass


class UnknownArtifactError(ShareError):
    """No record of that kind has that id."""


class ShareNotFoundError(ShareError):
    """No live share answers to that token.

    Deliberately the only read failure: unknown, expired, revoked, and malformed
    tokens all raise this, so the response cannot hint at which one it was.
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    """The only representation of a token that is ever stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MintedShare:
    """What the owner sees once: the raw token, and where the link points."""

    id: str
    token: str
    url: str
    expires_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "token": self.token,
            "url": self.url,
            "expires_at": self.expires_at,
        }


def public_base_url() -> str:
    """``AGENTIC_ODI_PUBLIC_BASE_URL`` when set, else the loopback default."""
    configured = os.environ.get("AGENTIC_ODI_PUBLIC_BASE_URL", "").strip()
    return configured.rstrip("/") if configured else DEFAULT_PUBLIC_BASE_URL


def _evidence_out(record: Evidence) -> dict[str, Any]:
    """One evidence record without ``raw``.

    The raw payload is the connector's original document and may carry a token
    or a customer's words that were never meant for a link; the shared view only
    needs the normalized fields.
    """
    return {
        "id": record.id,
        "source_name": record.source_name,
        "source_kind": record.source_kind,
        "item_type": record.item_type,
        "name": record.name,
        "content": record.content,
        "url": record.url,
        "outcome_id": record.outcome_id,
    }


class ShareService:
    """Mint, read, and revoke scoped capability tokens."""

    def __init__(
        self,
        service: ODIService,
        memory: StudioMemory,
        *,
        clock: Callable[[], datetime] = _now,
        base_url: str | None = None,
    ) -> None:
        self.service = service
        self.memory = memory
        #: Injectable so a test can move the clock past ``expires_at``.
        self._clock = clock
        self._base_url = base_url

    @property
    def repo(self) -> Repository:
        return self.service.repo

    def _base(self) -> str:
        return (self._base_url or public_base_url()).rstrip("/")

    # -- mint / revoke -----------------------------------------------------

    def mint(
        self,
        artifact_kind: str,
        artifact_id: str,
        ttl_days: int | None = None,
    ) -> MintedShare:
        """Create a token for one record. The raw token is returned once."""
        if artifact_kind not in ARTIFACT_KINDS:
            raise ShareError(
                f"unknown artifact kind '{artifact_kind}'. "
                f"Use one of: {', '.join(sorted(ARTIFACT_KINDS))}."
            )
        days = DEFAULT_TTL_DAYS if ttl_days is None else ttl_days
        if not 1 <= days <= MAX_TTL_DAYS:
            raise InvalidTTLError(f"ttl_days must be between 1 and {MAX_TTL_DAYS}")

        # Refuse to mint for a record that does not exist, so a link is never
        # created that could only ever 404.
        if self._resolve(artifact_kind, artifact_id) is None:
            raise UnknownArtifactError(f"no {artifact_kind} with id '{artifact_id}'")

        token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        expires_at = (self._clock() + timedelta(days=days)).isoformat()
        share = self.memory.create_share(
            token_hash=hash_token(token),
            artifact_kind=artifact_kind,
            artifact_id=artifact_id,
            expires_at=expires_at,
        )
        return MintedShare(
            id=share.id,
            token=token,
            url=f"{self._base()}/api/share/{token}",
            expires_at=expires_at,
        )

    def revoke(self, share_id: str) -> None:
        """Revoke a share. Idempotent; an unknown id is a not-found."""
        if not self.memory.revoke_share(share_id):
            raise ShareNotFoundError(share_id)

    def list_shares(self) -> list[Share]:
        """The owner's shares, without tokens."""
        return self.memory.list_shares()

    # -- read --------------------------------------------------------------

    def read(self, token: str) -> dict[str, Any]:
        """Return the one artifact the token names, and its own evidence.

        Every failure — malformed, unknown, expired, revoked, or a record that
        has since been deleted — is :class:`ShareNotFoundError`.
        """
        share = self._live_share(token)
        artifact = self._resolve(share.artifact_kind, share.artifact_id)
        if artifact is None:
            # The record was deleted after the share was minted. The capability
            # is now empty; say so the same way as any other dead token.
            raise ShareNotFoundError(token)
        self.memory.record_share_read(share.id)
        return {
            "artifact_kind": share.artifact_kind,
            "artifact": artifact.model_dump(mode="json"),
            "evidence": [_evidence_out(record) for record in self._evidence_for(share)],
        }

    def _live_share(self, token: str) -> Share:
        if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
            raise ShareNotFoundError(token)
        candidate = hash_token(token)
        share = self.memory.get_share_by_token_hash(candidate)
        # The lookup is indexed; the constant-time compare is the guard against
        # a stored hash being replayed as if it were a token.
        if share is None or not hmac.compare_digest(share.token_hash, candidate):
            raise ShareNotFoundError(token)
        if share.revoked_at is not None:
            raise ShareNotFoundError(token)
        if datetime.fromisoformat(share.expires_at) <= self._clock():
            raise ShareNotFoundError(token)
        return share

    # -- resolution --------------------------------------------------------

    def _resolve(self, artifact_kind: str, artifact_id: str) -> Any | None:
        if artifact_kind == "outcome":
            return self.repo.get_outcome(artifact_id)
        if artifact_kind == "segment":
            return self.repo.get_segment(artifact_id)
        if artifact_kind == "strategy":
            return self.repo.get_strategy(artifact_id)
        return None

    def _outcome_ids_for(self, share: Share, artifact: Any) -> list[str]:
        if share.artifact_kind == "outcome":
            return [artifact.id]
        if share.artifact_kind == "segment":
            return list(artifact.outcome_ids)
        if share.artifact_kind == "strategy" and artifact.segment_id:
            segment = self.repo.get_segment(artifact.segment_id)
            return list(segment.outcome_ids) if segment is not None else []
        return []

    def _evidence_for(self, share: Share) -> list[Evidence]:
        artifact = self._resolve(share.artifact_kind, share.artifact_id)
        if artifact is None:
            return []
        seen: dict[str, Evidence] = {}
        for outcome_id in self._outcome_ids_for(share, artifact):
            for record in self.service.list_evidence(outcome_id=outcome_id):
                seen.setdefault(record.id, record)
        return list(seen.values())


__all__ = [
    "ARTIFACT_KINDS",
    "DEFAULT_PUBLIC_BASE_URL",
    "DEFAULT_TTL_DAYS",
    "MAX_TTL_DAYS",
    "TOKEN_PREFIX",
    "InvalidTTLError",
    "MintedShare",
    "ShareError",
    "ShareNotFoundError",
    "ShareService",
    "UnknownArtifactError",
    "hash_token",
    "public_base_url",
]
