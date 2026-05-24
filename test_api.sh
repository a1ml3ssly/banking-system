#!/usr/bin/env bash
BASE="http://172.19.19.114:5000/banking/api/v1"
TOKEN=$(curl -s -X POST $BASE/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key":"bk_live_5f0938799ce02f33b60bbba948442eef","api_secret":"bk_secret_c8b187e3422943bebf436ba50ee802839737c4e0b00ce912"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
PASS=0; FAIL=0; SKIP=0

check() {
  local desc="$1" expected="$2"
  local actual
  actual=$(curl -s -o/dev/null -w "%{http_code}" "${@:3}")
  if [ "$actual" = "$expected" ]; then
    echo "  PASS  $desc"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $desc  [got $actual, want $expected]"
    FAIL=$((FAIL+1))
  fi
}

post_check() {
  local desc="$1" key="$2" url="$3"
  shift 3
  local body
  body=$(curl -s -X POST "$url" -H "$AUTH" -H "Content-Type: application/json" "$@")
  local val
  val=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$key','MISSING'))" 2>/dev/null)
  if [ "$val" != "MISSING" ] && [ -n "$val" ]; then
    echo "  PASS  $desc ($key=$val)"
    PASS=$((PASS+1))
    echo "$val"
  else
    local msg
    msg=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message', d.get('errors','?')))" 2>/dev/null)
    echo "  FAIL  $desc — $msg"
    FAIL=$((FAIL+1))
    echo "MISSING"
  fi
}

# ── Auth ──────────────────────────────────────────────────────
echo "=== AUTH ==="
check "POST /auth/token (admin)" 200 \
  -X POST $BASE/auth/token -H "Content-Type: application/json" \
  -d '{"api_key":"bk_live_5f0938799ce02f33b60bbba948442eef","api_secret":"bk_secret_c8b187e3422943bebf436ba50ee802839737c4e0b00ce912"}'
check "POST /auth/token bad creds -> 401" 401 \
  -X POST $BASE/auth/token -H "Content-Type: application/json" \
  -d '{"api_key":"bad","api_secret":"wrong"}'

# ── Branches ──────────────────────────────────────────────────
echo "=== BRANCHES ==="
check "GET /branches/" 200 $BASE/branches/ -H "$AUTH"
check "GET /branches/1" 200 $BASE/branches/1 -H "$AUTH"
check "GET /branches/9999 -> 404" 404 $BASE/branches/9999 -H "$AUTH"
NEW_BID=$(post_check "POST /branches/" BranchID $BASE/branches/ \
  -d '{"BranchName":"Test Branch","Address":"1 Test St","City":"Haifa","Country":"Israel","Phone":"04-0000001","Email":"haifa@bank.com"}')

# ── Clients ───────────────────────────────────────────────────
echo "=== CLIENTS ==="
check "GET /clients/" 200 $BASE/clients/ -H "$AUTH"
check "GET /clients/4" 200 $BASE/clients/4 -H "$AUTH"
check "GET /clients/9999 -> 404" 404 $BASE/clients/9999 -H "$AUTH"
check "GET /clients/4/accounts" 200 $BASE/clients/4/accounts -H "$AUTH"
check "GET /clients/4/summary" 200 $BASE/clients/4/summary -H "$AUTH"
TS=$(date +%s)
NEW_CID=$(post_check "POST /clients/" ClientID $BASE/clients/ \
  -d "{\"NationalID\":\"IL$TS\",\"FirstName\":\"Test\",\"LastName\":\"User\",\"DateOfBirth\":\"1990-01-01\",\"Email\":\"test$TS@example.com\",\"City\":\"Tel Aviv\"}")

# ── Accounts ──────────────────────────────────────────────────
echo "=== ACCOUNTS ==="
check "GET /accounts/" 200 $BASE/accounts/ -H "$AUTH"
check "GET /accounts/1" 200 $BASE/accounts/1 -H "$AUTH"
check "GET /accounts/9999 -> 404" 404 $BASE/accounts/9999 -H "$AUTH"
check "GET /accounts/1/transactions" 200 $BASE/accounts/1/transactions -H "$AUTH"
NEW_AID=$(post_check "POST /accounts/" AccountID $BASE/accounts/ \
  -d '{"ClientID":4,"BranchID":1,"AccountType":"Savings","Currency":"ILS"}')

# ── Transactions ───────────────────────────────────────────────
echo "=== TRANSACTIONS ==="
check "GET /transactions/" 200 $BASE/transactions/ -H "$AUTH"
check "GET /transactions/7" 200 $BASE/transactions/7 -H "$AUTH"
check "GET /transactions/9999 -> 404" 404 $BASE/transactions/9999 -H "$AUTH"
DEP_ID=$(post_check "POST /transactions/deposit" TransactionID $BASE/transactions/deposit \
  -d '{"account_id":1,"amount":100,"currency":"ILS","description":"Test Deposit"}')
WDR_ID=$(post_check "POST /transactions/withdrawal" TransactionID $BASE/transactions/withdrawal \
  -d '{"account_id":1,"amount":50,"currency":"ILS","description":"Test Withdrawal"}')
TRF_REF=$(post_check "POST /transactions/transfer" reference $BASE/transactions/transfer \
  -d '{"from_account_id":1,"to_account_id":2,"amount":25,"currency":"ILS","description":"Test Transfer"}')

# ── Loans ──────────────────────────────────────────────────────
echo "=== LOANS ==="
check "GET /loans/" 200 $BASE/loans/ -H "$AUTH"
check "GET /loans/4" 200 $BASE/loans/4 -H "$AUTH"
check "GET /loans/9999 -> 404" 404 $BASE/loans/9999 -H "$AUTH"
check "GET /loans/4/payments" 200 $BASE/loans/4/payments -H "$AUTH"

# ── Loan Applications ──────────────────────────────────────────
echo "=== LOAN APPLICATIONS ==="
check "GET /loan-applications/" 200 $BASE/loan-applications/ -H "$AUTH"
check "GET /loan-applications/13" 200 $BASE/loan-applications/13 -H "$AUTH"
check "GET /loan-applications/9999 -> 404" 404 $BASE/loan-applications/9999 -H "$AUTH"

NEW_APPID=$(post_check "POST /loan-applications/" ApplicationID $BASE/loan-applications/ \
  -d '{"ClientID":4,"LoanType":"Personal","RequestedAmount":5000,"TermMonths":12,"Purpose":"Test loan"}')

if [ "$NEW_APPID" != "MISSING" ]; then
  DEC_BODY=$(curl -s -X POST "$BASE/loan-applications/$NEW_APPID/decision" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"decision":"approved","ApprovedAmount":5000,"ApprovedRate":5.5,"decision_note":"Test approval"}')
  DEC_STATUS=$(echo "$DEC_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('Status','MISSING'))" 2>/dev/null)
  if [ "$DEC_STATUS" = "approved" ]; then
    echo "  PASS  POST /loan-applications/$NEW_APPID/decision (Status=$DEC_STATUS)"
    PASS=$((PASS+1))
  else
    MSG=$(echo "$DEC_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message','?'))" 2>/dev/null)
    echo "  FAIL  POST /loan-applications/$NEW_APPID/decision — $MSG"
    FAIL=$((FAIL+1))
  fi
else
  echo "  SKIP  POST /loan-applications/{id}/decision"
  SKIP=$((SKIP+1))
fi

# Eligibility
ELI_APPID=$(curl -s "$BASE/loan-applications/?per_page=50" -H "$AUTH" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['ApplicationID'] if d.get('data') else '')" 2>/dev/null)
if [ -n "$ELI_APPID" ]; then
  ELI_CODE=$(curl -s -o/dev/null -w "%{http_code}" "$BASE/loan-applications/$ELI_APPID/eligibility" -H "$AUTH")
  if [ "$ELI_CODE" = "200" ]; then
    echo "  PASS  GET /loan-applications/$ELI_APPID/eligibility"
    PASS=$((PASS+1))
  elif [ "$ELI_CODE" = "404" ]; then
    echo "  SKIP  GET /loan-applications/$ELI_APPID/eligibility (no ClientFinancialProfile — data gap)"
    SKIP=$((SKIP+1))
  else
    echo "  FAIL  GET /loan-applications/$ELI_APPID/eligibility [got $ELI_CODE]"
    FAIL=$((FAIL+1))
  fi
fi

# ── Cards ──────────────────────────────────────────────────────
echo "=== CARDS ==="
check "GET /cards/" 200 $BASE/cards/ -H "$AUTH"
check "GET /cards/1" 200 $BASE/cards/1 -H "$AUTH"
check "GET /cards/9999 -> 404" 404 $BASE/cards/9999 -H "$AUTH"
check "GET /cards/account/1" 200 $BASE/cards/account/1 -H "$AUTH"
check "GET /cards/client/4" 200 $BASE/cards/client/4 -H "$AUTH"

# ── Exchange Rates ─────────────────────────────────────────────
echo "=== EXCHANGE RATES ==="
check "GET /exchange-rates/" 200 $BASE/exchange-rates/ -H "$AUTH"
check "GET /exchange-rates/USD/ILS" 200 $BASE/exchange-rates/USD/ILS -H "$AUTH"
check "GET /exchange-rates/USD/XYZ -> 404" 404 $BASE/exchange-rates/USD/XYZ -H "$AUTH"

echo ""
echo "═══════════════════════════════════════════"
echo "  RESULTS: $PASS passed  |  $FAIL failed  |  $SKIP skipped"
echo "═══════════════════════════════════════════"
