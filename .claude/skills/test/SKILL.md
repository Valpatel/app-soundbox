---
name: test
description: Run the Playwright test suite against the running Sound Box server
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "[test-file-or-pattern]"
---

## Run Tests

Run the Sound Box Playwright test suite. The server must already be running.

If `$ARGUMENTS` is provided, use it to filter tests:
- A file path runs that specific test file: `npx playwright test tests/$ARGUMENTS`
- A pattern with `--grep` runs matching test names: `npx playwright test --grep "$ARGUMENTS"`

If no arguments provided, run all tests:
```bash
npx playwright test --reporter=list
```

After running, summarize:
1. Total passed / failed / skipped
2. List any failures with the test name and brief error
3. If all pass, confirm success
