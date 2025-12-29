# Soundbox Deep Review - 10 Phase Attack Plan

## Mission
Make this codebase indestructible through systematic review, real testing, and security hardening.

---

## Phase 1: Database Integrity Audit (45 min)

### Attack Vectors to Test
1. **SQL Injection Points**
   - All user-supplied query parameters
   - Search queries with special characters: `'; DROP TABLE--`, `" OR "1"="1`
   - Category filters with malicious input
   - Pagination parameters (limit, offset)

2. **Data Integrity Issues**
   - Orphaned database records (no matching audio file)
   - Audio files without database entries
   - Invalid JSON in category column
   - Duplicate IDs or filenames
   - FTS5 index out of sync with main table

3. **Concurrency Problems**
   - Race conditions in INSERT operations
   - Concurrent category updates
   - Transaction isolation issues

### Files to Audit
- `database.py` - Every SQL query
- Schema definitions
- Migration paths

### Deliverables
- [ ] Fix all SQL injection vulnerabilities
- [ ] Add data validation functions
- [ ] Create integrity check script
- [ ] Document schema

---

## Phase 2: API Security Review (60 min)

### Attack Vectors
1. **Input Validation Failures**
   - Oversized payloads (1GB JSON)
   - Missing required fields
   - Wrong data types
   - Unicode edge cases (null bytes, RTL override)

2. **Path Traversal**
   - `../../../etc/passwd` in file paths
   - Encoded traversal: `%2e%2e%2f`
   - Null byte injection: `file.txt%00.png`

3. **Resource Exhaustion**
   - Unlimited file uploads
   - No rate limiting on generation
   - Memory exhaustion via large requests

4. **Authentication/Authorization**
   - Accessing other users' data
   - Admin functions without auth
   - CSRF on state-changing operations

### Endpoints to Attack
```
POST /api/generate
POST /api/tts/generate
POST /api/upload
POST /api/vote
POST /api/favorite
GET  /api/library
GET  /api/audio/<path>
DELETE /api/delete
```

### Deliverables
- [ ] Input validation on all endpoints
- [ ] Rate limiting implementation
- [ ] Path traversal protection
- [ ] CSRF tokens (if needed)

---

## Phase 3: Frontend JavaScript Audit (60 min)

### Attack Vectors
1. **XSS (Cross-Site Scripting)**
   - Stored XSS via prompt text: `<script>alert(1)</script>`
   - DOM XSS in search results
   - Event handler injection

2. **Memory Leaks**
   - Audio elements not cleaned up
   - Event listeners not removed
   - Intervals/timeouts not cleared
   - WebSocket connections left open

3. **State Management Bugs**
   - Race conditions in async operations
   - Stale closures in callbacks
   - Invalid state transitions

4. **Error Handling**
   - Unhandled promise rejections
   - Network failure recovery
   - Invalid API response handling

### Components to Audit
- Radio player state machine
- Library grid rendering
- Search/filter logic
- Audio loading/playback
- Visualizer

### Deliverables
- [ ] Sanitize all dynamic content
- [ ] Add proper error boundaries
- [ ] Fix memory leaks
- [ ] Add loading states

---

## Phase 4: Audio Pipeline Review (45 min)

### Attack Vectors
1. **File Handling**
   - Malformed audio files
   - Files with wrong extensions
   - Zero-byte files
   - Extremely long filenames

2. **Generation Failures**
   - TTS service unavailable
   - Invalid voice IDs
   - Empty prompts
   - Timeout handling

3. **Storage Issues**
   - Disk full scenarios
   - File permission errors
   - Temp file cleanup failures

### Code Paths to Test
- TTS generation flow
- SFX generation flow
- Music generation flow
- File upload flow
- Waveform generation

### Deliverables
- [ ] Robust error handling
- [ ] File validation
- [ ] Cleanup routines
- [ ] Retry logic

---

## Phase 5: Error Handling Hardening (45 min)

### Systematic Review
1. **Backend (Python)**
   - Every try/except block
   - Exception types caught
   - Error logging completeness
   - User-facing error messages

2. **Frontend (JavaScript)**
   - Promise rejection handling
   - Fetch error handling
   - Event handler try/catch
   - User feedback on errors

3. **External Services**
   - Ollama server failures
   - TTS service failures
   - Network timeouts
   - Partial failures

### Deliverables
- [ ] Comprehensive error handling
- [ ] Graceful degradation
- [ ] User-friendly error messages
- [ ] Structured logging

---

## Phase 6: Build Real Tests (90 min)

### Test Categories

1. **Unit Tests (Python)**
   - Database functions
   - Category logic
   - Input validation
   - File path handling

2. **Integration Tests**
   - API endpoint responses
   - Database operations
   - File system operations

3. **E2E Tests (Playwright)**
   - User workflows
   - Error scenarios
   - Edge cases
   - Performance benchmarks

### Anti-Cheat Principles
- No mocking of core logic
- Real database operations
- Actual file system tests
- Network failure simulation
- Timing-based tests for race conditions

### Deliverables
- [ ] Python unit test suite
- [ ] API integration tests
- [ ] Expanded Playwright tests
- [ ] Test coverage report

---

## Phase 7: Code Organization (45 min)

### Cleanup Tasks
1. **Remove Dead Code**
   - Unused functions
   - Commented-out blocks
   - Legacy migrations

2. **Consolidate Duplicates**
   - Similar validation logic
   - Repeated error handling
   - Copy-pasted SQL

3. **Improve Structure**
   - Extract constants
   - Group related functions
   - Add type hints
   - Improve naming

4. **Documentation**
   - Function docstrings
   - API documentation
   - Architecture overview

### Deliverables
- [ ] Clean, organized code
- [ ] No dead code
- [ ] Consistent style
- [ ] Basic documentation

---

## Phase 8: Performance Optimization (45 min)

### Analysis Areas
1. **Database Queries**
   - N+1 query patterns
   - Missing indexes
   - Unnecessary joins
   - Large result sets

2. **Frontend**
   - Initial load time
   - Scroll performance
   - Memory usage
   - Animation jank

3. **API Response Times**
   - Slow endpoints
   - Unnecessary data transfer
   - Caching opportunities

### Deliverables
- [ ] Add missing indexes
- [ ] Optimize slow queries
- [ ] Implement caching
- [ ] Reduce payload sizes

---

## Phase 9: Security Hardening (45 min)

### Hardening Checklist
1. **HTTP Headers**
   - Content-Security-Policy
   - X-Content-Type-Options
   - X-Frame-Options
   - Strict-Transport-Security

2. **Input Sanitization**
   - HTML encoding
   - SQL parameterization
   - Path canonicalization
   - JSON validation

3. **File Security**
   - Restricted upload types
   - File size limits
   - Safe file serving
   - No directory listing

4. **Configuration**
   - Debug mode disabled
   - Secret keys secured
   - Error details hidden
   - Logging sanitized

### Deliverables
- [ ] Security headers middleware
- [ ] Input sanitization library
- [ ] Secure configuration
- [ ] Security audit log

---

## Phase 10: Final Validation (30 min)

### Validation Steps
1. **Run All Tests**
   - Unit tests pass
   - Integration tests pass
   - E2E tests pass

2. **Manual Testing**
   - All major features work
   - Error handling verified
   - Performance acceptable

3. **Code Review**
   - All changes reviewed
   - No regressions
   - Clean commit history

4. **Documentation**
   - Changes documented
   - README updated
   - API docs current

### Final Commit
- Squash/organize commits
- Write comprehensive commit message
- Tag release version

---

## Execution Rules

1. **Commit frequently** - After each meaningful change
2. **Test before commit** - Ensure nothing breaks
3. **Document as you go** - Add comments explaining fixes
4. **Preserve functionality** - Don't change behavior unless fixing bugs
5. **Log everything** - Track what was found and fixed

## Progress Tracking

| Phase | Status | Bugs Found | Bugs Fixed | Notes |
|-------|--------|------------|------------|-------|
| 1 | Complete | 1 | 1 | FTS5 injection vulnerability fixed |
| 2 | Complete | 2 | 2 | Added rate limiting + input validation |
| 3 | Complete | 0 | 0 | Frontend already secure (escapeHtml/escapeJsString) |
| 4 | Complete | 0 | 0 | Audio pipeline well-designed |
| 5 | Complete | 1 | 1 | Fixed bare except clause |
| 6 | Complete | 0 | 0 | Added Python unit tests |
| 7 | Complete | 0 | 0 | Code already clean |
| 8 | Complete | 0 | 2 | Added composite indexes |
| 9 | Complete | 0 | 1 | Added CSP header |
| 10 | Complete | 0 | 0 | All validations passed |
