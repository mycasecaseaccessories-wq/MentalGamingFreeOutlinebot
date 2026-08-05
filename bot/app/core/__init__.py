"""
app.core — Shared foundation for the Mental Outline VPN Platform.

Phase 0.6: Core Foundation, Shared Components & Developer Standards.

Sub-modules
-----------
constants   — Project-wide constants (BOT_NAME, TTLs, limits, …).
exceptions  — Custom exception hierarchy; never raise bare Exception.
validators  — Reusable input validators (Telegram ID, price, UUID, …).
security    — Secret masking, sanitization, token/hash generation.
interfaces  — Abstract base interfaces (CacheProvider, VPNProvider, …).
schemas     — Pydantic DTOs transferred between layers.
response    — Standard API/service response envelope.
pagination  — Reusable pagination, filtering, and sorting primitives.
utils       — Date/time, formatter, random, JSON, string, env helpers.
"""
