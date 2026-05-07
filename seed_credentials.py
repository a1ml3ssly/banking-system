import secrets
import pymssql
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

CREDENTIALS = [
    {"name": "Admin Service",         "role": "admin"},
    {"name": "Analytics Dashboard",   "role": "readonly"},
    {"name": "Audit Tool",            "role": "readonly"},
]

def generate_key():
    return "bk_live_" + secrets.token_hex(16)

def generate_secret():
    return "bk_secret_" + secrets.token_hex(24)

def seed():
    conn = pymssql.connect(
        server=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 1433)),
        user=os.getenv("DB_USER", "sa"),
        password=os.getenv("DB_PASSWORD", "Banking@NUC2024!"),
        database=os.getenv("DB_NAME", "BankingDB"),
    )
    cursor = conn.cursor()
    generated = []

    print("\nGenerating API credentials...\n")
    print("=" * 70)

    for c in CREDENTIALS:
        api_key     = generate_key()
        api_secret  = generate_secret()
        secret_hash = generate_password_hash(api_secret)
        try:
            cursor.execute(
                "INSERT INTO ApiCredentials (ApiKey, ApiSecretHash, Name, Role) VALUES (%s, %s, %s, %s)",
                (api_key, secret_hash, c["name"], c["role"]),
            )
            generated.append({"name": c["name"], "role": c["role"], "key": api_key, "secret": api_secret})
            print(f"  Name   : {c['name']}")
            print(f"  Role   : {c['role']}")
            print(f"  Key    : {api_key}")
            print(f"  Secret : {api_secret}")
            print(f"  {'─'*60}")
        except Exception as e:
            print(f"  ERROR for {c['name']}: {e}")

    conn.commit()
    conn.close()

    print("\n⚠  Save these secrets now — they cannot be recovered from the database.")
    print("=" * 70)

    with open("credentials.txt", "w") as f:
        f.write("Banking System API Credentials\n")
        f.write("=" * 70 + "\n\n")
        for c in generated:
            f.write(f"Name   : {c['name']}\n")
            f.write(f"Role   : {c['role']}\n")
            f.write(f"Key    : {c['key']}\n")
            f.write(f"Secret : {c['secret']}\n")
            f.write("-" * 70 + "\n\n")

    print("\nCredentials saved to: credentials.txt")
    print("\nTo get a token:")
    print('  curl -X POST http://localhost:8080/token \\')
    print('       -H "Content-Type: application/json" \\')
    if generated:
        print(f'       -d \'{{"key": "{generated[0]["key"]}", "secret": "{generated[0]["secret"]}"}}\'')

if __name__ == "__main__":
    seed()
