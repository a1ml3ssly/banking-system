# CLAUDE.md — Banking System API (v2)

Full context for Claude Code. Read this before touching any file.

---

## Stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Language    | Python 3.12                                     |
| Framework   | Flask 3 + Flask-RESTX (Swagger UI at `/docs`)   |
| Database    | Microsoft SQL Server — T-SQL dialect            |
| DB driver   | pymssql                                         |
| Auth        | JWT (PyJWT) via POST `/api/v1/token`            |
| Gateway     | Tyk v5.3 (Docker, port 8080)                   |
| Dev entry   | `python run.py` (port 5000)                     |

---

## Project layout

```
/
├── .env                     ← secrets (gitignored — copy from .env.example)
├── .env.example             ← template — commit this, never .env
├── .gitignore
├── run.py                   ← local dev entry point (3 meaningful lines)
├── docker-compose.yml       ← all secrets come from .env via env_file:
├── create_credentials.sql   ← creates ApiCredentials table in SSMS
├── seed_credentials.py      ← populates ApiCredentials from .env
├── CLAUDE.md                ← this file
│
├── banking_api/
│   ├── __init__.py          ← create_app() factory — registers all namespaces
│   ├── config.py            ← all env-var loading; DB_PROFILE switching here
│   ├── db.py                ← lazy DB connection; query(), query_one(), execute(), execute_returning()
│   ├── auth.py              ← JWT namespace (/token endpoint) + require_auth() decorator
│   ├── utils.py             ← serialize_row/rows(), paginate()
│   ├── requirements.txt
│   ├── Dockerfile
│   └── routes/
│       ├── branches.py
│       ├── clients.py
│       ├── accounts.py
│       ├── transactions.py
│       ├── loans.py
│       ├── loan_applications.py
│       ├── cards.py
│       └── exchange_rates.py
│
└── tyk/
    ├── tyk.conf
    ├── apps/banking-api.json
    └── policies/policies.json
```

---

## Running locally (no Docker)

```bash
# 1. Create your env file
cp .env.example .env
# edit .env: fill in DB_HOST_OFFICE, DB_HOST_HOME, DB_PASSWORD, JWT_SECRET

# 2. Install deps (from project root)
pip install -r banking_api/requirements.txt

# 3. Start
python run.py
```

Swagger UI: http://127.0.0.1:5000/docs

The app starts even if the database is unreachable.
Endpoints return 503 until the DB is available — the process never crashes on startup.

---

## Running with Docker (full stack)

```bash
docker-compose up --build
```

- Flask API:    http://localhost:5000
- Tyk gateway: http://localhost:8080
- Swagger UI:  http://localhost:5000/docs

---

## DB profile switching

Edit one line in `.env`:

```
DB_PROFILE=office    # LAN (default)
DB_PROFILE=home      # Tailscale
```

The hosts are set separately:
```
DB_HOST_OFFICE=192.168.x.x
DB_HOST_HOME=100.x.x.x
```

No code changes — just `.env`.

---

## Auth flow

1. POST `/api/v1/token` with `{ "api_key": "...", "api_secret": "..." }`
2. Receive `{ "access_token": "...", "role": "admin|readonly" }`
3. All other endpoints require: `Authorization: Bearer <access_token>`

Roles:
- `admin` — full access (GET + POST + mutations)
- `readonly` — GET endpoints only

---

## API endpoints

| Method | Path                                      | Role     |
|--------|-------------------------------------------|----------|
| POST   | /api/v1/token                             | public   |
| GET    | /api/v1/branches/                         | any      |
| POST   | /api/v1/branches/                         | admin    |
| GET    | /api/v1/branches/{id}                     | any      |
| GET    | /api/v1/clients/                          | any      |
| POST   | /api/v1/clients/                          | admin    |
| GET    | /api/v1/clients/{id}                      | any      |
| GET    | /api/v1/clients/{id}/accounts             | any      |
| GET    | /api/v1/clients/{id}/summary              | any      |
| GET    | /api/v1/accounts/                         | any      |
| POST   | /api/v1/accounts/                         | admin    |
| GET    | /api/v1/accounts/{id}                     | any      |
| GET    | /api/v1/accounts/{id}/transactions        | any      |
| GET    | /api/v1/transactions/                     | any      |
| GET    | /api/v1/transactions/{id}                 | any      |
| POST   | /api/v1/transactions/deposit              | admin    |
| POST   | /api/v1/transactions/withdrawal           | admin    |
| POST   | /api/v1/transactions/transfer             | admin    |
| GET    | /api/v1/loans/                            | any      |
| GET    | /api/v1/loans/{id}                        | any      |
| GET    | /api/v1/loans/{id}/payments               | any      |
| GET    | /api/v1/loan-applications/                | any      |
| POST   | /api/v1/loan-applications/                | admin    |
| GET    | /api/v1/loan-applications/{id}            | any      |
| POST   | /api/v1/loan-applications/{id}/decision   | admin    |
| GET    | /api/v1/loan-applications/{id}/eligibility | any     |
| GET    | /api/v1/cards/                            | any      |
| GET    | /api/v1/cards/{id}                        | any      |
| GET    | /api/v1/cards/account/{id}                | any      |
| GET    | /api/v1/cards/client/{id}                 | any      |
| GET    | /api/v1/exchange-rates/                   | any      |
| GET    | /api/v1/exchange-rates/{base}/{target}    | any      |

---

## T-SQL conventions (never use MySQL/PostgreSQL syntax)

| Concern               | Correct T-SQL                  | Do NOT use              |
|-----------------------|--------------------------------|-------------------------|
| Auto-increment PK     | `INT IDENTITY(1,1) PRIMARY KEY`| `AUTO_INCREMENT`        |
| Boolean               | `BIT`                          | `BOOLEAN`               |
| Current timestamp     | `GETDATE()`                    | `NOW()`, `CURRENT_TIMESTAMP` |
| Auto-update timestamp | `AFTER UPDATE` trigger         | `ON UPDATE CURRENT_TIMESTAMP` |
| Self-referencing FK   | Separate `ALTER TABLE`         | Inline FK on same table |
| Unicode strings       | `NVARCHAR(n)`                  | `VARCHAR` for user data |
| Conditional insert    | `IF NOT EXISTS (...) INSERT`   | `INSERT IGNORE`         |
| Return inserted row   | `OUTPUT INSERTED.*`            | `RETURNING`             |

---

## Key patterns used throughout

**Lazy DB connection** — `db.get_connection()` is only called inside route handlers.
The app boots without a DB. Unreachable DB → 503, never a crash.

**require_auth decorator** — wraps resource methods, validates JWT, aborts with 401/403.
```python
@require_auth()                      # any valid token
@require_auth(roles=['admin'])       # admin only
```

**OUTPUT INSERTED.*** — used in every INSERT to return the created row without a second query.
```sql
INSERT INTO Branches (...) OUTPUT INSERTED.* VALUES (...)
```

**paginate()** — `utils.paginate(rows, page, per_page)` returns a standard envelope:
```json
{ "data": [...], "page": 1, "per_page": 20, "total": 142, "pages": 8 }
```

---

## Credentials setup (first time)

1. In SSMS: run `create_credentials.sql`
2. Add your keys to `.env`:
   ```
   CRED_1_KEY=bk_live_xxx
   CRED_1_SECRET=bk_secret_xxx
   CRED_1_LABEL=Admin
   CRED_1_ROLE=admin
   ```
3. `python seed_credentials.py`

---

## What still needs doing

- [ ] Stored procedures (fund transfer, close account)
- [ ] Views (account summary, client portfolio, overdue loans)
- [ ] Performance indexes on AccountNumber, ClientID, TransactionDate
- [ ] Audit trigger (auto-insert into AuditLogs on write)
- [ ] Balance update trigger (recalculate balance from Transactions)
- [ ] Employees and Beneficiaries routes (schema exists, no routes yet)
- [ ] SupportTickets and Notifications routes
