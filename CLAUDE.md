# CLAUDE.md — Banking System Database Project

This file gives Claude Code full context on the project: what it is, what's been built, the design decisions made, and what remains to do.

---

## Project Overview

A complete relational database for a banking system, designed from scratch. The goal is a production-quality schema with supporting SQL scripts, documentation, and potential API/loan-engine layer on top.

**Stack:**
- Database: Microsoft SQL Server (likely Express edition)
- SQL Dialect: **T-SQL** (not MySQL, not PostgreSQL)
- Management Tool: SSMS (SQL Server Management Studio)
- ERD Visualization: Mermaid.js (in docs); DBeaver or dbdiagram.io recommended for local diagrams
- Documentation: Word (.docx) generated via the `docx` Node.js library
- API: Flask + Flask-RESTX (Swagger UI at `/docs`)
- API Gateway: Tyk (runs in Docker, proxies to Flask on port 8080)

---

## Schema — 18 Tables

The schema is finalized at **18 tables**, organized into three functional groups:

### Core Banking
| Table | Purpose |
|---|---|
| `Clients` | Individual and business banking customers |
| `Branches` | Physical bank branches |
| `Employees` | Staff linked to branches |
| `Accounts` | Bank accounts (checking, savings, etc.) owned by clients |
| `Transactions` | All financial movements (debits, credits, transfers) |
| `Cards` | Debit/credit cards linked to accounts |
| `Beneficiaries` | Saved transfer recipients for clients |

### Loan Management
| Table | Purpose |
|---|---|
| `Loans` | Active loans linked to accounts |
| `LoanPayments` | Individual repayment records per loan |
| `LoanApplications` | Loan application lifecycle tracking |
| `LoanEligibilityRules` | Configurable thresholds/rules used by the eligibility engine |
| `ClientFinancialProfiles` | Snapshot of a client's financial health (income, DTI, credit score, etc.) |

### Client Services
| Table | Purpose |
|---|---|
| `SupportTickets` | Customer service cases |
| `Notifications` | Messages/alerts sent to clients |
| `AuditLogs` | System-level change tracking |
| `ExchangeRates` | Currency rates for multi-currency support |
| `InterestRates` | Rate configurations per product type |
| `Overdrafts` | Overdraft facilities linked to accounts |

---

## T-SQL Conventions (Critical)

These are non-negotiable — always use T-SQL syntax, never MySQL or PostgreSQL equivalents:

| Concern | Correct T-SQL | Do NOT use |
|---|---|---|
| Auto-increment PK | `INT IDENTITY(1,1) PRIMARY KEY` | `AUTO_INCREMENT` |
| Boolean | `BIT` | `BOOLEAN` / `TINYINT(1)` |
| Current timestamp | `GETDATE()` | `CURRENT_TIMESTAMP`, `NOW()` |
| Auto-update timestamp | Not native — use triggers if needed | `ON UPDATE CURRENT_TIMESTAMP` |
| Self-referencing FK | Separate `ALTER TABLE` after table creation | Inline FK on same table |
| String types | `NVARCHAR(n)` for Unicode | `VARCHAR` where Unicode matters |
| Conditional insert | `IF NOT EXISTS (SELECT ...) INSERT ...` | `INSERT IGNORE` / `ON CONFLICT` |

---

## Key Design Decisions

- **Industry-standard naming**: All table and column names follow standard banking conventions.
- **Loan eligibility engine**: Three tables (`ClientFinancialProfiles`, `LoanApplications`, `LoanEligibilityRules`) were added proactively to support a future rule-based eligibility engine. The engine logic (thresholds, scoring, application workflow) is not yet implemented.
- **Self-referencing FK on `Employees`**: The `ManagerID` column references `EmployeeID` in the same table. This required a separate `ALTER TABLE` statement after creation.
- **`Accounts` links to `Clients` and `Branches`**: Core ownership and branch assignment are both tracked at the account level.
- **`AuditLogs`** is intentionally generic — it captures entity name, record ID, action, old/new values as `NVARCHAR` for flexibility.
- **API folder named `banking_api`** (underscore, not hyphen) — hyphen is invalid in Python module names.
- **API is a monolith split by route file** — each namespace lives in its own file under `banking_api/routes/`. `app.py` is a slim factory that only wires them together.

---

## What Has Been Completed

- [x] Full schema design (18 tables)
- [x] T-SQL `CREATE TABLE` script for all tables
- [x] T-SQL `INSERT` population script with realistic seed data
- [x] ERD rendered in Mermaid.js
- [x] Word (.docx) technical reference document covering all 18 tables
- [x] REST API (Flask + Flask-RESTX) with Swagger UI
- [x] API refactored into monolith structure — one file per route namespace
- [x] JWT authentication (`/token` endpoint via `auth.py` Blueprint)
- [x] Tyk API gateway configuration (Docker)
- [x] `run.py` at project root for local development without entering `banking_api/`

---

## What Remains / Next Steps

- [ ] **Loan eligibility engine logic** — Define the rules, scoring thresholds, and application workflow using `LoanEligibilityRules` and `ClientFinancialProfiles`
- [ ] **Stored procedures** — Common banking operations (transfer funds, apply for loan, close account)
- [ ] **Views** — Useful read-optimized views (e.g., account summary, client portfolio, overdue loans)
- [ ] **Indexes** — Performance indexes on high-query columns (e.g., `AccountNumber`, `ClientID`, `TransactionDate`)
- [ ] **Triggers** — Audit logging trigger, balance update trigger on transactions
- [ ] **ERD in DBeaver or dbdiagram.io** — SSMS diagram feature has a known compatibility issue with Express edition; use external tools instead
- [ ] **Flesh out individual route services** — each route file in `banking_api/routes/` needs to be expanded with full CRUD, validation, and error handling

---

## Known Issues / Gotchas

- **SSMS Diagram Tool**: The built-in diagram feature fails on some SQL Server Express editions. Use DBeaver or dbdiagram.io for visual ERDs.
- **Seed data inserts**: Use `SET IDENTITY_INSERT [TableName] ON/OFF` when manually inserting rows with explicit ID values.
- **No `ON UPDATE CURRENT_TIMESTAMP`** in SQL Server — if `UpdatedAt` columns need auto-refresh, implement via an `AFTER UPDATE` trigger.
- **DB is not on the dev machine** — the database runs separately (configured for Docker via `host.docker.internal`). The Flask API and Swagger UI start fine without it, but any endpoint that hits the DB will fail locally.
- **`pymssql` install on Windows** — requires a pre-built wheel. Use `pip install pymssql --only-binary=:all:` if the normal install fails.

---

## File Structure

```
/
├── CLAUDE.md                        ← This file
├── run.py                           ← Entry point for local dev (run from project root)
├── docker-compose.yml               ← Spins up Flask API + Tyk gateway + Redis
├── create_credentials.sql           ← Creates ApiCredentials table
├── seed_credentials.py              ← Populates ApiCredentials with test keys
├── .gitignore                       ← Excludes .venv/, .idea/, .env, __pycache__
├── tyk/
│   ├── tyk.conf                     ← Tyk gateway config
│   ├── apps/banking-api.json        ← API definition for Tyk
│   └── policies/policies.json       ← Auth policies (admin, readonly)
└── banking_api/
    ├── app.py                       ← Flask app factory — registers namespaces & blueprints
    ├── auth.py                      ← JWT config + /token Blueprint
    ├── db.py                        ← pymssql connection, query(), execute()
    ├── utils.py                     ← serialize_row(), serialize_rows()
    ├── requirements.txt
    ├── Dockerfile
    ├── review.html                  ← Developer/QA documentation page
    └── routes/
        ├── branches.py              → GET /branches, /branches/<id>
        ├── clients.py               → GET/POST /clients, summary, accounts
        ├── accounts.py              → GET/POST /accounts, transactions
        ├── transactions.py          → GET /transactions, deposit-withdrawal, transfer
        ├── loans.py                 → GET /loans, /loans/<id>, /loans/types
        ├── loan_applications.py     → GET/POST /loan-applications, decision, eligibility
        ├── cards.py                 → GET /credit-cards, /<id>, /client/<id>
        └── exchange_rates.py        → GET /exchange-rates, /<base>/<target>
```

---

## API Structure

Each route file in `banking_api/routes/` follows this pattern:
- Creates its own `Namespace` (`ns`)
- Defines Swagger models on the namespace using `ns.model()`
- Each **class** = one URL path; each **method** (`get`, `post`, `put`, `delete`) = one endpoint
- Class docstrings document the URL, methods, and required/optional fields
- The class name is internal only — Swagger shows the URL + HTTP verb

### Request parts and how they are defined

| Part | Defined via | Accessed via |
|---|---|---|
| URL param | `@ns.route('/<int:id>')` | method argument |
| Body field | `ns.model()` + `@ns.expect()` | `ns.payload` |
| Query param | `ns.parser()` + `location='args'` | `parser.parse_args()` |
| Header | `ns.parser()` + `location='headers'` | `parser.parse_args()` |

---

## How to Run

### Local development
```
python run.py
```
Swagger UI: `http://127.0.0.1:5000/docs`

### Full stack (Docker)
```
docker-compose up
```
- Flask API: `http://localhost:5000`
- Tyk gateway: `http://localhost:8080`
- Swagger UI: `http://localhost:5000/docs`

### Database setup
1. Open SSMS and connect to your SQL Server instance.
2. `CREATE DATABASE BankingDB;`
3. Run `schema/create_tables.sql`
4. Run `schema/seed_data.sql`
5. Run `create_credentials.sql` then `python seed_credentials.py`
