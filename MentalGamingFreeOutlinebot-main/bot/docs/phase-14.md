# Phase 1.4 — Package Catalog & Buy VPN UI

Phase 1.4 connects the existing **🛒 Buy VPN** customer button to a read-only,
database-backed package catalogue.

## Flow

Main Menu → Buy VPN → Package List → Package Details → Package Selected →
Phase 2 checkout placeholder.

Only active, visible, customer-purchasable package types (`paid`, `promotion`,
`vip`) are shown. Free-trial and reward packages are intentionally excluded.

## Safety boundaries

Phase 1.4 does **not**:
- create orders,
- process payments,
- debit wallet balances,
- call Outline,
- select an actual VPN server,
- generate VPN keys.

The selection state contains only a package id, quoted price/currency and
timestamp for future Phase 2 handoff.

## Package storage

The legacy package schema remains backward compatible. Migration `0006`
adds customer-catalogue metadata while retaining `is_active`, `sort_order`,
`max_devices`, and existing price/duration/data columns.
