# Database Architecture Audit — MentalGamingFreeOutlinebot

## အနှစ်ချုပ်

Actual repository code အရ application သည် **SQLAlchemy Async ORM** ပေါ်တွင် တည်ဆောက်ထားပြီး production အတွက် **PostgreSQL + asyncpg**၊ development/test အတွက် **SQLite + aiosqlite** ကို `DATABASE_URL` scheme ဖြင့် ရွေးချယ်နိုင်သည်။ MongoDB/Motor/PyMongo/Beanie ကဲ့သို့သော MongoDB ODM/driver သို့မဟုတ် MongoDB configuration မတွေ့ပါ။

> **MONGODB_REPLACEMENT = NOT_SUPPORTED_WITHOUT_ARCHITECTURAL_CHANGE**

Database မပြောင်းထားပါ၊ repository ကို rewrite မလုပ်ထားပါ။

## Actual findings

| အချက် | Codebase မှ တွေ့ရှိချက် | Evidence |
|---|---|---|
| Current database engine | SQL relational database architecture ဖြစ်သည်။ Production target က PostgreSQL၊ local development/test default က SQLite ဖြစ်သည်။ | `bot/database/connection.py:7-10, 120-128` |
| ORM/ODM | SQLAlchemy 2.x async ORM ဖြစ်သည်။ `AsyncEngine`, `AsyncSession`, `async_sessionmaker`, declarative `Mapped`/`mapped_column` models အသုံးပြုထားသည်။ MongoDB ODM မရှိပါ။ | `bot/database/connection.py:31-37`; `bot/database/models/*.py` |
| Database driver | PostgreSQL အတွက် `asyncpg`၊ SQLite အတွက် `aiosqlite` ဖြစ်သည်။ | `pyproject.toml`; `bot/database/connection.py:7-10, 120-128` |
| Migration system | Alembic ဖြစ်သည်။ Application startup တွင် `_run_migrations()` က Alembic `upgrade head` ကို run သည်။ Current repository migration head သည် `0042_phase83_payment_wallet_security` ဖြစ်သည်။ | `bot/database/connection.py:101-185`; `bot/database/migrations/versions/` |
| Transaction implementation | `DatabaseManager.session()` သည် async context manager ဖြစ်ပြီး success တွင် `session.commit()`၊ exception တွင် `session.rollback()` လုပ်သည်။ Service တစ်ခုအတွင်း atomic DB unit-of-work အဖြစ် အသုံးပြုထားသည်။ | `bot/database/connection.py:265-285` |
| Row/record locking | SQLAlchemy `select(...).with_for_update()`၊ `session.get(..., with_for_update=True)` နှင့် conditional `UPDATE` များကို အသုံးပြုထားသည်။ PostgreSQL တွင် row locks အဖြစ် အကျိုးသက်ရောက်ပြီး SQLite တွင် database locking semantics သာ ရှိသည်။ | `bot/app/services/*.py`; `bot/database/repositories/*.py` |
| Wallet unique constraints | `transactions` table တွင် `(provider, provider_reference)` unique constraint နှင့် `idempotency_key` unique field/index အသုံးပြုထားသည်။ Phase 8.3 migration က provider-scoped reference index/constraint ကို ထည့်ထားသည်။ | `bot/database/models/transaction.py`; `0042_phase83_payment_wallet_security.py` |
| Payment-submission uniqueness | `payment_submissions` တွင် `public_payment_id`, `idempotency_key`, `(provider, provider_reference)` အတွက် database uniqueness ရှိသည်။ Manual-payment model တွင် provider fields သည် evidence/reference metadata ဖြစ်ပြီး external provider authority မဟုတ်ပါ။ | `bot/database/models/payment_submission.py` |
| Concurrent debit protection | `WalletAccountingService.debit()` သည် transaction idempotency ကို အရင်စစ်ပြီး wallet row ကို lock/query လုပ်ကာ `balance >= amount` conditional `UPDATE` ဖြင့် debit လုပ်သည်။ Ledger insert နှင့် balance update သည် database session တစ်ခုထဲတွင် ဖြစ်သည်။ Duplicate idempotency key သည် existing transaction ကို ပြန်ပေးပြီး conflict ဖြစ်ပါက failure ပြန်ပေးသည်။ | `bot/app/services/wallet_accounting_service.py:159-225, 227-318` |
| Immutable ledger behavior | Ledger row ကို အသစ်ထည့်သည်။ Existing transaction ကို idempotency path မှာ ပြန်အသုံးပြုသော်လည်း ပြင်ဆင်ခြင်းမပြုပါ။ Direct balance mutation များကို accounting service အောက်သို့ ရွှေ့ထားသည်။ | `bot/app/services/wallet_accounting_service.py`; `wallet_payment_service.py`; `referral_reward_service.py` |
| Current test database | Existing test fixtures အများစုသည် temporary SQLite URL — `sqlite+aiosqlite:///...` — နှင့် disposable DB ကို အသုံးပြုသည်။ Tests များသည် PostgreSQL server မလိုဘဲ run နိုင်သော်လည်း production PostgreSQL locking/concurrency behavior ကို အပြည့်အဝ မသက်သေပြနိုင်ပါ။ | `bot/tests/conftest.py`; `bot/tests/integration/conftest.py`; `bot/tests/test_*.py` |
| PostgreSQL test requirement | Repository တွင် PostgreSQL `asyncpg` production URL support ရှိသော်လည်း လက်ရှိ environment တွင် PostgreSQL service/client မရှိသဖြင့် PostgreSQL-backed concurrency tests ကို မ run နိုင်ပါ။ | `bot/database/connection.py`; current environment check |
| MongoDB support | MongoDB URL, Motor/PyMongo/Beanie dependency, Mongo document models, Mongo migration path, or Mongo transaction/session adapter မတွေ့ပါ။ | dependency/config/source audit |

## Transaction and locking details

`DatabaseManager.session()` သည် service operations အတွက် commit/rollback boundary ဖြစ်သည်။ Wallet debit သည် idempotency row ကိုရှာပြီး wallet row ကို lock/query ပြုလုပ်ကာ `balance >= value` ကို database-level conditional predicate အဖြစ် ထည့်သွင်းထားသည်။ ထို့ကြောင့် balance မလုံလောက်သော debit နှစ်ခုအတွက် database update row count သည် တစ်ခုသာအောင်မြင်နိုင်ပြီး၊ unique `idempotency_key` သည် payment/reward/adjustment retry များကို ထပ်မံစာရင်းသွင်းခြင်းမှ ကာကွယ်သည်။

`with_for_update()` သည် SQLAlchemy relational locking API ဖြစ်သည်။ PostgreSQL တွင် သင့်တော်သော row-level lock semantics ရှိသော်လည်း SQLite သည် PostgreSQL နှင့်တူညီသော row-level concurrency မပေးပါ။ ထို့ကြောင့် SQLite focused tests အောင်မြင်ခြင်းကို PostgreSQL multi-process concurrency PASS ဟု မယူဆရပါ။

## MongoDB ပြောင်းရန် လိုအပ်မည့် architectural changes

MongoDB သို့ ပြောင်းလဲခြင်းသည် connection URL တစ်ခု ပြောင်းရုံဖြင့် မဖြစ်နိုင်ပါ။ လက်ရှိ code သည် SQLAlchemy `select`, `update`, `with_for_update`, SQL constraints, Alembic revisions, relational table schemas, `AsyncSession` commit/rollback နှင့် repository query patterns ပေါ်တွင် အခြေခံထားသည်။ MongoDB သို့ ပြောင်းပါက အနည်းဆုံး အောက်ပါအပိုင်းများကို ပြန်လည်ဒီဇိုင်းလုပ်ရမည်။

| ပြောင်းရမည့်အပိုင်း | လိုအပ်သော architectural change |
|---|---|
| Driver/session layer | `asyncpg`/`aiosqlite` နှင့် SQLAlchemy AsyncSession အစား Motor သို့မဟုတ် PyMongo async API ကို အသုံးပြုရမည်။ |
| Models | Relational SQLAlchemy models များကို Mongo documents/schema validation သို့ ပြောင်းရမည်။ Foreign-key-like relationships များကို reference/embedding strategy ဖြင့် ပြန်သတ်မှတ်ရမည်။ |
| Repositories | SQLAlchemy `select`, `update`, joins နှင့် scalar results များကို Mongo query/update pipelines သို့ ပြန်ရေးရမည်။ |
| Migrations | Alembic revision chain ကို MongoDB migration/versioning tool သို့ ပြောင်းရမည်။ Existing SQL schema migration history ကို တိုက်ရိုက်အသုံးမပြုနိုင်ပါ။ |
| Transactions | MongoDB replica set/cluster transaction model, session lifecycle နှင့် retry semantics ကို ပြန်ရေးရမည်။ လက်ရှိ SQL session context ကို မသုံးနိုင်ပါ။ |
| Locking | `with_for_update()` အစား atomic conditional updates, document-level atomicity, transactions နှင့် unique indexes ကို အသုံးပြုရမည်။ |
| Wallet debit | Balance နှင့် ledger ကို document တစ်ခုတည်းတွင် embedded လုပ်မလား၊ သီးခြား collections နှင့် transaction သုံးမလား ဆုံးဖြတ်ရမည်။ Current SQL row-lock/conditional-update implementation ကို တိုက်ရိုက်မရွှေ့နိုင်ပါ။ |
| Constraints | SQL `UniqueConstraint` များကို Mongo unique indexes သို့ ပြန်တည်ဆောက်ရမည်။ Null/partial-index semantics များကို ပြန်စစ်ရမည်။ |
| Tests | SQLite fixtures နှင့် SQL-specific assertions များကို Mongo test database/replica-set harness ဖြင့် ပြန်ရေးရမည်။ Concurrent debit, duplicate settlement, duplicate refund နှင့် idempotency tests များကို Mongo semantics အတိုင်း ပြန်သက်သေပြရမည်။ |
| Operations | Backup, restore, monitoring, deployment, connection pooling နှင့် production consistency assumptions များကို MongoDB အတွက် ပြန်စီမံရမည်။ |

## Final conclusion

လက်ရှိ application သည် **PostgreSQL-oriented relational architecture** ဖြစ်ပြီး SQLite သည် development/test compatibility အတွက်သာ အသုံးပြုထားသည်။ MongoDB ကို လက်ရှိ codebase အတွင်း configuration ပြောင်းရုံဖြင့် အစားထိုးအသုံးပြုနိုင်ခြင်း မရှိပါ။ WalletAccountingService ၏ correctness သည် SQL transactions, unique constraints, conditional updates နှင့် row-locking/repository conventions များပေါ်တွင် တည်နေသောကြောင့် MongoDB migration သည် **new database adapter သာမက model, repository, migration, transaction, locking, test နှင့် operational architecture ပြောင်းလဲမှု** ဖြစ်မည်။

> **MONGODB_REPLACEMENT = NOT_SUPPORTED_WITHOUT_ARCHITECTURAL_CHANGE**

## References

1. `bot/database/connection.py` — SQLAlchemy async engine, PostgreSQL/SQLite URLs, session commit/rollback, Alembic startup migration.
2. `bot/app/services/wallet_accounting_service.py` — Decimal validation, idempotency, conditional debit, ledger insertion, wallet mutation boundary.
3. `bot/database/models/transaction.py` — transaction fields, provider/reference uniqueness, idempotency key.
4. `bot/database/models/payment_submission.py` — manual payment submission fields and uniqueness constraints.
5. `bot/database/migrations/versions/0042_phase83_payment_wallet_security.py` — Phase 8.3 database indexes/constraints.
6. `bot/tests/conftest.py`, `bot/tests/integration/conftest.py`, and `bot/tests/test_*.py` — SQLite-based test fixtures and database requirements.
7. `pyproject.toml` — SQLAlchemy, Alembic, asyncpg, and aiosqlite dependencies.
8. `bot/database/repositories/*.py` and `bot/app/services/*.py` — relational repository queries and `with_for_update()` locking usage.
