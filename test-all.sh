#!/bin/bash
# Sound Box - Full Test Suite Runner
# Runs all test suites: Python unit tests + Playwright E2E tests
#
# Usage: ./test-all.sh [options]
#   --skip-e2e    Skip Playwright E2E tests
#   --skip-unit   Skip Python unit tests

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
    ./venv/bin/python -m pytest tests/test_*.py -v 2>&1 | tee /tmp/soundbox-unit-tests.txt
    UNIT_EXIT=${PIPESTATUS[0]}
    set -e

    UNIT_PASSED=$(grep -cE "PASSED" /tmp/soundbox-unit-tests.txt 2>/dev/null || echo "0")
    UNIT_FAILED=$(grep -cE "FAILED" /tmp/soundbox-unit-tests.txt 2>/dev/null || echo "0")

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

    E2E_PASSED=$(grep -oE '[0-9]+ passed' /tmp/soundbox-e2e-tests.txt | tail -1 | grep -oE '[0-9]+' || echo "0")
    E2E_FAILED=$(grep -oE '[0-9]+ failed' /tmp/soundbox-e2e-tests.txt | tail -1 | grep -oE '[0-9]+' || echo "0")

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

# Cleanup temp files
rm -f /tmp/soundbox-unit-tests.txt /tmp/soundbox-e2e-tests.txt

exit $OVERALL_EXIT
