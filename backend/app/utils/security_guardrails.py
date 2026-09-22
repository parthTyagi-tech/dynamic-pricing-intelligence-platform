"""
backend/app/utils/security_guardrails.py

Centralized security guardrails for the pricing swarm (SEC-1..SEC-16).

Design notes (why this file looks the way it does):
- Every function here is pure / side-effect-scoped and independently unit-testable —
  none of them reach into Flask's `g` except the tenant-scoping helpers, which is the
  one place SEC-1/SEC-2 require it.
- Nothing in here talks to an LLM, a scraper, or the DB directly (besides the
  `atomic_ledger_write` contextmanager, which just wraps `db.session`). That keeps
  this module a dependency leaf so agents/routes/scrapers can all import it safely.
"""

from __future__ import annotations

import re
import ipaddress
import socket
from contextlib import contextmanager
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus, urlparse

from flask import g

from app.extensions import db


# =========================================================================
# SEC-1 / SEC-2 — Tenant scoping: organization_id must come from verified
# JWT claims (g.organization_id), never from the request body/query string.
# =========================================================================

class TenantScopeError(Exception):
    """Raised when a caller attempts to assert/derive tenant scope unsafely."""


def get_verified_organization_id() -> str:
    """
    The ONLY sanctioned way to get the current organization_id.

    Raises TenantScopeError if g.organization_id was never set — which happens
    only if a route is missing @jwt_required_with_user (or equivalent). This is
    intentionally loud: a silent None here is how cross-tenant leaks happen.
    """
    org_id = getattr(g, "organization_id", None)
    if not org_id:
        raise TenantScopeError(
            "organization_id is not present on g — this route is not going "
            "through an auth decorator that sets g.organization_id. Refusing "
            "to proceed rather than fall back to a client-supplied value."
        )
    return str(org_id)


def assert_no_client_supplied_org_id(payload: dict) -> None:
    """
    Defense in depth: if a request body/query dict contains an org id key,
    it is never trusted — but its presence is itself suspicious (a client
    trying to set its own tenant scope) and worth rejecting loudly rather
    than silently ignoring, since silent-ignore hides bugs in the frontend
    or an active tenant-spoofing attempt.
    """
    suspicious_keys = {"organization_id", "org_id", "organizationId", "orgId"}
    found = suspicious_keys.intersection(payload.keys())
    if found:
        raise TenantScopeError(
            f"Request payload attempted to set tenant-scope field(s) {found} "
            "directly. organization_id must only ever come from the verified "
            "JWT (g.organization_id)."
        )


def enforce_tenant_scope(query, model_class) -> Any:
    """
    Apply .filter_by(organization_id=<verified>) to a SQLAlchemy query.
    Use this instead of hand-writing `.filter_by(organization_id=...)` at
    call sites so there is exactly one code path that can get it wrong.
    """
    org_id = get_verified_organization_id()
    return query.filter_by(organization_id=org_id)


# =========================================================================
# SEC-4 — CSV / spreadsheet formula-injection defense.
# Applies to catalog_ingestion_service.py and any exported sheet.
# =========================================================================

_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> Any:
    """
    Neutralize formula injection in a single cell destined for CSV/XLSX,
    per SEC-4. Non-string values pass through untouched. A leading single
    quote forces spreadsheet applications to treat the cell as literal text
    instead of evaluating it as a formula.
    """
    if not isinstance(value, str):
        return value

    if value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value

    return value


def sanitize_csv_row(row: dict) -> dict:
    """Apply sanitize_csv_cell to every value in a row dict."""
    return {key: sanitize_csv_cell(val) for key, val in row.items()}


def sanitize_csv_rows(rows: Iterable[dict]) -> list[dict]:
    return [sanitize_csv_row(row) for row in rows]


# =========================================================================
# SEC-5 — Prompt injection neutralization for any user-controlled string
# (product name, description, attributes) before it enters an LLM prompt.
# =========================================================================

# Control characters except common whitespace (\n, \t handled separately below)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Instruction-override / role-hijack patterns. Case-insensitive, tolerant of
# extra whitespace. This list is deliberately pattern-based rather than a
# single fixed phrase list, since attackers vary punctuation/casing.
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"^\s*system\s*:",
    r"^\s*assistant\s*:",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"new\s+instructions\s*:",
    r"override\s+(your\s+)?(system\s+)?prompt",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"</?\s*(system|instructions?)\s*>",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)

# Common prompt delimiter tokens attackers use to try to "break out" of a
# user-data field and into the instruction portion of a prompt.
_DELIMITER_RE = re.compile(r"[`]{3,}|-{3,}|#{2,}|\[/?INST\]|<\|.*?\|>")

_MAX_SANITIZED_LENGTH = 2000


def sanitize_for_prompt(value: Optional[str], *, max_length: int = _MAX_SANITIZED_LENGTH) -> str:
    """
    Sanitize a user-controlled string before interpolating it into an LLM
    prompt (product name, description, brand, category_hint, etc).

    This does NOT try to be a perfect prompt-injection filter — no regex list
    is. It's a defense-in-depth layer; the real boundary is that the LLM
    output from agent debate turns is never used to grant more authority
    than "text for a human to review" (see SEC-10 sanity bound + HITL
    approval, which is the actual control that matters).
    """
    if not value:
        return ""

    text = str(value)

    # Strip control characters
    text = _CONTROL_CHAR_RE.sub(" ", text)

    # Strip prompt delimiter tokens attackers use to fake a new message/role
    text = _DELIMITER_RE.sub(" ", text)

    # Neutralize instruction-override phrases by flagging rather than
    # silently deleting (deletion can be reconstructed by an attacker
    # probing what gets removed; flagging is inert but visible in logs/audit).
    text = _INJECTION_RE.sub("[filtered]", text)

    # Collapse excess whitespace left behind by the substitutions above
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_length:
        text = text[:max_length] + "…"

    return text


def sanitize_product_for_prompt(product) -> dict:
    """
    Convenience wrapper for the common case: build a dict of sanitized
    product fields safe to interpolate into an agent prompt. Takes a
    Product model instance (duck-typed — works with any object exposing
    these attributes).
    """
    return {
        "name": sanitize_for_prompt(getattr(product, "name", None)),
        "brand": sanitize_for_prompt(getattr(product, "brand", None)),
        "description": sanitize_for_prompt(getattr(product, "description", None)),
        "category": sanitize_for_prompt(getattr(product, "category", None)),
        "category_hint": sanitize_for_prompt(getattr(product, "category_hint", None)),
        "normalized_query": sanitize_for_prompt(getattr(product, "normalized_query", None)),
    }


# =========================================================================
# SEC-6 / SEC-7 — Atomic ledgers: catalog price update + PriceHistory
# append + AuditLog record must all commit (or all roll back) together.
# =========================================================================

@contextmanager
def atomic_ledger_write():
    """
    Wrap a set of related writes (price update, PriceHistory append,
    AuditLog record) in a SAVEPOINT so they commit or roll back as one unit,
    without requiring the caller to manage nested-transaction bookkeeping.

    Usage:
        with atomic_ledger_write():
            product.current_price = new_price
            db.session.add(PriceHistory(...))
            db.session.add(AuditLog(...))
        # commits together on exit; on exception, the SAVEPOINT rolls back
        # and the exception propagates so the caller's job-state machine
        # (RecommendationJob) can record the failure.
    """
    nested = db.session.begin_nested()
    try:
        yield nested
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# =========================================================================
# SEC-10 — Sanity bounds: block auto-execution if |ΔPrice| > 50%,
# regardless of the agents' stated confidence.
# =========================================================================

SANITY_BOUND_PCT = 0.50


def check_sanity_bound(current_price: float, recommended_price: float) -> tuple[bool, float]:
    """
    Returns (sanity_bound_flagged, delta_pct).

    delta_pct is signed (positive = price increase, negative = decrease),
    expressed as a fraction of current_price (0.5 == 50%).

    Callers MUST check `sanity_bound_flagged` and, if True, force the
    recommendation into a human-approval-only state — auto-execution must
    be blocked unconditionally here, not merely "discouraged" by a lower
    confidence score. Confidence is a separate, unrelated signal and must
    never be allowed to override this check.
    """
    if current_price is None or current_price <= 0:
        # Can't compute a meaningful percentage delta from a zero/invalid
        # base price — treat as flagged so it always routes to a human.
        return True, float("inf")

    delta_pct = (recommended_price - current_price) / current_price

    flagged = abs(delta_pct) > SANITY_BOUND_PCT

    return flagged, delta_pct


def enforce_sanity_bound_or_raise(current_price: float, recommended_price: float) -> float:
    """
    Strict variant for call sites that should hard-fail rather than branch
    on a boolean (e.g. the auto-execute path, which should never be reached
    at all for an out-of-bounds delta). Returns delta_pct if within bounds.
    """
    flagged, delta_pct = check_sanity_bound(current_price, recommended_price)
    if flagged:
        raise ValueError(
            f"Recommended price {recommended_price} deviates {delta_pct:.1%} "
            f"from current price {current_price}, exceeding the "
            f"{SANITY_BOUND_PCT:.0%} sanity bound. Auto-execution is blocked; "
            "this recommendation must route to human approval."
        )
    return delta_pct


# =========================================================================
# SEC-12 — SSRF defense + safe URL/query encoding for outbound scraper
# requests and any redirect URL (e.g. competitor product_url, rollback link).
# =========================================================================

_ALLOWED_REDIRECT_SCHEMES = {"https"}

# RFC1918 / loopback / link-local / metadata-endpoint ranges that outbound
# scraper requests must never be allowed to resolve to, even if a marketplace
# response or query parameter tries to redirect there.
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local, incl. cloud metadata (169.254.169.254)
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def safe_encode_query_param(value: str) -> str:
    """SEC-12: percent-encode a value destined for a marketplace search URL."""
    return quote_plus(str(value))


def build_safe_search_url(base_url: str, query_params: dict) -> str:
    """
    Build a search URL with all query values safely encoded. base_url must
    already be one of the platform's known, hardcoded search endpoints
    (never derived from user input) — this function only protects the
    query string, not the host.
    """
    parsed = urlparse(base_url)
    if parsed.scheme not in _ALLOWED_REDIRECT_SCHEMES:
        raise ValueError(f"Refusing non-HTTPS scraper base_url: {base_url!r}")

    encoded_params = "&".join(
        f"{safe_encode_query_param(k)}={safe_encode_query_param(v)}"
        for k, v in query_params.items()
    )
    separator = "&" if parsed.query else "?"
    return f"{base_url}{separator}{encoded_params}" if encoded_params else base_url


def is_https_url(url: str) -> bool:
    try:
        return urlparse(url).scheme == "https"
    except Exception:
        return False


def resolves_to_blocked_ip(hostname: str) -> bool:
    """
    Resolve `hostname` and check whether ANY of its resolved addresses fall
    in a blocked (private/loopback/link-local) range. Used before a scraper
    or webhook client actually dials out, to catch DNS-rebinding attempts
    where a public-looking hostname resolves to an internal address.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # Cannot resolve — let the caller's HTTP client surface that error
        # naturally rather than us guessing; not itself a blocked condition.
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if any(ip in network for network in _BLOCKED_IP_NETWORKS):
            return True

    return False


def validate_outbound_url(url: str) -> str:
    """
    Full SEC-12 gate for any outbound request the scraper engine or webhook
    client is about to make (initial request AND every redirect hop).
    Raises ValueError if the URL is unsafe. Returns the url unchanged if OK.
    """
    if not is_https_url(url):
        raise ValueError(f"Refusing non-HTTPS outbound request: {url!r}")

    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError(f"Outbound URL has no resolvable hostname: {url!r}")

    if resolves_to_blocked_ip(hostname):
        raise ValueError(
            f"Refusing outbound request to {hostname!r} — resolves to a "
            "private/internal IP range (possible SSRF / DNS rebinding)."
        )

    return url


def validate_rollback_redirect_url(url: str) -> str:
    """
    Same HTTPS-only rule applied to the rollback-confirmation redirect built
    from the one-click email link, kept as a separate named function so the
    two call sites (scraper HTTP client vs. approval_routes rollback
    handler) can be audited/tested independently even though the underlying
    check is shared.
    """
    return validate_outbound_url(url)
