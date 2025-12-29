# Soundbox Application - 10 Phase Bug Review Plan

## Overview
Comprehensive review of the Soundbox application (22,000+ lines of code) covering Flask backend, SQLite database, frontend UI, audio generation, and all supporting scripts.

---

## Phase 1: Database Integrity & Schema Review
**Focus**: database.py (2987 lines) + soundbox.db

### Tasks
- [ ] Verify all table schemas are correct and have proper indexes
- [ ] Check for SQL injection vulnerabilities in all queries
- [ ] Validate foreign key relationships and constraints
- [ ] Review migration/upgrade paths for schema changes
- [ ] Audit `voice_id` column usage (recent addition)
- [ ] Verify category JSON storage format consistency
- [ ] Check for orphaned records (files without DB entries, DB entries without files)
- [ ] Review connection pooling and transaction handling
- [ ] Test concurrent write operations for race conditions
- [ ] Validate FTS5 search table synchronization

### Key Files
- `database.py` - All database operations
- `soundbox.db` - Production database

---

## Phase 2: API Endpoint Security & Validation
**Focus**: app.py API routes (4273 lines)

### Tasks
- [ ] Audit all `/api/*` endpoints for input validation
- [ ] Check file upload handling for path traversal attacks
- [ ] Verify rate limiting on generation endpoints
- [ ] Review authentication/authorization (if any)
- [ ] Check for CSRF protection on state-changing operations
- [ ] Validate JSON request parsing and error handling
- [ ] Review file serving for directory traversal
- [ ] Check for information leakage in error responses
- [ ] Audit external service calls (Ollama, TTS, etc.)
- [ ] Verify timeout handling on long-running operations

### Key Endpoints to Review
- `/api/tts/generate` - TTS generation
- `/api/generate` - Audio/music generation
- `/api/library` - Library listing
- `/api/upload` - File uploads
- `/api/vote`, `/api/favorite` - User actions

---

## Phase 3: Frontend JavaScript Review
**Focus**: templates/index.html (15106 lines)

### Tasks
- [ ] Check for XSS vulnerabilities in dynamic content rendering
- [ ] Audit DOM manipulation for injection risks
- [ ] Review event handlers for proper cleanup (memory leaks)
- [ ] Validate audio player state management
- [ ] Check WebSocket/SSE handling (if used)
- [ ] Review error handling in async operations
- [ ] Audit localStorage/sessionStorage usage
- [ ] Check for race conditions in UI updates
- [ ] Validate form submissions and input sanitization
- [ ] Review keyboard navigation and focus management

### UI Components to Audit
- Radio player
- Library grid/list views
- Search functionality
- Category sidebar
- Now playing display
- Visualizer

---

## Phase 4: Audio Generation Pipeline
**Focus**: Audio file creation and storage

### Tasks
- [ ] Verify TTS API integration error handling
- [ ] Check audio file format validation
- [ ] Review temp file cleanup processes
- [ ] Validate filename generation (collisions, special chars)
- [ ] Check audio duration calculation accuracy
- [ ] Review waveform generation process
- [ ] Verify proper error responses for failed generations
- [ ] Check disk space handling
- [ ] Review concurrent generation handling
- [ ] Validate audio file integrity checks

### Key Flows
- TTS voice generation
- SFX generation (external API)
- Music generation (external API)
- File import/upload

---

## Phase 5: Category & Tagging System
**Focus**: Categorization logic and display

### Tasks
- [ ] Verify `SPEECH_CATEGORIES` implementation
- [ ] Check `SFX_CATEGORIES` and `MUSIC_CATEGORIES` completeness
- [ ] Validate `get_category_counts()` accuracy
- [ ] Review category filter logic in library API
- [ ] Check sidebar category display and counts
- [ ] Verify LLM categorization prompt effectiveness
- [ ] Review deterministic categorization rules
- [ ] Check for category name normalization issues
- [ ] Validate multi-category storage format
- [ ] Test category search integration

### Key Files
- `database.py` - Category definitions
- `scripts/categorize_*.py` - Categorization scripts
- `templates/index.html` - Category UI

---

## Phase 6: Search & Filtering
**Focus**: FTS5 search and filter functionality

### Tasks
- [ ] Test FTS5 query syntax edge cases
- [ ] Check search result ranking accuracy
- [ ] Verify combined filter + search behavior
- [ ] Review search input sanitization
- [ ] Test special characters in search queries
- [ ] Check search performance on large datasets
- [ ] Validate pagination with search results
- [ ] Review search highlighting (if implemented)
- [ ] Test empty search results handling
- [ ] Verify search index updates on new content

---

## Phase 7: Radio Player & Playback
**Focus**: Audio playback functionality

### Tasks
- [ ] Test audio format compatibility
- [ ] Review playlist/queue management
- [ ] Check shuffle algorithm randomness
- [ ] Verify repeat mode functionality
- [ ] Test play/pause state persistence
- [ ] Review volume control and muting
- [ ] Check audio loading error handling
- [ ] Test network interruption recovery
- [ ] Verify visualizer synchronization
- [ ] Review keyboard shortcuts functionality

### Audio Formats to Test
- WAV
- MP3
- OGG
- FLAC (if supported)

---

## Phase 8: Error Handling & Logging
**Focus**: Application resilience

### Tasks
- [ ] Review all try/except blocks for proper handling
- [ ] Check error message user-friendliness
- [ ] Verify error logging completeness
- [ ] Review Flask error handlers (404, 500, etc.)
- [ ] Check JavaScript error boundary implementation
- [ ] Verify graceful degradation on service failures
- [ ] Review timeout configurations
- [ ] Check retry logic for transient failures
- [ ] Validate error state UI feedback
- [ ] Review console error suppression (if any)

---

## Phase 9: Performance & Resource Management
**Focus**: Speed and efficiency

### Tasks
- [ ] Profile database query performance
- [ ] Check for N+1 query patterns
- [ ] Review pagination implementation
- [ ] Check image/waveform lazy loading
- [ ] Verify memory cleanup in long sessions
- [ ] Review browser caching headers
- [ ] Check gzip compression
- [ ] Profile JavaScript bundle size
- [ ] Review animation performance
- [ ] Check for blocking operations on main thread

### Performance Metrics
- Initial page load time
- Library grid scroll performance
- Search response time
- Audio start latency

---

## Phase 10: Integration & End-to-End Testing
**Focus**: System-wide functionality

### Tasks
- [ ] Review existing Playwright tests coverage
- [ ] Identify missing test scenarios
- [ ] Test cross-browser compatibility
- [ ] Verify mobile/responsive behavior
- [ ] Test offline functionality (if any)
- [ ] Review test data setup/teardown
- [ ] Check test flakiness and reliability
- [ ] Verify CI/CD test integration
- [ ] Test backup/restore procedures
- [ ] Review deployment process

### Existing Test Files
- `tests/user-journeys.spec.js`
- `tests/search.spec.js`
- `tests/navigation.spec.js`
- `tests/categorization.spec.js`
- `tests/voting-favorites.spec.js`
- `tests/accessibility.spec.js`
- `tests/responsive.spec.js`
- `tests/asset-manager.spec.js`
- `tests/visualizer-fps.spec.js`

---

## Execution Notes

### Priority Order
1. **Critical**: Phase 2 (Security), Phase 4 (Audio Generation)
2. **High**: Phase 1 (Database), Phase 3 (Frontend)
3. **Medium**: Phase 5-7 (Features)
4. **Lower**: Phase 8-10 (Quality)

### Tools Needed
- SQLite browser for database inspection
- Browser DevTools for frontend debugging
- Network inspector for API testing
- Python debugger for backend tracing

### Documentation
- Create bug tickets for each issue found
- Document reproduction steps
- Note severity (Critical/High/Medium/Low)
- Track fixes and verification

---

## Quick Reference

| Phase | Focus | Lines of Code | Priority |
|-------|-------|---------------|----------|
| 1 | Database | ~3000 | High |
| 2 | API Security | ~4300 | Critical |
| 3 | Frontend | ~15000 | High |
| 4 | Audio Pipeline | Scattered | Critical |
| 5 | Categories | ~500 | Medium |
| 6 | Search | ~300 | Medium |
| 7 | Radio Player | ~1000 | Medium |
| 8 | Error Handling | All files | Lower |
| 9 | Performance | All files | Lower |
| 10 | Integration | ~500 (tests) | Lower |
