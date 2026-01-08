#!/bin/bash
# Sound Box E2E Test Runner
# Usage: ./test.sh [options]
#
# Options:
#   --headed    Run tests with visible browser
#   --debug     Run in debug mode
#   --report    Open HTML report after tests
#   <pattern>   Run only tests matching pattern (e.g., ./test.sh search)

set -e

cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sound Box E2E Test Suite${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if server is running
echo -e "${YELLOW}Checking server status...${NC}"
if curl -s http://localhost:5309/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server is running on http://localhost:5309${NC}"
else
    echo -e "${RED}✗ Server not running. Starting server...${NC}"
    ./venv/bin/python app.py &
    SERVER_PID=$!
    echo "  Started server (PID: $SERVER_PID)"
    sleep 5

    if ! curl -s http://localhost:5309/ > /dev/null 2>&1; then
        echo -e "${RED}✗ Failed to start server${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Server started${NC}"
fi

echo ""

# Parse arguments
ARGS=""
OPEN_REPORT=false
PATTERN=""

for arg in "$@"; do
    case $arg in
        --headed)
            ARGS="$ARGS --headed"
            ;;
        --debug)
            ARGS="$ARGS --debug"
            ;;
        --report)
            OPEN_REPORT=true
            ;;
        *)
            PATTERN="$arg"
            ;;
    esac
done

# Build test command
if [ -n "$PATTERN" ]; then
    echo -e "${YELLOW}Running tests matching: ${PATTERN}${NC}"
    TEST_CMD="npx playwright test $PATTERN $ARGS"
else
    echo -e "${YELLOW}Running all tests...${NC}"
    TEST_CMD="npx playwright test $ARGS"
fi

echo ""

# Run tests and capture output
START_TIME=$(date +%s)

# Run tests with custom reporter format
$TEST_CMD --reporter=list 2>&1 | tee /tmp/test-output.txt
TEST_EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Extract pass/fail counts from output
PASSED=$(grep -oE '[0-9]+ passed' /tmp/test-output.txt | tail -1 | grep -oE '[0-9]+' || echo "0")
FAILED=$(grep -oE '[0-9]+ failed' /tmp/test-output.txt | tail -1 | grep -oE '[0-9]+' || echo "0")
TOTAL=$((PASSED + FAILED))

if [ "$TOTAL" -gt 0 ]; then
    PASS_RATE=$((PASSED * 100 / TOTAL))
else
    PASS_RATE=0
fi

echo ""
echo -e "  Tests Run:    ${TOTAL}"
echo -e "  ${GREEN}Passed:       ${PASSED}${NC}"
if [ "$FAILED" -gt 0 ]; then
    echo -e "  ${RED}Failed:       ${FAILED}${NC}"
else
    echo -e "  Failed:       ${FAILED}"
fi
echo -e "  Pass Rate:    ${PASS_RATE}%"
echo -e "  Duration:     ${DURATION}s"
echo ""

# Show pass rate bar
BAR_WIDTH=40
FILLED=$((PASS_RATE * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))

printf "  ["
for ((i=0; i<FILLED; i++)); do printf "${GREEN}█${NC}"; done
for ((i=0; i<EMPTY; i++)); do printf "░"; done
printf "] ${PASS_RATE}%%\n"

echo ""

# Status message
if [ "$PASS_RATE" -ge 90 ]; then
    echo -e "  ${GREEN}✓ Excellent! Test coverage target (90%) achieved.${NC}"
elif [ "$PASS_RATE" -ge 80 ]; then
    echo -e "  ${YELLOW}◐ Good coverage. ${NC}$((90 - PASS_RATE))% more needed for target."
else
    echo -e "  ${RED}✗ Coverage below target.${NC} Consider fixing failing tests."
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Show HTML report location
echo ""
echo -e "  ${YELLOW}Reports:${NC}"
echo "    HTML Report: playwright-report/index.html"
echo "    Screenshots: test-results/"
echo ""

# Open report if requested
if [ "$OPEN_REPORT" = true ]; then
    echo -e "${YELLOW}Opening HTML report...${NC}"
    npx playwright show-report
fi

# Clean up temp file
rm -f /tmp/test-output.txt

exit $TEST_EXIT_CODE
