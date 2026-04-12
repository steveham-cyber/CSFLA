"""
HMAC-SHA256 pseudonymisation.

Algorithm: pseudo_id = Base64Url(HMAC-SHA256(key, str(member_id)))

This module implements the algorithm from Data Architecture Spec v0.2 Section 5.
In production the key is retrieved from Azure Key Vault — the raw key never
leaves the vault. In tests, TEST_PSEUDONYMISATION_KEY provides a fixed test key
that is never used in production.
"""

from __future__ import annotations

import base64
import hmac
import hashlib


def compute_pseudo_id(member_id: str | int, key: str) -> str:
    """
    Compute a stable, irreversible pseudonymous identifier.

    Properties:
      - Stability: same member_id + key always produces the same output.
      - Uniqueness: different member_ids produce different outputs (HMAC collision
        resistance).
      - Irreversibility: no function can recover member_id from pseudo_id without
        the key.
      - Key isolation: the test key is a fixed known string, never the production key.

    Args:
        member_id: Raw member identifier from the membership export.
        key: HMAC secret key bytes encoded as a UTF-8 string.
             Production: retrieved from Azure Key Vault at pipeline startup.
             Tests: TEST_PSEUDONYMISATION_KEY environment variable.

    Returns:
        URL-safe Base64 string (no padding) — the pseudonymous identifier.
    """
    digest = hmac.new(
        key.encode("utf-8"),
        str(member_id).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
