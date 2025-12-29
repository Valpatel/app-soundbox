# Phase 2: API Security Findings

## Summary

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Authentication | 0 | 0 | 0 | 0 |
| Authorization/IDOR | 0 | 0 | 1 | 2 |
| Security Headers | 0 | 0 | 1 | 0 |

---

## 2A. Authentication Audit

### Positive Findings

All critical endpoints properly use authentication decorators:

| Pattern | Usage |
|---------|-------|
| `@require_auth` | Voting, favorites, playlists, admin, user stats, generation |
| `@optional_auth` | History, rating, tag suggestions, playlist viewing |
| `@require_auth_or_localhost` | Generation (allows batch scripts) |

### Auth Decorator Implementation (Verified)

- `require_auth` (line 579): Validates Bearer token with accounts server
- `optional_auth` (line 646): Sets user context if token present, allows anonymous
- `require_auth_or_localhost` (line 607): Allows localhost bypass for batch generation

### Token Handling

- Uses `request.user_id` from verified auth token throughout
- Admin checks use `request.user.get('is_admin')` from verified token
- No hardcoded credentials found

---

## 2B. Authorization/IDOR Audit

### Finding 2-001: Widget Radio Favorites IDOR (MEDIUM)

**Location**: `app.py:4079-4082`

**Issue**: The `/api/radio?station=favorites&user_id=X` endpoint accepts `user_id` from query parameter without authentication:

```python
if station == 'favorites':
    user_id = request.args.get('user_id')
    if user_id:
        tracks = db.get_random_favorites(user_id, count=limit, model=model)
```

**Risk**: Anyone can access any user's favorites by knowing their user_id.

**Mitigating Factors**:
- Favorites are just references to public tracks (not private data)
- An authenticated endpoint `/api/radio/favorites` exists for secure access
- Designed for widget embedding (needs CORS)

**Recommendation**: Consider if favorites should be public per-user. If not:
- Require auth for favorites station
- Or add a user setting for "public favorites"

**Status**: DOCUMENTED - Design decision needed

---

### Finding 2-002: Download Analytics Spoofing (LOW)

**Location**: `app.py:3587-3588`

**Issue**: Download tracking uses client-provided `user_id`:

```python
user_id = request.args.get('user_id')
db.record_download(gen_id, user_id, 'wav')
```

**Risk**: Analytics can be polluted with fake user IDs.

**Impact**: Low - only affects statistics, not access control.

**Recommendation**: Use `@optional_auth` and fall back to `request.user_id`.

**Status**: VALIDATED - LOW PRIORITY

---

### Finding 2-003: Library user_id Filter (SAFE)

**Location**: `app.py:2247`

**Analysis**: The `user_id` parameter in `/api/library` only filters the **public** library. Private content is handled by `/api/my-generations` which requires auth.

**Status**: SAFE - No action needed

---

## 2C. Security Headers Audit

### Finding 2-004: Missing Security Headers (MEDIUM)

**Location**: `app.py:376-381` (after_request)

**Issue**: Only cache control headers are set. Missing recommended security headers:

| Header | Current | Recommended |
|--------|---------|-------------|
| Content-Security-Policy | Missing | Add for HTML pages |
| X-Frame-Options | Missing | `DENY` or `SAMEORIGIN` |
| X-Content-Type-Options | Missing | `nosniff` |
| X-XSS-Protection | Missing | `1; mode=block` |
| Strict-Transport-Security | Missing | For HTTPS deployment |

**Impact**: Medium - reduces defense-in-depth for XSS/clickjacking.

**Recommendation**: Add security headers in `after_request`:

```python
@app.after_request
def add_security_headers(response):
    if response.content_type and 'text/html' in response.content_type:
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # CSP should be customized based on needs
    return response
```

**Status**: VALIDATED - MEDIUM PRIORITY

---

## Safe Patterns Confirmed

### Path Traversal Protection
All file-serving endpoints use:
1. `is_safe_filename()` validation
2. `os.path.realpath()` + prefix check

### IDOR Prevention
Protected endpoints use `request.user_id` from verified token:
- `/api/favorites/*` - line 2824, 2844, 2858, 2872, 2887
- `/api/playlists/*` - line 2976, 3005, 3038, 3069, 3082, 3099, 3112
- `/api/my-generations/*` - line 2305, 2346, 2383

### Admin Check Pattern
Admin-only endpoints consistently use:
```python
if not request.user.get('is_admin'):
    return jsonify({'error': 'Admin access required'}), 403
```

---

## Action Items

### Immediate
1. **FIX** Finding 2-004: Add security headers to HTML responses

### Design Decision Required
2. **REVIEW** Finding 2-001: Decide if favorites should be public via widget

### Low Priority
3. **CONSIDER** Finding 2-002: Use auth for download tracking

---

## Changes Made

### Fix 2-004: Security Headers Added

**File**: `app.py:376-394`

**Before**:
```python
@app.after_request
def add_cache_headers(response):
    """Disable caching for HTML pages..."""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache...'
    return response
```

**After**:
```python
@app.after_request
def add_security_headers(response):
    """Add security headers and cache control for responses."""
    # Security headers for all responses
    response.headers['X-Content-Type-Options'] = 'nosniff'

    if response.content_type and 'text/html' in response.content_type:
        # Cache control + security headers for HTML
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

**Headers Added**:
| Header | Value | Protection |
|--------|-------|------------|
| X-Content-Type-Options | nosniff | Prevents MIME sniffing |
| X-Frame-Options | SAMEORIGIN | Prevents clickjacking |
| X-XSS-Protection | 1; mode=block | XSS filter (legacy browsers) |
| Referrer-Policy | strict-origin-when-cross-origin | Limits referrer leakage |

**Test Result**: Syntax verified. Server restart required for runtime test.
