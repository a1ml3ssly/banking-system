-- create_credentials.sql
-- Run this once against BankingDB to create the API credentials table.
-- Then run seed_credentials.py to populate it.

USE BankingDB;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = 'ApiCredentials'
)
BEGIN
    CREATE TABLE ApiCredentials (
        CredentialID INT          IDENTITY(1,1) PRIMARY KEY,
        ApiKey       NVARCHAR(64) NOT NULL UNIQUE,
        ApiSecret    NVARCHAR(128) NOT NULL,
        Label        NVARCHAR(100) NULL,
        Role         NVARCHAR(50)  NOT NULL DEFAULT 'readonly',
        IsActive     BIT           NOT NULL DEFAULT 1,
        CreatedAt    DATETIME      NOT NULL DEFAULT GETDATE()
    );

    PRINT 'ApiCredentials table created.';
END
ELSE
BEGIN
    PRINT 'ApiCredentials table already exists — skipping.';
END
GO
