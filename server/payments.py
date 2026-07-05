# -*- coding: utf-8 -*-
"""PAYMENTS — the Stripe seam for paid pulse launches (2026-06-22).

Keys are read from server/.env.local (LUMI_STRIPE_SECRET_KEY /
LUMI_STRIPE_PUBLISHABLE_KEY / LUMI_STRIPE_WEBHOOK_SECRET), the SAME "always on"
pattern as ANTHROPIC_API_KEY (app._load_local_env). A real env var always wins.

Deliberately dependency-light: we talk to Stripe over httpx (already a project
dep) and verify webhook signatures with stdlib hmac — no `stripe` SDK to install.

GRACEFUL FALLBACK: when no secret key is configured, is_configured() is False and
the checkout route returns a clear "payments not enabled" state. The dev
"simulate paid" path (admin-guarded) then drives the rest of the launch flow so
build -> review -> approve -> [pay] -> open -> respond -> report is fully testable
before real keys exist. This is the designed floor, NOT a bug — mirrors the AI
fallback.
"""
import hashlib
import hmac
import json
import os
import time

import httpx

STRIPE_API = "https://api.stripe.com/v1"


def secret_key():
    return os.environ.get("LUMI_STRIPE_SECRET_KEY", "").strip()


def publishable_key():
    return os.environ.get("LUMI_STRIPE_PUBLISHABLE_KEY", "").strip()


def webhook_secret():
    return os.environ.get("LUMI_STRIPE_WEBHOOK_SECRET", "").strip()


def is_configured():
    """True once a Stripe secret key is present — gates the real checkout route."""
    return bool(secret_key())


def mode():
    """'live' | 'test' | 'off' — surfaced to staff so they never confuse a test
    launch for a real one. Stripe encodes the mode in the key prefix."""
    k = secret_key()
    if not k:
        return "off"
    return "live" if k.startswith("sk_live") else "test"


def create_checkout_session(*, amount_pence, currency, product_name,
                            success_url, cancel_url, client_reference_id, metadata=None):
    """Create a Stripe Checkout Session (mode=payment) for a one-off launch fee.
    Returns (session_id, checkout_url). Raises RuntimeError('payments_not_configured')
    when no key is set, or httpx.HTTPStatusError on a Stripe error."""
    if not is_configured():
        raise RuntimeError("payments_not_configured")
    data = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": client_reference_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][unit_amount]": str(int(amount_pence)),
        "line_items[0][price_data][product_data][name]": product_name,
        # a proper VAT invoice for the B2B charge (Stripe applies tax per the
        # account's tax settings); the customer also gets an emailed receipt
        "invoice_creation[enabled]": "true",
    }
    # opt-in automatic VAT once Stripe Tax is configured on the account
    if os.environ.get("LUMI_STRIPE_AUTOMATIC_TAX", "").lower() == "on":
        data["automatic_tax[enabled]"] = "true"
    for k, v in (metadata or {}).items():
        data["metadata[%s]" % k] = str(v)
    resp = httpx.post(STRIPE_API + "/checkout/sessions", data=data,
                      auth=(secret_key(), ""), timeout=20)
    resp.raise_for_status()
    body = resp.json()
    return body["id"], body["url"]


def get_checkout_session(session_id):
    """Fetch a Checkout Session from Stripe (for reconciling the success redirect
    instead of trusting the URL). Returns the parsed session dict, or None when
    payments aren't configured. Raises httpx.HTTPStatusError on a Stripe error."""
    if not is_configured() or not session_id:
        return None
    resp = httpx.get(STRIPE_API + "/checkout/sessions/" + session_id,
                     auth=(secret_key(), ""), timeout=20)
    resp.raise_for_status()
    return resp.json()


def verify_webhook(payload_bytes, sig_header, tolerance=300):
    """Verify the Stripe-Signature header (HMAC-SHA256 over '<t>.<payload>') and
    return the parsed event dict. Raises ValueError on any verification failure —
    the route must treat a raised ValueError as a 400 and change nothing."""
    secret = webhook_secret()
    if not secret:
        raise ValueError("webhook secret not configured")
    if not sig_header:
        raise ValueError("missing signature header")
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("v1")
    if not ts or not sig:
        raise ValueError("malformed signature header")
    signed = ("%s." % ts).encode("utf-8") + payload_bytes
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("signature mismatch")
    if tolerance and abs(time.time() - int(ts)) > tolerance:
        raise ValueError("timestamp outside tolerance")
    return json.loads(payload_bytes)
