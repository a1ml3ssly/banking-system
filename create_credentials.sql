USE BankingDB;
GO

CREATE TABLE ApiCredentials (
    CredentialID   INT          PRIMARY KEY IDENTITY(1,1),
    ApiKey         VARCHAR(50)  UNIQUE NOT NULL,
    ApiSecretHash  VARCHAR(255) NOT NULL,
    Name           VARCHAR(100) NOT NULL,
    Role           VARCHAR(20)  NOT NULL CHECK (Role IN ('admin', 'readonly')),
    IsActive       BIT          DEFAULT 1,
    CreatedAt      DATETIME     DEFAULT GETDATE(),
    LastUsedAt     DATETIME
);
GO

PRINT 'ApiCredentials table created. Run seed_credentials.py to insert credentials.';
GO
