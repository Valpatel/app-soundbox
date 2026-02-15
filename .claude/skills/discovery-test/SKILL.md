---
name: discovery-test
description: Run the full service discovery test suite (bash + Playwright)
disable-model-invocation: true
allowed-tools: Bash
argument-hint: ""
---

## Discovery Test Suite

Run all service discovery tests to verify mDNS, manifest, agent card, MCP, and OpenAPI.

Steps:
1. Run bash tests:
   ```bash
   bash tests/test-discovery.sh
   ```
2. Run Playwright tests:
   ```bash
   npx playwright test tests/discovery.spec.js --reporter=list
   ```
3. Report summary:
   - Bash: total checks, passed, failed
   - Playwright: total tests, passed, failed
   - List any failures with details
