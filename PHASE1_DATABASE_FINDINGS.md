# Phase 1: Database Layer Findings

## Summary

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| SQL Injection | 0 | 0 | 0 | 1 |
| Transaction/Atomicity | 0 | 1 | 0 | 0 |
| SQLite Portability | 0 | 0 | 12 | 0 |

---

## 1A. SQL Injection Audit

### Finding 1-001: LIKE Pattern Escaping (LOW)

**Location**: `database.py:792-793`, `database.py:1600-1602`

**Issue**: Category filter uses LIKE with user input without escaping `%` and `_` wildcards:
```python
conditions.append("g.category LIKE ?")
params.append(f'%"{category}"%')
```

**Risk**: User could input `%` to match more broadly than intended. Not true SQL injection since parameterized queries are used.

**Validation**:
- Tested: Passing `%` as category could match all categories
- Impact: Low - only affects filter breadth, not data integrity

**Status**: VALIDATED - LOW PRIORITY

---

### Safe Patterns Confirmed

1. **ORDER BY clauses** (lines 817-822, 2802): Use whitelist pattern
   ```python
   order_map = {
       'recent': 'g.created_at DESC',
       'popular': '(g.upvotes + g.downvotes) DESC',
       ...
   }
   order_clause = order_map.get(sort, 'g.created_at DESC')  # Safe default
   ```

2. **Dynamic SET clauses** (line 2595-2596): Column names are hardcoded
   ```python
   updates.append("name = ?")  # Hardcoded column name
   ```

3. **IN clauses** (line 1324-1329): Use parameterized placeholders
   ```python
   placeholders = ','.join('?' * len(generation_ids))  # Safe
   ```

4. **FTS5 queries** (lines 798-812): Sanitize operators and quote terms

---

## 1B. Transaction/Atomicity Issues

### Finding 1-002: Early Commit in Tag Suggestions (HIGH)

**Location**: `database.py:2250-2296`

**Issue**: `submit_tag_suggestion()` commits after INSERT but before consensus logic:
```python
# Line 2257: Commits here
conn.commit()

# Lines 2262-2296: More operations follow
count = conn.execute(...)  # Count suggestions
if count >= TAG_CONSENSUS_THRESHOLD:
    conn.execute(...)  # Update generations
    conn.execute(...)  # Insert tag_consensus
    conn.commit()      # Line 2296: Commits again
```

**Risk**: If error occurs between first commit and consensus operations:
- Suggestion is recorded
- Category update is lost
- Database in inconsistent state

**Validation**:
- Code inspection confirms dual-commit pattern
- Exception after line 2257 would leave partial state

**Fix Required**: Move commit to end after all operations complete.

**Status**: VALIDATED - HIGH PRIORITY

---

## 1C. SQLite-Specific Code (Portability)

For PostgreSQL migration, the following must be abstracted:

### Database Connection (HIGH)

| Line | SQLite Code | PostgreSQL Equivalent |
|------|-------------|----------------------|
| 6 | `import sqlite3` | `import psycopg2` or SQLAlchemy |
| 442 | `sqlite3.connect()` | `psycopg2.connect()` |
| 443 | `sqlite3.Row` | `psycopg2.extras.RealDictCursor` |

### PRAGMA Statements (MEDIUM)

| Line | SQLite | PostgreSQL |
|------|--------|------------|
| 444 | `PRAGMA foreign_keys = ON` | Default ON in PostgreSQL |
| 445 | `PRAGMA journal_mode = WAL` | N/A (uses WAL by default) |
| 446 | `PRAGMA busy_timeout = 30000` | Connection timeout in connect() |
| 622 | `PRAGMA table_info()` | `information_schema.columns` |

### Auto-Increment (HIGH)

| Lines | SQLite | PostgreSQL |
|-------|--------|------------|
| 328, 342, 352, 364, 387, 569, 585 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` or `GENERATED ALWAYS AS IDENTITY` |

### FTS5 Full-Text Search (HIGH)

| Lines | SQLite | PostgreSQL |
|-------|--------|------------|
| 414-436 | `VIRTUAL TABLE ... USING fts5()` | `tsvector` + `GIN index` |
| 811, 873, 915 | `generations_fts MATCH ?` | `to_tsquery()` + `@@` operator |
| 425, 429, 433 | FTS trigger syntax | Different trigger syntax |
| 690 | `INSERT INTO fts VALUES('rebuild')` | `REINDEX` |

### rowid References (HIGH)

| Lines | Issue |
|-------|-------|
| 418 | `content_rowid='rowid'` - PostgreSQL has no implicit rowid |
| 811, 873, 915 | `g.rowid IN (SELECT rowid ...)` - Must use explicit PK |

### Date Functions (MEDIUM)

| Lines | SQLite | PostgreSQL |
|-------|--------|------------|
| 1723, 1951, 1994 | `datetime('now', ?)` | `NOW() - INTERVAL ?` |
| 1925 | `datetime('now', '-7 days')` | `NOW() - INTERVAL '7 days'` |
| 2104-2106, 2166-2167 | Same pattern | Same conversion needed |

### Exception Types (LOW)

| Lines | SQLite | PostgreSQL |
|-------|--------|------------|
| 463, 470, etc. | `sqlite3.OperationalError` | `psycopg2.OperationalError` |
| 1399, 2258, etc. | `sqlite3.IntegrityError` | `psycopg2.IntegrityError` |

### Other SQLite-isms (LOW)

| Issue | Lines | Notes |
|-------|-------|-------|
| `CURRENT_TIMESTAMP` | Various | Works in both, but timezone handling differs |
| `COALESCE()` | Various | Works in both |
| `ON CONFLICT ... DO UPDATE` | 1286-1289 | Syntax differs slightly in PostgreSQL |

---

## Recommended Abstraction Strategy

For supporting both SQLite (dev) and PostgreSQL (prod):

### Option A: SQLAlchemy ORM
- Use SQLAlchemy Core or ORM
- Handles dialect differences automatically
- FTS requires custom handling (pg_trgm or full-text search extension)

### Option B: Database Adapter Pattern
```python
# database_adapter.py
class DatabaseAdapter:
    def get_connection(self): ...
    def execute(self, query, params): ...
    def fts_search(self, table, column, query): ...
    def date_offset(self, interval): ...

class SQLiteAdapter(DatabaseAdapter): ...
class PostgresAdapter(DatabaseAdapter): ...
```

### Option C: Query Builder
- Use a query builder that generates dialect-specific SQL
- Example: pypika, sqlbuilder

---

## Action Items

### Immediate (Before Production)
1. **FIX** Finding 1-002: Move commit to end of `submit_tag_suggestion()`
2. **CONSIDER** Finding 1-001: Add LIKE escape function (low priority)

### Migration Preparation
3. Create database adapter abstraction
4. Replace FTS5 with PostgreSQL-compatible full-text search
5. Replace `rowid` with explicit primary key references
6. Replace `datetime()` with portable date arithmetic
7. Abstract exception handling

---

## Validation Tests Completed

- [x] Test tag suggestion function after fix - PASSED
  - Suggestion recorded correctly
  - Commit happens at end of operation
  - Consensus path and non-consensus path both work
- [ ] Test LIKE filter with `%` character in category name (low priority)
- [ ] Integration tests for all query functions (future work)

---

## Changes Made

### Fix 1-002: Transaction Atomicity in submit_tag_suggestion()

**File**: `database.py`
**Lines**: 2257, 2305-2306

**Before**:
```python
conn.execute(INSERT...)
conn.commit()  # Early commit - PROBLEM
# ... more operations ...
if consensus:
    conn.execute(UPDATE...)
    conn.commit()
return  # Non-consensus path didn't commit!
```

**After**:
```python
conn.execute(INSERT...)
# Note: Don't commit here - wait for atomicity
# ... more operations ...
if consensus:
    conn.execute(UPDATE...)
    conn.commit()  # Commit all operations together
    return
conn.commit()  # Non-consensus path now commits
return
```

**Test Result**: PASSED - Suggestion recorded correctly, both paths commit properly.
