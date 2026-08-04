# -*- coding: utf-8 -*-
"""PAYMENTS — the invoice seam.

ALL PAYMENTS BY INVOICE (David's ruling, 2026-08-04 — PH-PAY-1). The Stripe
integration that used to live here (httpx Checkout Sessions, stdlib-HMAC
webhook verification, key accessors) was removed under that ruling: no keys
were ever configured (the DECISIONS:4076 "add TEST keys" was owed and never
delivered), the webhook was fail-closed-inert without a secret, and dead
payment machinery under a product that takes no card payments is exactly what
someone later "completes" because it looks half-finished.

Card payment MAY return later. This module is the seam it returns through:
mode() is what the console and the launch flow branch on, and today it has
exactly one answer. Reinstating card payment is a deliberate build against
DECISIONS 2026-08-04 (PH-PAY-1), not a key drop-in — the checkout routes and
webhook no longer exist.

The £ flow that remains: an approved pulse launch records an order
(pulse_launch_orders — the invoice ledger); the platform admin's
Confirm-launch marks it paid (payment_intent='staff-confirmed') once the
invoice settles, which opens the pulse. pulses.py owns those helpers.
"""


def mode():
    """'invoice' — the only payment mode. Surfaced to the console and the
    member launch flow; the seam a future card integration would widen."""
    return "invoice"


def is_configured():
    """No card processor is configured, by ruling — not by missing keys."""
    return False
