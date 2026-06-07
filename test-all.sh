#!/bin/bash
# Sound Box - Full Test Suite Runner
# Runs all test suites: Python unit tests + Playwright E2E tests
#
# Usage: ./test-all.sh [options]
#   --skip-e2e    Skip Playwright E2E tests
#   --skip-unit   Skip Python unit tests
#
# Reports written to reports/ (gitignored):
#   reports/index.html     — unified summary with links
#   reports/pytest.html    — pytest detail report
#   reports/playwright.html — Playwright detail report

set -e
cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
SKIP_E2E=false
SKIP_UNIT=false
for arg in "$@"; do
    case $arg in
        --skip-e2e) SKIP_E2E=true ;;
        --skip-unit) SKIP_UNIT=true ;;
    esac
done

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sound Box - Full Test Suite${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ─── Reports directory ───
mkdir -p reports

# ─── Prerequisites ───
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Venv must exist (created by setup.sh)
if [ ! -x "./venv/bin/python" ]; then
    echo -e "${RED}✗ venv not found - run ./setup.sh first${NC}"
    exit 1
fi

# pytest (installed by setup.sh, but self-heal for older envs)
if ! ./venv/bin/python -m pytest --version > /dev/null 2>&1; then
    echo -e "${YELLOW}  Installing pytest into venv...${NC}"
    ./venv/bin/pip install pytest -q
fi

# Node deps
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}  Installing Node dependencies...${NC}"
    npm install
fi

# Playwright browser binaries (separate from node_modules)
if [ "$SKIP_E2E" = false ]; then
    if ! find "$HOME/.cache/ms-playwright" -name "headless_shell" -type f 2>/dev/null | grep -q .; then
        echo -e "${YELLOW}  Installing Playwright Chromium browser...${NC}"
        npx playwright install chromium
    fi
fi

echo -e "${GREEN}✓ Prerequisites ready${NC}"
echo ""

# ─── Server ───
STARTED_SERVER=false
echo -e "${YELLOW}Checking server...${NC}"
if curl -s http://localhost:5309/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server already running${NC}"
else
    echo -e "${YELLOW}Starting server...${NC}"
    ./start.sh &
    SERVER_PID=$!
    STARTED_SERVER=true
    trap "kill $SERVER_PID 2>/dev/null" EXIT

    # Wait for server to be ready
    for i in $(seq 1 30); do
        if curl -s http://localhost:5309/ > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:5309/ > /dev/null 2>&1; then
        echo -e "${RED}✗ Failed to start server${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"
fi
echo ""

# ─── Results tracking ───
UNIT_PASSED=0
UNIT_FAILED=0
UNIT_EXIT=0
E2E_PASSED=0
E2E_FAILED=0
E2E_EXIT=0
OVERALL_EXIT=0

# ─── Python Unit Tests ───
if [ "$SKIP_UNIT" = false ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Python Unit Tests${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    set +e
    ./venv/bin/python -m pytest tests/test_*.py -v --html=reports/pytest.html --self-contained-html 2>&1 | tee /tmp/soundbox-unit-tests.txt
    UNIT_EXIT=${PIPESTATUS[0]}
    set -e

    # grep -c always prints a count, but exits non-zero on no-match. Without
    # `|| true` the `|| echo "0"` fallback double-emits "0\n0" which breaks
    # downstream arithmetic.
    UNIT_PASSED=$(grep -cE "PASSED" /tmp/soundbox-unit-tests.txt 2>/dev/null || true)
    UNIT_FAILED=$(grep -cE "FAILED" /tmp/soundbox-unit-tests.txt 2>/dev/null || true)
    UNIT_PASSED=${UNIT_PASSED:-0}
    UNIT_FAILED=${UNIT_FAILED:-0}

    if [ "$UNIT_EXIT" -eq 0 ]; then
        echo -e "\n${GREEN}✓ Unit tests passed${NC}"
    else
        echo -e "\n${RED}✗ Unit tests failed${NC}"
        OVERALL_EXIT=1
    fi
    echo ""
fi

# ─── Playwright E2E Tests ───
if [ "$SKIP_E2E" = false ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Playwright E2E Tests${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    set +e
    npx playwright test --reporter=list 2>&1 | tee /tmp/soundbox-e2e-tests.txt
    E2E_EXIT=${PIPESTATUS[0]}
    set -e

    E2E_PASSED=$(grep -oE '[0-9]+ passed' /tmp/soundbox-e2e-tests.txt 2>/dev/null | tail -1 | grep -oE '[0-9]+' || true)
    E2E_FAILED=$(grep -oE '[0-9]+ failed' /tmp/soundbox-e2e-tests.txt 2>/dev/null | tail -1 | grep -oE '[0-9]+' || true)
    E2E_PASSED=${E2E_PASSED:-0}
    E2E_FAILED=${E2E_FAILED:-0}

    if [ "$E2E_EXIT" -eq 0 ]; then
        echo -e "\n${GREEN}✓ E2E tests passed${NC}"
    else
        echo -e "\n${RED}✗ E2E tests failed${NC}"
        OVERALL_EXIT=1
    fi
    echo ""
fi

# ─── Summary ───
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$SKIP_UNIT" = false ]; then
    if [ "$UNIT_EXIT" -eq 0 ]; then
        echo -e "  ${GREEN}✓ Python Unit Tests:  ${UNIT_PASSED} passed, ${UNIT_FAILED} failed${NC}"
    else
        echo -e "  ${RED}✗ Python Unit Tests:  ${UNIT_PASSED} passed, ${UNIT_FAILED} failed${NC}"
    fi
else
    echo -e "  ${YELLOW}⊘ Python Unit Tests:  skipped${NC}"
fi

if [ "$SKIP_E2E" = false ]; then
    if [ "$E2E_EXIT" -eq 0 ]; then
        echo -e "  ${GREEN}✓ E2E Tests:         ${E2E_PASSED} passed, ${E2E_FAILED} failed${NC}"
    else
        echo -e "  ${RED}✗ E2E Tests:         ${E2E_PASSED} passed, ${E2E_FAILED} failed${NC}"
    fi
else
    echo -e "  ${YELLOW}⊘ E2E Tests:          skipped${NC}"
fi

echo ""

TOTAL_PASSED=$((UNIT_PASSED + E2E_PASSED))
TOTAL_FAILED=$((UNIT_FAILED + E2E_FAILED))

if [ "$OVERALL_EXIT" -eq 0 ]; then
    echo -e "  ${GREEN}All test suites passed! (${TOTAL_PASSED} total)${NC}"
else
    echo -e "  ${RED}Some test suites failed. (${TOTAL_PASSED} passed, ${TOTAL_FAILED} failed)${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ─── Copy Playwright report ───
if [ "$SKIP_E2E" = false ] && [ -f "playwright-report/index.html" ]; then
    cp playwright-report/index.html reports/playwright.html
fi

# ─── Generate unified index.html ───
RUN_TS=$(date '+%Y-%m-%d %H:%M:%S')

# Build per-suite status strings and colors for the HTML
if [ "$SKIP_UNIT" = true ]; then
    UNIT_HTML_STATUS="skipped"
    UNIT_HTML_COLOR="#64748b"
    UNIT_HTML_LINK="<span style='color:#64748b'>no report</span>"
elif [ "$UNIT_EXIT" -eq 0 ]; then
    UNIT_HTML_STATUS="${UNIT_PASSED} passed, ${UNIT_FAILED} failed"
    UNIT_HTML_COLOR="#10b981"
    UNIT_HTML_LINK="<a href='pytest.html'>open pytest report</a>"
else
    UNIT_HTML_STATUS="${UNIT_PASSED} passed, ${UNIT_FAILED} failed"
    UNIT_HTML_COLOR="#ef4444"
    UNIT_HTML_LINK="<a href='pytest.html'>open pytest report</a>"
fi

if [ "$SKIP_E2E" = true ]; then
    E2E_HTML_STATUS="skipped"
    E2E_HTML_COLOR="#64748b"
    E2E_HTML_LINK="<span style='color:#64748b'>no report</span>"
elif [ "$E2E_EXIT" -eq 0 ]; then
    E2E_HTML_STATUS="${E2E_PASSED} passed, ${E2E_FAILED} failed"
    E2E_HTML_COLOR="#10b981"
    E2E_HTML_LINK="<a href='playwright.html'>open Playwright report</a>"
else
    E2E_HTML_STATUS="${E2E_PASSED} passed, ${E2E_FAILED} failed"
    E2E_HTML_COLOR="#ef4444"
    E2E_HTML_LINK="<a href='playwright.html'>open Playwright report</a>"
fi

if [ "$OVERALL_EXIT" -eq 0 ]; then
    OVERALL_LABEL="All suites passed"
    OVERALL_COLOR="#10b981"
    BADGE_BG="#10b981"
else
    OVERALL_LABEL="Some suites failed"
    OVERALL_COLOR="#ef4444"
    BADGE_BG="#ef4444"
fi

cat > reports/index.html << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sound Box — Test Report</title>
<style>
  body { margin: 0; font-family: system-ui, sans-serif; background: #0a0e17; color: #f1f5f9; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding: 2rem 1rem; box-sizing: border-box; }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .subtitle { color: #64748b; font-size: 0.85rem; margin: 0 0 2rem; }
  .badge { display: inline-block; padding: 0.35rem 1rem; border-radius: 999px; background: ${BADGE_BG}; color: #fff; font-weight: 600; font-size: 0.9rem; margin-bottom: 2rem; }
  .card { background: #111827; border-radius: 0.75rem; padding: 1.25rem 1.5rem; width: 100%; max-width: 480px; margin-bottom: 1rem; border: 1px solid #1e293b; }
  .card-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin: 0 0 0.5rem; }
  .card-status { font-size: 1.1rem; font-weight: 600; color: ${UNIT_HTML_COLOR}; margin: 0 0 0.75rem; }
  .card-status.e2e { color: ${E2E_HTML_COLOR}; }
  .card-link { font-size: 0.85rem; }
  .card-link a { color: #a855f7; text-decoration: none; }
  .card-link a:hover { text-decoration: underline; }
  .totals { color: #64748b; font-size: 0.8rem; margin-top: 2rem; }
</style>
</head>
<body>
<h1>Sound Box — Test Report</h1>
<p class="subtitle">${RUN_TS}</p>
<div class="badge">${OVERALL_LABEL}</div>

<div class="card">
  <div class="card-title">Python Unit Tests</div>
  <div class="card-status">${UNIT_HTML_STATUS}</div>
  <div class="card-link">${UNIT_HTML_LINK}</div>
</div>

<div class="card">
  <div class="card-title">Playwright E2E Tests</div>
  <div class="card-status e2e">${E2E_HTML_STATUS}</div>
  <div class="card-link">${E2E_HTML_LINK}</div>
</div>

<p class="totals">Total: ${TOTAL_PASSED} passed &nbsp;|&nbsp; ${TOTAL_FAILED} failed</p>
</body>
</html>
HTMLEOF

echo -e "${GREEN}  Report: reports/index.html${NC}"

# Cleanup temp files
rm -f /tmp/soundbox-unit-tests.txt /tmp/soundbox-e2e-tests.txt

exit $OVERALL_EXIT
