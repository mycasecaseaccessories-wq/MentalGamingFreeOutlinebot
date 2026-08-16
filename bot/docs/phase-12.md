# Phase 1.2 — Customer Main UI & Navigation

Phase 1.2 replaces the Phase 1.1 customer placeholder with a real,
localized customer main menu.

## Main menu

- 🛒 Buy VPN
- 🎁 Free Trial
- 🔑 My Keys
- 💰 Wallet
- 👤 Profile
- 🎫 Support

The main menu is a persistent `ReplyKeyboardMarkup`. Each destination is
routed through `CustomerNavigationService`, which stores `last_menu` in the
existing user preferences table.

Phase 1.2 intentionally does not implement package purchases, free-trial
eligibility, wallet transactions, VPN key data, profile details, or support
business logic. These menu destinations render localized placeholder pages so
later phases can replace each page independently without changing navigation.

`/start` now routes normal customers directly to this menu after onboarding.
`/menu` and `/home` reopen it. Unknown text receives a localized fallback and
the menu is re-shown.

No VPN-key ownership check exists in the start or navigation flow.
