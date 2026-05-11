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

---

## What Has Been Completed

- [x] Full schema design (18 tables)
- [x] T-SQL `CREATE TABLE` script for all tables
- [x] T-SQL `INSERT` population script with realistic seed data
- [x] ERD rendered in Mermaid.js
- [x] Word (.docx) technical reference document covering all 18 tables

---

## What Remains / Next Steps

- [ ] **Loan eligibility engine logic** — Define the rules, scoring thresholds, and application workflow using `LoanEligibilityRules` and `ClientFinancialProfiles`
- [ ] **Stored procedures** — Common banking operations (transfer funds, apply for loan, close account)
- [ ] **API service layer** — REST API design on top of the schema (endpoints, request/response contracts)
- [ ] **Views** — Useful read-optimized views (e.g., account summary, client portfolio, overdue loans)
- [ ] **Indexes** — Performance indexes on high-query columns (e.g., `AccountNumber`, `ClientID`, `TransactionDate`)
- [ ] **Triggers** — Audit logging trigger, balance update trigger on transactions
- [ ] **ERD in DBeaver or dbdiagram.io** — SSMS diagram feature has a known compatibility issue with Express edition; use external tools instead

---

## Known Issues / Gotchas

- **SSMS Diagram Tool**: The built-in diagram feature fails on some SQL Server Express editions. Use DBeaver or dbdiagram.io for visual ERDs.
- **Seed data inserts**: Use `SET IDENTITY_INSERT [TableName] ON/OFF` when manually inserting rows with explicit ID values.
- **No `ON UPDATE CURRENT_TIMESTAMP`** in SQL Server — if `UpdatedAt` columns need auto-refresh, implement via an `AFTER UPDATE` trigger.

---

## File Structure (Expected)

```
/
├── CLAUDE.md                  ← This file
├── schema/
│   ├── create_tables.sql      ← Full T-SQL CREATE TABLE script
│   └── seed_data.sql          ← T-SQL INSERT population script
├── procedures/
│   └── (stored procs — TBD)
├── views/
│   └── (views — TBD)
├── docs/
│   ├── banking_db_reference.docx   ← Technical Word document
│   └── erd.mermaid                 ← Mermaid ERD source
└── api/
    └── (API design — TBD)
```

---

## How to Run

1. Open SSMS and connect to your SQL Server instance.
2. Create a new database: `CREATE DATABASE BankingDB;`
3. Run `schema/create_tables.sql` to create all 18 tables.
4. Run `schema/seed_data.sql` to populate with sample data.
5. Verify with: `SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE';`
