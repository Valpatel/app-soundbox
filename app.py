"""
Sound Box - AI Audio Generation Server

Flask server that generates music and sound effects from text prompts
using Meta's AudioCraft models (MusicGen/AudioGen). Features priority
queue processing, quality analysis with auto-retry, and spectrogram
visualization.

See docs/ARCHITECTURE.md for system overview.
"""
import os
import hashlib
from dotenv import load_dotenv
load_dotenv()  # Load .env file
import uuid
import json
import threading
import queue
import time
from datetime import datetime
from functools import wraps
from collections import OrderedDict
import torch

# =============================================================================
# Open Access Mode - Allow unauthenticated usage
# =============================================================================
# When enabled, auth decorators create anonymous users from IP addresses.
# Rate limits still apply per-IP. Localhost/whitelisted IPs get creator tier.
OPEN_ACCESS_MODE = os.environ.get('OPEN_ACCESS_MODE', '').lower() in ('1', 'true', 'yes')

# IP whitelist for elevated privileges (creator-tier limits)
_ip_whitelist_raw = os.environ.get('IP_WHITELIST', '')
IP_WHITELIST = set(ip.strip() for ip in _ip_whitelist_raw.split(',') if ip.strip())

if OPEN_ACCESS_MODE:
    print("[Config] OPEN ACCESS MODE enabled - no login required")
    if IP_WHITELIST:
        print(f"[Config] IP whitelist: {', '.join(IP_WHITELIST)}")
import numpy as np
import librosa
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, jsonify, send_file
from flask_limiter import Limiter
# NOTE: Do NOT use flask_limiter.util.get_remote_address - it trusts X-Forwarded-For
# which allows attackers to spoof localhost and bypass auth/rate limits
import requests
from audiocraft.models import MusicGen, AudioGen, MAGNeT
from audiocraft.data.audio import audio_write
from piper import PiperVoice
import wave
import io
import database as db
import voice_licenses
import backup

# Voice models directory
VOICES_DIR = os.path.join(os.path.dirname(__file__), "models", "voices")
voice_models = OrderedDict()  # Cached voice models with LRU eviction
voice_models_lock = threading.Lock()  # Thread safety for voice cache
_VOICE_CACHE_MAX_SIZE = 10  # Max voices to keep in memory (each ~100-300MB)

METADATA_FILE = "generations.json"
OUTPUT_DIR = "generated"
SPECTROGRAMS_DIR = "spectrograms"

os.makedirs(SPECTROGRAMS_DIR, exist_ok=True)


def generate_spectrogram(audio_path, output_path):
    """Generate a mel spectrogram image from audio file."""
    try:
        y, sr = librosa.load(audio_path, sr=None)

        # Generate mel spectrogram
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)

        # Dark theme styling
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 3))
        fig.patch.set_facecolor('#1a1a2e')
        ax.set_facecolor('#1a1a2e')

        img = librosa.display.specshow(S_dB, x_axis='time', y_axis='mel',
                                        sr=sr, fmax=8000, ax=ax, cmap='magma')
        cbar = fig.colorbar(img, ax=ax, format='%+2.0f dB')
        cbar.ax.yaxis.set_tick_params(color='white')
        cbar.outline.set_edgecolor('white')
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')

        # Style axes
        ax.set_xlabel('Time', color='white')
        ax.set_ylabel('Hz', color='white')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_edgecolor('#444')

        plt.tight_layout()

        # Save
        plt.savefig(output_path, dpi=100, bbox_inches='tight',
                    facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        return True
    except Exception as e:
        print(f"Spectrogram generation failed: {e}")
        return False


def analyze_audio_quality(audio_path, sample_rate=32000):
    """Analyze audio for quality issues. Returns quality score 0-100 and issues list.

    Note: Thresholds are set conservatively to avoid false positives.
    Only flag truly problematic audio, not just unusual characteristics.
    """
    try:
        # Wait a moment for file to be fully written
        import time
        time.sleep(0.5)
        y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)

        issues = []
        scores = []

        # 1. Check for severe clipping (values near ±1.0 for extended periods)
        clipping_ratio = np.mean(np.abs(y) > 0.98)
        if clipping_ratio > 0.05:  # More than 5% clipping is bad
            issues.append(f"Clipping detected ({clipping_ratio*100:.1f}%)")
            scores.append(max(0, 100 - clipping_ratio * 300))
        else:
            scores.append(100)

        # 2. Check for complete silence/very low energy
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = np.mean(rms)
        if mean_rms < 0.005:  # Only flag near-silence
            issues.append("Very low audio level")
            scores.append(40)
        else:
            scores.append(100)

        # 3. Check for extreme high-frequency noise/static (only severe cases)
        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        high_freq_mask = freqs > 14000  # Higher threshold
        if np.any(high_freq_mask):
            high_freq_energy = np.mean(S[high_freq_mask, :])
            total_energy = np.mean(S)
            hf_ratio = high_freq_energy / (total_energy + 1e-10)
            if hf_ratio > 0.5:  # Only flag extreme cases
                issues.append("High-frequency noise detected")
                scores.append(max(0, 100 - hf_ratio * 100))
            else:
                scores.append(100)
        else:
            scores.append(100)

        # 4. Check spectral flatness - only flag pure noise
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        mean_flatness = np.mean(flatness)
        if mean_flatness > 0.7:  # Only pure noise/static
            issues.append("Static/noise-like audio")
            scores.append(max(0, 100 - mean_flatness * 100))
        else:
            scores.append(100)

        # Overall quality score
        quality_score = int(np.mean(scores))

        # Only mark as bad if score is very low AND has critical issues
        return {
            'score': quality_score,
            'issues': issues,
            'is_good': quality_score >= 50 or len(issues) == 0  # More lenient
        }

    except Exception as e:
        print(f"Quality analysis failed: {e}")
        # Return unknown state - allow through but flag as unanalyzed
        return {'score': None, 'issues': ['analysis_failed'], 'is_good': True, 'analysis_skipped': True}


# Subscription tiers (matching Valnet/Graphlings):
# - free: No subscription ($0/month)
# - supporter: $5/month (supporter-monthly)
# - premium: $10/month (premium-monthly)
# - creator: $20/month (ai-graphling-monthly)

# Priority levels (lower = higher priority)
PRIORITY_LEVELS = {
    'admin': 0,
    'creator': 1,   # $20/month - highest paying tier
    'premium': 2,   # $10/month
    'supporter': 3, # $5/month
    'free': 4
}

# Queue and rate limits by user tier
MAX_QUEUE_SIZE = 100  # Total jobs in queue
MAX_PENDING_PER_USER = {
    'creator': 20,    # Whitelisted IPs / admin
    'premium': 10,    # Premium tier
    'supporter': 5,   # Supporter tier
    'free': 3         # Free / anonymous users
}

# Generation limits by tier
# per_hour: max generations per hour
# max_duration: max audio duration in seconds
GENERATION_LIMITS = {
    'creator': {'per_hour': 60, 'max_duration': 180},   # Whitelisted IPs / admin
    'premium': {'per_hour': 30, 'max_duration': 120},   # Premium tier
    'supporter': {'per_hour': 15, 'max_duration': 60},  # Supporter tier
    'free': {'per_hour': 10, 'max_duration': 60}        # Free / anonymous users
}

# =============================================================================
# Skip-the-Queue Pricing Configuration
# =============================================================================
# Easy to tune - just update these values to change pricing
#
# Format: (max_duration, aura_cost, label)
# Jobs are matched to the first tier where duration <= max_duration

SKIP_QUEUE_PRICING = [
    # (max_seconds, aura_cost, user_friendly_label)
    (10,  1,  "Short SFX"),      # 1-10s: 1 Aura
    (30,  3,  "Medium clip"),    # 11-30s: 3 Aura
    (60,  5,  "Long SFX"),       # 31-60s: 5 Aura
    (120, 10, "Song"),           # 61-120s: 10 Aura
    (999, 15, "Long song"),      # 121s+: 15 Aura
]

def get_skip_cost(duration_seconds):
    """Calculate Aura cost to skip the queue based on job duration."""
    for max_duration, cost, _ in SKIP_QUEUE_PRICING:
        if duration_seconds <= max_duration:
            return cost
    return SKIP_QUEUE_PRICING[-1][1]  # Fallback to highest tier


def get_skip_pricing_info():
    """Get pricing info for UI display."""
    return [
        {
            'max_duration': max_dur,
            'cost': cost,
            'label': label
        }
        for max_dur, cost, label in SKIP_QUEUE_PRICING
    ]


def spend_aura(token, amount, item_description, job_id=None):
    """
    Spend Aura from user's wallet via Valnet API.

    Args:
        token: User's auth token
        amount: Amount of Aura to spend
        item_description: What the Aura is being spent on
        job_id: Optional job ID for metadata

    Returns:
        dict with 'success', 'new_balance', 'error' keys
    """
    try:
        response = requests.post(
            f'{ACCOUNTS_URL}/api/wallet/spend',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'amount': amount,
                'currency': 'aura',
                'item': item_description,
                'app_id': 'soundbox',
                'metadata': {'job_id': job_id} if job_id else {}
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'new_balance': data.get('new_balance'),
                'transaction_id': data.get('transaction_id')
            }
        else:
            try:
                error = response.json().get('detail', 'Payment failed')
            except (ValueError, requests.exceptions.JSONDecodeError):
                error = 'Payment failed'
            return {'success': False, 'error': error}

    except requests.RequestException as e:
        print(f"[Aura] Spend request failed: {e}")
        return {'success': False, 'error': 'Payment service unavailable'}

def get_user_tier(user):
    """
    Determine user subscription tier from Graphlings/Valnet user data.

    Returns one of: 'creator', 'premium', 'supporter', 'free', or None (not authenticated)

    Tiers match Valnet subscription products:
    - creator: ai-graphling-monthly ($20/mo)
    - premium: premium-monthly ($10/mo)
    - supporter: supporter-monthly ($5/mo)
    - free: no active subscription
    """
    if not user:
        return None  # Not authenticated

    # Check for admin flag (admins get creator treatment)
    if user.get('is_admin') or user.get('role') == 'admin':
        return 'creator'

    # Check subscription_tier field (set directly by Valnet)
    sub_tier = user.get('subscription_tier') or user.get('tier')
    if sub_tier:
        tier_lower = sub_tier.lower()
        if tier_lower in ('creator', 'ai-graphling', 'ai_graphling'):
            return 'creator'
        if tier_lower in ('premium', 'pro'):
            return 'premium'
        if tier_lower in ('supporter', 'plus', 'basic'):
            return 'supporter'

    # Check subscription object (from Valnet)
    subscription = user.get('subscription') or user.get('plan') or {}
    if isinstance(subscription, str):
        # Simple string plan_id
        plan = subscription.lower()
        if 'ai-graphling' in plan or 'creator' in plan:
            return 'creator'
        if 'premium' in plan:
            return 'premium'
        if 'supporter' in plan or 'plus' in plan:
            return 'supporter'
    elif isinstance(subscription, dict):
        # Subscription object with plan_id and status
        status = subscription.get('status', '').lower()
        plan_id = subscription.get('plan_id', '').lower()
        tier = subscription.get('tier', '').lower()

        # Only count active or trialing subscriptions
        if status in ('active', 'trialing'):
            # Check plan_id (e.g., 'ai-graphling-monthly', 'premium-monthly')
            if 'ai-graphling' in plan_id or tier == 'creator':
                return 'creator'
            if 'premium' in plan_id or tier == 'premium':
                return 'premium'
            if 'supporter' in plan_id or tier == 'supporter':
                return 'supporter'

    return 'free'

def count_user_pending_jobs(user_id):
    """Count how many pending/processing jobs a user has."""
    with queue_lock:
        return sum(1 for j in jobs.values()
                   if j.get('user_id') == user_id and j['status'] in ['queued', 'processing'])

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def make_loopable(wav, sample_rate, fade_duration=0.5):
    """Apply crossfade to make audio loop seamlessly."""
    fade_samples = int(fade_duration * sample_rate)
    if fade_samples * 2 >= wav.shape[-1]:
        fade_samples = wav.shape[-1] // 4

    fade_out = torch.linspace(1, 0, fade_samples, device=wav.device)
    fade_in = torch.linspace(0, 1, fade_samples, device=wav.device)

    result = wav.clone()
    result[..., -fade_samples:] = result[..., -fade_samples:] * fade_out
    end_section = wav[..., -fade_samples:] * fade_in
    result[..., :fade_samples] = result[..., :fade_samples] * fade_in + end_section * fade_out
    start_section = wav[..., :fade_samples]
    result[..., -fade_samples:] = result[..., -fade_samples:] + start_section * fade_in

    return result


app = Flask(__name__)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.after_request
def add_security_headers(response):
    """Add security headers and cache control for responses."""
    # Security headers for all responses
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Additional security headers for HTML pages
    if response.content_type and 'text/html' in response.content_type:
        # Cache control for development
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        # Security headers
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Content Security Policy - prevent XSS and injection attacks
        # Allow self, inline styles/scripts (needed for the app), and specific external resources
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://graphlings.com https://*.graphlings.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self' https://graphlings.com https://*.graphlings.com; "
            "frame-ancestors 'self'"
        )

    return response


# =============================================================================
# Rate Limiting - Prevent abuse and DoS
# =============================================================================

def get_secure_remote_address():
    """Get the actual remote address without trusting X-Forwarded-For.

    SECURITY: Never trust X-Forwarded-For headers from untrusted sources.
    Attackers can spoof these headers to bypass localhost checks and rate limits.
    Only use request.remote_addr which is set by the WSGI server.
    """
    return request.remote_addr


def _is_mcp_proxy_request():
    """Check if this request was proxied through the MCP server.

    The MCP server sets X-MCP-Proxy: true on all requests it forwards to Flask.
    These requests arrive from localhost (127.0.0.1) but should NOT receive
    localhost privileges (system user, admin, rate limit exemption).

    SECURITY: This header can only reduce privileges, never escalate them.
    A non-localhost attacker sending this header changes nothing (they already
    lack localhost privileges). A localhost process sending it intentionally
    would only downgrade themselves from system to anonymous/free tier.
    """
    return request.headers.get('X-MCP-Proxy') == 'true'


def get_remote_address_or_exempt():
    """Get remote address, but exempt localhost from rate limiting.

    MCP-proxied requests are NOT exempt — they get rate limited under
    a shared 'mcp-proxy' identity to prevent GPU queue flooding.
    """
    addr = get_secure_remote_address()
    # MCP-proxied requests come from localhost but must be rate limited
    if addr in ('127.0.0.1', 'localhost', '::1') and _is_mcp_proxy_request():
        return 'mcp-proxy'
    # Exempt actual localhost (batch generation, admin scripts)
    if addr in ('127.0.0.1', 'localhost', '::1'):
        return None  # Returning None exempts from rate limiting
    return addr


def is_localhost_request():
    """Check if the request originates from localhost.

    Localhost requests (server-side batch generation, admin scripts, etc.)
    are trusted and can bypass certain restrictions like content moderation.

    SECURITY: Uses request.remote_addr directly, NOT X-Forwarded-For.
    MCP-proxied requests are excluded — they come from localhost but should
    not receive system/admin privileges.
    """
    addr = get_secure_remote_address()
    if addr not in ('127.0.0.1', 'localhost', '::1'):
        return False
    # MCP proxy runs on localhost but should not get localhost privileges
    if _is_mcp_proxy_request():
        return False
    return True

limiter = Limiter(
    get_remote_address_or_exempt,
    app=app,
    # No default limits - apply specific limits to sensitive endpoints only
    # Default limits broke the frontend which polls /status every 3 seconds
    default_limits=[],
    storage_uri="memory://",
)

# =============================================================================
# Global Error Handlers - Prevent information leakage
# =============================================================================

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler to prevent information leakage."""
    # Log the full error for debugging
    import traceback
    print(f"[Error] Unhandled exception: {e}")
    traceback.print_exc()

    # Return a generic error message
    return jsonify({
        'error': 'An unexpected error occurred',
        'success': False
    }), 500

@app.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def handle_rate_limit(e):
    """Handle rate limit errors."""
    return jsonify({'error': 'Too many requests - please wait before trying again'}), 429

# =============================================================================
# Authentication - Verify tokens with Graphlings accounts server
# =============================================================================

# Auto-detect accounts server URL based on environment
def get_accounts_url():
    """Get the accounts server URL based on environment."""
    # Check environment variable first
    env_url = os.environ.get('GRAPHLINGS_ACCOUNTS_URL')
    if env_url:
        return env_url.rstrip('/')

    # In production, use the production server
    # In development, assume local server
    return 'http://localhost:8002'

ACCOUNTS_URL = get_accounts_url()

def send_user_notification(user_id, title, message, notification_type='info', data=None):
    """
    Send a notification to a user via the Graphlings/Valnet widget.

    Args:
        user_id: The user's ID
        title: Notification title
        message: Notification message
        notification_type: 'info', 'success', 'warning', 'error'
        data: Optional dict with additional data (e.g., job_id, audio_url)
    """
    try:
        payload = {
            'user_id': user_id,
            'title': title,
            'message': message,
            'type': notification_type,
            'app': 'soundbox',
            'data': data or {}
        }

        response = requests.post(
            f'{ACCOUNTS_URL}/api/notifications/send',
            json=payload,
            timeout=5
        )

        if response.status_code == 200:
            print(f"[Notification] Sent to user {user_id}: {title}")
            return True
        else:
            print(f"[Notification] Failed to send: {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"[Notification] Error sending to user {user_id}: {e}")
        return False

# Token verification cache with LRU eviction to prevent memory exhaustion
# Format: OrderedDict {token: {'user': user_data, 'expires': timestamp}}
_token_cache = OrderedDict()
_token_cache_lock = threading.Lock()
_TOKEN_CACHE_TTL = 300  # 5 minutes
_TOKEN_CACHE_MAX_SIZE = 1000  # Max cached tokens

def _cleanup_token_cache():
    """Remove expired entries and enforce max size (call with lock held)."""
    now = time.time()
    # Remove expired entries
    expired = [k for k, v in _token_cache.items() if v['expires'] <= now]
    for k in expired:
        del _token_cache[k]
    # Enforce max size (remove oldest entries)
    while len(_token_cache) > _TOKEN_CACHE_MAX_SIZE:
        _token_cache.popitem(last=False)

def verify_auth_token(token):
    """
    Verify a JWT token with the Graphlings accounts server.

    Returns user data dict if valid, None if invalid.
    Uses a short-lived LRU cache to reduce load on accounts server.

    SECURITY: Does NOT use expired cache entries on network errors.
    If the accounts server is down, authentication will fail.
    """
    if not token:
        return None

    # Check cache first (with lock for thread safety)
    with _token_cache_lock:
        cached = _token_cache.get(token)
        if cached and cached['expires'] > time.time():
            # Move to end (most recently used)
            _token_cache.move_to_end(token)
            return cached['user']
        # Remove expired entry if present
        if cached:
            del _token_cache[token]

    # Verify with accounts server
    try:
        response = requests.get(
            f'{ACCOUNTS_URL}/api/auth/me',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )

        if response.status_code == 200:
            try:
                user = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                return None
            # Cache the result (with lock)
            with _token_cache_lock:
                _token_cache[token] = {
                    'user': user,
                    'expires': time.time() + _TOKEN_CACHE_TTL
                }
                _cleanup_token_cache()
            return user
        else:
            # Invalid token - ensure not in cache
            with _token_cache_lock:
                _token_cache.pop(token, None)
            return None

    except requests.RequestException as e:
        # Log error but do NOT use expired cache - that's a security risk
        print(f"[Auth] Token verification failed (accounts server error): {e}")
        return None

def get_auth_token():
    """Extract auth token from request headers."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None

def _get_anonymous_user():
    """Create an anonymous user based on IP address for open access mode.

    Returns a synthetic user dict with stable user_id derived from IP hash.
    Whitelisted IPs and localhost get creator-tier privileges.
    """
    ip = get_secure_remote_address()
    user_id = 'anon_' + hashlib.sha256(ip.encode()).hexdigest()[:12]
    is_whitelisted = ip in IP_WHITELIST or is_localhost_request()

    return {
        'id': user_id,
        'username': f'user_{user_id[-6:]}',
        'is_admin': is_localhost_request(),
        'subscription_tier': 'creator' if is_whitelisted else 'free',
        'account_type': 'adult',
        'email_verified': True,
        'open_access': True
    }


def _apply_user_to_request(user):
    """Set request.user, request.user_id, and request.is_adult from user dict."""
    request.user = user
    request.user_id = user.get('id')
    request.is_adult = (
        user.get('account_type') == 'adult' or
        (user.get('account_type') != 'child' and not user.get('is_child'))
    )


def require_auth(f):
    """
    Decorator to require authentication for an endpoint.
    Sets request.user_id and request.user if authenticated.

    Authentication is done via Bearer token verified with the Graphlings accounts server.
    The token must be valid and not expired.

    In OPEN_ACCESS_MODE: creates anonymous user from IP if no valid token.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try real auth first (works in any mode)
        token = get_auth_token()
        user = verify_auth_token(token)

        if user:
            _apply_user_to_request(user)
            return f(*args, **kwargs)

        # Open access mode: create anonymous user from IP
        if OPEN_ACCESS_MODE:
            user = _get_anonymous_user()
            _apply_user_to_request(user)
            return f(*args, **kwargs)

        # No valid token - reject request
        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function


def require_auth_or_localhost(f):
    """
    Decorator that requires auth for remote requests but allows localhost.

    Localhost requests (batch generation, admin scripts) use a synthetic
    "system" user with full privileges. This enables server-side batch
    generation without needing auth tokens.

    In OPEN_ACCESS_MODE: creates anonymous user from IP if no valid token.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow localhost to bypass auth for batch generation
        if is_localhost_request():
            request.user = {
                'id': 'system',
                'username': 'system',
                'is_admin': True,
                'subscription_tier': 'creator',
                'account_type': 'adult'
            }
            request.user_id = 'system'
            request.is_adult = True
            return f(*args, **kwargs)

        # Try real auth
        token = get_auth_token()
        user = verify_auth_token(token)

        if user:
            _apply_user_to_request(user)
            return f(*args, **kwargs)

        # Open access mode: create anonymous user from IP
        if OPEN_ACCESS_MODE:
            user = _get_anonymous_user()
            _apply_user_to_request(user)
            return f(*args, **kwargs)

        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function

def optional_auth(f):
    """
    Decorator to optionally authenticate.
    Sets request.user_id and request.user if token provided and valid.
    Does not fail if no token or invalid token.
    Localhost requests get the 'system' user for consistency with batch operations.

    In OPEN_ACCESS_MODE: always creates anonymous user when no valid token.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Localhost gets system user for batch operations
        if is_localhost_request():
            request.user = {
                'id': 'system',
                'username': 'system',
                'is_admin': True,
                'subscription_tier': 'creator',
                'account_type': 'adult'
            }
            request.user_id = 'system'
            request.is_adult = True
            return f(*args, **kwargs)

        token = get_auth_token()
        user = verify_auth_token(token) if token else None

        if user:
            _apply_user_to_request(user)
        elif OPEN_ACCESS_MODE:
            # Open access: give anonymous user identity
            user = _get_anonymous_user()
            _apply_user_to_request(user)
        else:
            request.user = None
            request.user_id = None
            request.is_adult = False

        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# Input Validation & Content Moderation
# =============================================================================

import re
from werkzeug.utils import secure_filename

# Maximum lengths for various inputs
MAX_PROMPT_LENGTH = 500
MAX_PLAYLIST_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500
MAX_NOTES_LENGTH = 1000

# Allowed filename characters (alphanumeric, dash, underscore, dot)
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
# Voice ID pattern: locale_model-name-quality (e.g., en_US-lessac-medium)
SAFE_VOICE_ID_PATTERN = re.compile(r'^[a-zA-Z]{2}_[a-zA-Z]{2}-[a-zA-Z0-9_]+-[a-z]+$')

# Profanity/explicit content word list (basic list - expand as needed)
# This is intentionally a minimal set - add more as needed
BLOCKED_WORDS = {
    # Explicit/sexual terms
    'porn', 'xxx', 'nsfw', 'nude', 'naked', 'sex', 'sexual', 'erotic',
    'hentai', 'orgasm', 'masturbat', 'genital', 'penis', 'vagina',
    # Slurs and hate speech (abbreviated to avoid full words in code)
    'nigger', 'nigga', 'faggot', 'retard', 'kike', 'spic', 'chink',
    # Violence/harmful
    'kill yourself', 'kys', 'suicide', 'rape', 'molest', 'pedophil',
    # Drug references (for child safety)
    'cocaine', 'heroin', 'meth', 'crack',
}

# Patterns that indicate explicit content
EXPLICIT_PATTERNS = [
    re.compile(r'\b(fuck|shit|bitch|ass|dick|cock|pussy|cunt)\b', re.IGNORECASE),
    re.compile(r'\b(porn|xxx|nsfw|nude|naked)\b', re.IGNORECASE),
    re.compile(r'\b(kill\s*(your)?self|kys)\b', re.IGNORECASE),
]


def is_safe_filename(filename):
    """
    Check if a filename is safe (no path traversal, valid characters).
    Returns True if safe, False otherwise.
    """
    if not filename:
        return False

    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        return False

    # Check for valid characters
    if not SAFE_FILENAME_PATTERN.match(filename):
        return False

    # Must have a valid extension
    if not (filename.endswith('.wav') or filename.endswith('.png')):
        return False

    return True


def is_safe_voice_id(voice_id):
    """
    Check if a voice_id is safe (no path traversal, valid format).
    Voice IDs follow the pattern: locale_region-name-quality (e.g., en_US-lessac-medium)
    Returns True if safe, False otherwise.
    """
    if not voice_id:
        return False

    # Check for path traversal attempts
    if '..' in voice_id or '/' in voice_id or '\\' in voice_id:
        return False

    # Check for valid voice ID format
    if not SAFE_VOICE_ID_PATTERN.match(voice_id):
        return False

    return True


def sanitize_filename(filename):
    """
    Sanitize a filename to prevent path traversal.
    Returns sanitized filename or None if invalid.
    """
    if not filename:
        return None

    # Use werkzeug's secure_filename first
    safe = secure_filename(filename)

    # Additional checks
    if not safe or safe != filename:
        return None

    if not is_safe_filename(safe):
        return None

    return safe


def normalize_text_for_filter(text):
    """
    Normalize text to defeat common content filter bypass techniques.
    - Remove zero-width characters
    - Normalize Unicode homoglyphs to ASCII
    - Handle leetspeak substitutions
    - Remove excessive spacing between letters
    """
    if not text:
        return ""

    # Remove zero-width characters and invisible Unicode
    zero_width_chars = '\u200b\u200c\u200d\u2060\ufeff\u00ad'
    for char in zero_width_chars:
        text = text.replace(char, '')

    # Common Unicode homoglyph mappings (Cyrillic/Greek that look like Latin)
    homoglyphs = {
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x', 'у': 'y',
        'А': 'A', 'Е': 'E', 'О': 'O', 'Р': 'P', 'С': 'C', 'Х': 'X',
        'υ': 'u', 'ι': 'i', 'α': 'a', 'ο': 'o', 'ν': 'v',
        '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
        '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
    }
    for homoglyph, replacement in homoglyphs.items():
        text = text.replace(homoglyph, replacement)

    # Leetspeak substitutions
    leetspeak = {
        '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's',
        '7': 't', '@': 'a', '$': 's', '!': 'i', '*': '',
        '+': 't',
    }
    for leet, replacement in leetspeak.items():
        text = text.replace(leet, replacement)

    # Remove single spaces between single letters (catches "f u c k")
    # This pattern: letter + space + letter repeated
    import re
    text = re.sub(r'\b([a-zA-Z])\s+(?=[a-zA-Z]\b)', r'\1', text)

    return text.lower()


def contains_blocked_content(text):
    """
    Check if text contains blocked/explicit content.
    Returns (is_blocked, reason) tuple.
    """
    if not text:
        return False, None

    # Normalize text to defeat bypass attempts
    normalized = normalize_text_for_filter(text)
    text_lower = text.lower()

    # Check both original and normalized versions
    for check_text in [text_lower, normalized]:
        # Check blocked words
        for word in BLOCKED_WORDS:
            if word in check_text:
                return True, "Content contains prohibited term"

        # Check explicit patterns
        for pattern in EXPLICIT_PATTERNS:
            if pattern.search(check_text):
                return True, "Content contains explicit language"

    return False, None


def validate_prompt(prompt, is_adult=False):
    """
    Validate and sanitize a generation prompt.
    Returns (is_valid, cleaned_prompt, error_message) tuple.
    """
    if not prompt:
        return False, None, "Prompt is required"

    if not isinstance(prompt, str):
        return False, None, "Prompt must be a string"

    # Strip and check length
    prompt = prompt.strip()
    if len(prompt) < 3:
        return False, None, "Prompt too short (minimum 3 characters)"

    if len(prompt) > MAX_PROMPT_LENGTH:
        return False, None, f"Prompt too long (maximum {MAX_PROMPT_LENGTH} characters)"

    # Check for blocked content (skip for adult accounts - they can use mild profanity)
    if not is_adult:
        is_blocked, reason = contains_blocked_content(prompt)
        if is_blocked:
            return False, None, reason

    # Remove control characters
    prompt = ''.join(char for char in prompt if ord(char) >= 32 or char in '\n\t')

    return True, prompt, None


def validate_text_input(text, field_name, max_length, required=True, allow_empty=False):
    """
    Validate a generic text input field.
    Returns (is_valid, cleaned_text, error_message) tuple.
    """
    if text is None:
        if required:
            return False, None, f"{field_name} is required"
        return True, None, None

    if not isinstance(text, str):
        return False, None, f"{field_name} must be a string"

    text = text.strip()

    if not text and not allow_empty:
        if required:
            return False, None, f"{field_name} cannot be empty"
        return True, None, None

    if len(text) > max_length:
        return False, None, f"{field_name} too long (maximum {max_length} characters)"

    # Check for blocked content
    is_blocked, reason = contains_blocked_content(text)
    if is_blocked:
        return False, None, f"{field_name}: {reason}"

    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')

    return True, text, None


def validate_integer(value, field_name, min_val=None, max_val=None, default=None):
    """
    Validate an integer input.
    Returns (is_valid, int_value, error_message) tuple.
    """
    if value is None:
        if default is not None:
            return True, default, None
        return False, None, f"{field_name} is required"

    try:
        int_val = int(value)
    except (ValueError, TypeError):
        return False, None, f"{field_name} must be an integer"

    if min_val is not None and int_val < min_val:
        return False, None, f"{field_name} must be at least {min_val}"

    if max_val is not None and int_val > max_val:
        return False, None, f"{field_name} must be at most {max_val}"

    return True, int_val, None


def is_valid_gen_id(gen_id):
    """
    Validate generation ID format.
    Valid gen_ids are 32-character hex strings (UUID4 hex format).
    Returns True if valid, False otherwise.
    """
    if not isinstance(gen_id, str):
        return False
    if len(gen_id) != 32:
        return False
    try:
        int(gen_id, 16)  # Check if valid hex
        return True
    except ValueError:
        return False


def safe_int(value, default=0, min_val=None, max_val=None):
    """
    Safely parse an integer from a string value.
    Returns default if parsing fails. Clamps to min/max if provided.
    """
    try:
        result = int(value) if value is not None else default
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)
        return result
    except (ValueError, TypeError, OverflowError):
        return default


def require_json_content_type():
    """
    Check if the request has a valid JSON content type.

    SECURITY: Explicit Content-Type validation prevents:
    - CSRF attacks that rely on form submissions (which use different content types)
    - Accidental processing of non-JSON data
    - Content-type confusion attacks

    Returns (is_valid, error_response) tuple.
    If is_valid is False, error_response should be returned immediately.
    """
    content_type = request.content_type or ''
    if not content_type.startswith('application/json'):
        return False, (jsonify({
            'error': 'Content-Type must be application/json',
            'received': content_type[:50] if content_type else 'none'
        }), 415)  # 415 Unsupported Media Type
    return True, None


def get_pagination_params():
    """
    Safely extract and validate pagination parameters from request args.
    Returns (page, per_page) with sane defaults and limits.
    """
    # Parse page - must be positive integer, default 1, max 10000
    try:
        page = int(request.args.get('page', 1))
        page = max(1, min(page, 10000))  # Clamp to 1-10000
    except (ValueError, TypeError, OverflowError):
        page = 1

    # Parse per_page - must be positive integer, default 20, max 100
    try:
        per_page = int(request.args.get('per_page', 20))
        per_page = max(1, min(per_page, 100))  # Clamp to 1-100
    except (ValueError, TypeError, OverflowError):
        per_page = 20

    return page, per_page


# =============================================================================

# Model state
models = {}
loading_status = {
    'music': 'pending',
    'audio': 'pending',
    'magnet-music': 'pending',
    'magnet-audio': 'pending',
    'tts': 'ready'  # TTS is external API, always available
}

# Model memory requirements (approximate VRAM in GB)
# These are estimates - actual usage varies with batch size and duration
MODEL_MEMORY_GB = {
    'music': 4.0,       # MusicGen small
    'audio': 5.0,       # AudioGen medium
    'magnet-music': 6.0,
    'magnet-audio': 6.0,
    'tts': 0.5,         # Piper TTS (very small)
}

# Smart scheduler settings
# Starvation timeouts by tier - higher paying users get faster service
# Free users can wait longer since they get notifications when done
_STARVATION_TIMEOUT_BY_TIER = {
    'creator': 120,     # 2 min - top tier gets quick service
    'premium': 300,     # 5 min
    'supporter': 600,   # 10 min
    'free': 1800,       # 30 min - free users wait, but get notified
}
_STARVATION_TIMEOUT_DEFAULT = 900  # 15 min default

_MAX_BATCH_SIZE = 50       # Process more jobs per model before switching (more efficient)
_MIN_FREE_MEMORY_GB = 2.0  # Minimum free GPU memory to keep available
_current_batch_count = 0
_last_model_used = None

# Queue and job tracking
job_queue = queue.PriorityQueue()
jobs = {}  # job_id -> job info
current_job = None
queue_lock = threading.Lock()
model_lock = threading.Lock()  # Lock for model loading/unloading

# Job cleanup settings
_JOB_MAX_AGE_SECONDS = 3600  # Remove completed/failed jobs after 1 hour
_JOB_CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes
_last_job_cleanup = 0

def cleanup_old_jobs():
    """Remove completed/failed jobs older than max age to prevent memory exhaustion."""
    global _last_job_cleanup
    now = time.time()

    # Only run cleanup periodically
    if now - _last_job_cleanup < _JOB_CLEANUP_INTERVAL:
        return 0

    _last_job_cleanup = now
    removed = 0

    with queue_lock:
        to_remove = []
        stuck_jobs = []

        for job_id, job in jobs.items():
            status = job.get('status')

            # Check for stuck 'processing' jobs (no response for > 10 minutes)
            if status == 'processing':
                started_time = job.get('started')
                if started_time:
                    try:
                        started_dt = datetime.fromisoformat(started_time)
                        processing_time = (datetime.now() - started_dt).total_seconds()
                        if processing_time > 600:  # 10 minutes
                            stuck_jobs.append(job_id)
                    except (ValueError, TypeError):
                        pass
                continue

            # Clean up completed, failed, or cancelled jobs
            if status not in ('completed', 'failed', 'cancelled'):
                continue

            # Check age based on completion time or creation time
            completed_time = job.get('completed')
            if completed_time:
                try:
                    completed_dt = datetime.fromisoformat(completed_time)
                    age = (datetime.now() - completed_dt).total_seconds()
                    if age > _JOB_MAX_AGE_SECONDS:
                        to_remove.append(job_id)
                except (ValueError, TypeError):
                    pass
            else:
                # No completion time, check created time
                created_time = job.get('created')
                if created_time:
                    try:
                        created_dt = datetime.fromisoformat(created_time)
                        age = (datetime.now() - created_dt).total_seconds()
                        # Give more time for jobs without completion time
                        if age > _JOB_MAX_AGE_SECONDS * 2:
                            to_remove.append(job_id)
                    except (ValueError, TypeError):
                        pass

        # Mark stuck processing jobs as failed
        for job_id in stuck_jobs:
            job = jobs[job_id]
            job['status'] = 'failed'
            job['error'] = 'Job timed out after 10 minutes'
            job['completed'] = datetime.now().isoformat()
            print(f"[Cleanup] Marked stuck job {job_id[:8]} as failed (processing > 10 min)")

        for job_id in to_remove:
            del jobs[job_id]
            removed += 1

    if removed > 0:
        print(f"[Cleanup] Removed {removed} old jobs from memory")
    if stuck_jobs:
        print(f"[Cleanup] Marked {len(stuck_jobs)} stuck jobs as failed")

    return removed + len(stuck_jobs)


def get_gpu_info():
    """Get GPU utilization info."""
    if not torch.cuda.is_available():
        return {'available': False}

    try:
        gpu_mem_used = torch.cuda.memory_allocated() / 1024**3
        gpu_mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        # Guard against division by zero and clamp to valid range
        gpu_mem_percent = (gpu_mem_used / max(gpu_mem_total, 0.001)) * 100
        gpu_mem_percent = max(0.0, min(100.0, gpu_mem_percent))

        return {
            'available': True,
            'name': torch.cuda.get_device_name(0),
            'memory_used_gb': round(gpu_mem_used, 2),
            'memory_total_gb': round(gpu_mem_total, 2),
            'memory_percent': round(gpu_mem_percent, 1),
            'busy': current_job is not None
        }
    except Exception as e:
        print(f"[GPU] Status check error: {e}")
        return {'available': True, 'error': 'GPU status check failed'}


# GPU memory cache to avoid frequent nvidia-smi calls (5-second timeout is expensive)
_gpu_memory_cache = {'value': 0.0, 'time': 0}
_GPU_MEMORY_CACHE_TTL = 1.0  # Cache for 1 second


def get_free_gpu_memory():
    """Get available GPU memory in GB (checking system-wide, not just our process)."""
    global _gpu_memory_cache

    if not torch.cuda.is_available():
        return 0.0

    # Return cached value if fresh
    now = time.time()
    if now - _gpu_memory_cache['time'] < _GPU_MEMORY_CACHE_TTL:
        return _gpu_memory_cache['value']

    try:
        # Use nvidia-smi to get actual free memory (accounts for other processes like Ollama)
        # Note: GB10 (unified memory) reports memory.free as [N/A] — fall through to torch
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            raw = result.stdout.strip().split('\n')[0]
            if raw and raw.replace('.', '', 1).isdigit():
                free_mb = float(raw)
                free_gb = free_mb / 1024.0
                _gpu_memory_cache = {'value': free_gb, 'time': now}
                return free_gb
    except Exception as e:
        print(f"[GPU] nvidia-smi failed, using torch estimate: {e}")

    # Fallback: use torch's view (only sees our process)
    try:
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        used = torch.cuda.memory_allocated() / 1024**3
        free_gb = total - used
        _gpu_memory_cache = {'value': free_gb, 'time': now}
        return free_gb
    except Exception:
        return 0.0


def get_loaded_models():
    """Get list of currently loaded model types."""
    return [model_type for model_type, model in models.items() if model is not None]


def get_loaded_models_memory():
    """Get total VRAM used by our loaded models (estimate)."""
    total = 0.0
    for model_type in get_loaded_models():
        total += MODEL_MEMORY_GB.get(model_type, 2.0)
    return total


def can_load_model(model_type):
    """Check if we have enough GPU memory to load a model."""
    if model_type in models and models[model_type] is not None:
        return True  # Already loaded

    required = MODEL_MEMORY_GB.get(model_type, 4.0)
    free = get_free_gpu_memory()

    # Need enough free memory plus a buffer
    return free >= (required + _MIN_FREE_MEMORY_GB)


def _unload_model_unlocked(model_type):
    """Internal: Unload a model without acquiring lock. Caller must hold model_lock."""
    global models, loading_status

    if model_type in models and models[model_type] is not None:
        print(f"[GPU] Unloading {model_type} to free memory...")
        del models[model_type]
        models[model_type] = None
        loading_status[model_type] = 'unloaded'

        # Force garbage collection and clear CUDA cache
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print(f"[GPU] {model_type} unloaded. Free memory: {get_free_gpu_memory():.1f}GB")
        return True
    return False


def unload_model(model_type):
    """Unload a model to free GPU memory."""
    with model_lock:
        return _unload_model_unlocked(model_type)


def load_model_on_demand(model_type):
    """Load a model on demand, waiting for GPU memory if needed."""
    global models, loading_status

    # Already loaded?
    if model_type in models and models[model_type] is not None:
        return True

    with model_lock:
        # Double-check after acquiring lock
        if model_type in models and models[model_type] is not None:
            return True

        required_memory = MODEL_MEMORY_GB.get(model_type, 4.0)

        # Wait for GPU memory to become available (Ollama may be using it)
        max_wait = 300  # Wait up to 5 minutes
        wait_start = time.time()
        logged_waiting = False

        while time.time() - wait_start < max_wait:
            free_memory = get_free_gpu_memory()

            if free_memory >= required_memory + _MIN_FREE_MEMORY_GB:
                break

            if not logged_waiting:
                print(f"[GPU] Waiting for memory to load {model_type}... "
                      f"(need {required_memory:.1f}GB, have {free_memory:.1f}GB free)")
                logged_waiting = True

            # Check if we can unload another model to make room
            loaded = get_loaded_models()
            for other_model in loaded:
                if other_model != model_type:
                    # Check if any jobs need this model
                    with queue_lock:
                        needs_model = any(
                            j.get('model') == other_model and j.get('status') == 'queued'
                            for j in jobs.values()
                        )
                    if not needs_model:
                        print(f"[GPU] Unloading idle model {other_model} to make room for {model_type}")
                        _unload_model_unlocked(other_model)  # Use unlocked version - we already hold model_lock
                        break

            time.sleep(5)  # Check every 5 seconds

        # Final check
        free_memory = get_free_gpu_memory()
        if free_memory < required_memory:
            print(f"[GPU] Not enough memory for {model_type} after waiting "
                  f"(need {required_memory:.1f}GB, have {free_memory:.1f}GB)")
            return False

        # Load the model
        print(f"[GPU] Loading {model_type}... (free memory: {free_memory:.1f}GB)")
        loading_status[model_type] = 'loading'

        try:
            if model_type == 'music':
                models['music'] = MusicGen.get_pretrained('facebook/musicgen-small')
            elif model_type == 'audio':
                models['audio'] = AudioGen.get_pretrained('facebook/audiogen-medium')
            elif model_type == 'magnet-music':
                models['magnet-music'] = MAGNeT.get_pretrained('facebook/magnet-small-10secs')
            elif model_type == 'magnet-audio':
                models['magnet-audio'] = MAGNeT.get_pretrained('facebook/audio-magnet-small')
            else:
                print(f"[GPU] Unknown model type: {model_type}")
                return False

            loading_status[model_type] = 'ready'
            print(f"[GPU] {model_type} loaded! (free memory: {get_free_gpu_memory():.1f}GB)")
            return True

        except Exception as e:
            loading_status[model_type] = 'error'  # Hide internal error details from public API
            print(f"[GPU] Failed to load {model_type}: {e}")
            return False


def get_next_job_smart():
    """
    Smart job selection with model affinity and starvation prevention.

    Priority:
    1. Starving jobs (waited too long) - force model switch if needed
    2. Jobs matching currently loaded model (skip ahead)
    3. Highest priority job (may require model switch)

    Returns (priority, timestamp, job_id) or None if no jobs.
    """
    global _current_batch_count, _last_model_used

    with queue_lock:
        # Get all queued jobs
        queued = [(jid, j) for jid, j in jobs.items() if j.get('status') == 'queued']
        if not queued:
            return None

        now = time.time()
        loaded_models = get_loaded_models()

        # Find starving jobs (waited too long based on their tier)
        # Higher paying users have shorter starvation timeouts
        starving = []
        for job_id, job in queued:
            created = job.get('created')
            if created:
                try:
                    created_dt = datetime.fromisoformat(created)
                    wait_time = (datetime.now() - created_dt).total_seconds()

                    # Get tier-based timeout (premium users wait less)
                    job_tier = job.get('tier', 'free')
                    timeout = _STARVATION_TIMEOUT_BY_TIER.get(job_tier, _STARVATION_TIMEOUT_DEFAULT)

                    if wait_time > timeout:
                        starving.append((job_id, job, wait_time, job_tier))
                except (ValueError, TypeError):
                    pass

        # If there are starving jobs, prioritize by tier then wait time
        # (higher tier jobs that are starving get priority)
        if starving:
            # Sort by tier priority (creator=0, premium=1, etc) then by wait time
            tier_priority = {'creator': 0, 'premium': 1, 'supporter': 2, 'free': 3}
            starving.sort(key=lambda x: (tier_priority.get(x[3], 3), -x[2]))
            job_id, job, wait_time, job_tier = starving[0]
            print(f"[Scheduler] Prioritizing starving {job_tier} job {job_id[:8]}... "
                  f"(waited {wait_time:.0f}s, model: {job.get('model')})")
            _current_batch_count = 0
            return (job.get('priority_num', 2), job.get('created', ''), job_id)

        # Check if we should continue batching with current model
        if _last_model_used and _last_model_used in loaded_models and _current_batch_count < _MAX_BATCH_SIZE:
            # Find jobs matching the loaded model
            matching = [(jid, j) for jid, j in queued if j.get('model') == _last_model_used]
            if matching:
                # Sort by priority then timestamp
                matching.sort(key=lambda x: (x[1].get('priority_num', 2), x[1].get('created', '')))
                job_id, job = matching[0]
                _current_batch_count += 1
                return (job.get('priority_num', 2), job.get('created', ''), job_id)

        # No matching jobs or batch limit reached - pick highest priority job
        queued.sort(key=lambda x: (x[1].get('priority_num', 2), x[1].get('created', '')))
        job_id, job = queued[0]
        _current_batch_count = 1
        _last_model_used = job.get('model')
        return (job.get('priority_num', 2), job.get('created', ''), job_id)


def process_queue():
    """
    Worker thread that processes generation jobs with smart scheduling.

    Features:
    - Model affinity: prefers jobs matching currently loaded model
    - Starvation prevention: forces model switch if jobs wait too long
    - GPU memory awareness: waits for memory, unloads idle models
    - On-demand model loading: loads models only when needed
    """
    global current_job, _last_model_used

    while True:
        try:
            # Smart job selection (model affinity + starvation prevention)
            next_job = get_next_job_smart()

            if next_job is None:
                # No jobs in queue - wait a bit and check again
                # Also drain the legacy PriorityQueue if anything was added directly
                try:
                    priority, timestamp, job_id = job_queue.get(timeout=1)
                    # Put it back and let smart scheduler handle it
                    with queue_lock:
                        if job_id in jobs:
                            jobs[job_id]['status'] = 'queued'
                    job_queue.task_done()  # Must call task_done() after get()
                    continue
                except queue.Empty:
                    time.sleep(0.5)
                    continue

            priority, timestamp, job_id = next_job

            with queue_lock:
                if job_id not in jobs:
                    continue
                job = jobs[job_id]
                job['status'] = 'processing'
                job['started'] = datetime.now().isoformat()
                current_job = job_id

            try:
                model_type = job['model']
                _last_model_used = model_type

                # On-demand model loading with GPU memory management
                job['progress'] = f'Loading {model_type} model...'
                if not load_model_on_demand(model_type):
                    # Couldn't load model (not enough memory after waiting)
                    job['status'] = 'queued'
                    job['progress'] = 'Waiting for GPU memory...'
                    print(f"[Scheduler] Re-queuing job {job_id[:8]} - not enough GPU memory")
                    time.sleep(10)  # Wait before retrying
                    continue

                m = models.get(model_type)
                if m is None:
                    job['status'] = 'failed'
                    job['error'] = 'Model failed to load'
                    continue

                # Estimate generation time - MusicGen is slower than AudioGen
                # MusicGen: ~1.5s per second of audio, AudioGen: ~0.5s per second
                time_per_second = 1.5 if model_type == 'music' else 0.5
                estimated_time = max(3, job['duration'] * time_per_second)
                job['estimated_time'] = estimated_time
                job['gen_start'] = time.time()
                gen_label = 'music' if model_type == 'music' else 'sound'
                job['progress'] = f'Generating {gen_label}...'
                job['progress_pct'] = 0

                # Run generation with progress tracking
                # Progress 0-90% = GPU generation (time-based estimate)
                # Progress 91-100% = post-processing (save, quality, spectrogram)
                def update_progress():
                    while job.get('status') == 'processing' and job.get('progress_pct', 0) < 90:
                        elapsed = time.time() - job['gen_start']
                        # Use asymptotic curve: approaches 90% but never overshoots
                        # even if estimate is wrong. ratio=1.0 → 63%, 2.0 → 86%, 3.0 → 90%
                        ratio = elapsed / estimated_time
                        pct = min(90, int(90 * (1 - 2.718 ** (-1.2 * ratio))))
                        job['progress_pct'] = pct
                        job['progress'] = f'Generating {gen_label}... {pct}%'
                        time.sleep(0.3)

                progress_thread = threading.Thread(target=update_progress, daemon=True)
                progress_thread.start()

                m.set_generation_params(duration=job['duration'])
                wav = m.generate([job['prompt']])

                job['progress_pct'] = 92
                job['progress'] = 'Saving file...'

                audio_out = wav[0]
                if job.get('loop'):
                    job['progress'] = 'Applying loop crossfade...'
                    audio_out = make_loopable(audio_out, m.sample_rate)

                # Note: audio_write automatically adds the extension
                filepath_base = os.path.join(OUTPUT_DIR, job_id)
                audio_write(filepath_base, audio_out.cpu(), m.sample_rate, strategy="loudness")
                filename = f"{job_id}.wav"  # This is the actual filename created
                filepath = os.path.join(OUTPUT_DIR, filename)

                job['progress_pct'] = 95
                job['progress'] = 'Analyzing quality...'
                quality = analyze_audio_quality(filepath, m.sample_rate)

                # Generate spectrogram
                job['progress_pct'] = 98
                job['progress'] = 'Generating spectrogram...'
                spec_filename = f"{job_id}.png"
                spec_path = os.path.join(SPECTROGRAMS_DIR, spec_filename)
                generate_spectrogram(filepath, spec_path)

                job['progress_pct'] = 100
                job['progress'] = 'Saving metadata...'

                # Save metadata (JSON for backwards compatibility)
                metadata = load_metadata()
                metadata[filename] = {
                    'prompt': job['prompt'],
                    'model': model_type,
                    'duration': job['duration'],
                    'loop': job.get('loop', False),
                    'rating': None,
                    'created': datetime.now().isoformat(),
                    'priority': job.get('priority', 'standard'),
                    'quality_score': quality['score'],
                    'quality_issues': quality['issues'],
                    'spectrogram': spec_filename,
                    'user_id': job.get('user_id')  # Track user who created this
                }
                save_metadata(metadata)

                # Also save to SQLite database (with retry on failure)
                db_saved = False
                for attempt in range(2):  # Try twice
                    try:
                        db.create_generation(
                            gen_id=job_id,
                            filename=filename,
                            prompt=job['prompt'],
                            model=model_type,
                            duration=job['duration'],
                            is_loop=job.get('loop', False),
                            quality_score=quality['score'],
                            spectrogram=spec_filename,
                            user_id=job.get('user_id'),
                            is_public=job.get('is_public', False)  # Localhost/admin = public
                        )
                        db_saved = True
                        break
                    except Exception as e:
                        print(f"[DB] Failed to save generation (attempt {attempt + 1}): {e}")
                        if attempt == 0:
                            time.sleep(0.5)  # Brief pause before retry

                if not db_saved:
                    # Log critical error - file exists but not in database
                    print(f"[DB] CRITICAL: Generation {job_id} saved to disk but NOT in database!")
                    job['db_save_failed'] = True  # Flag for debugging

                job['status'] = 'completed'
                job['completed'] = datetime.now().isoformat()  # For cleanup tracking
                job['filename'] = filename
                job['spectrogram'] = spec_filename
                job['quality'] = quality
                job['progress'] = 'Done!'

                # Send notification to user if they have notify_on_complete flag
                if job.get('notify_on_complete') and job.get('user_id'):
                    prompt_preview = job['prompt'][:50] + '...' if len(job['prompt']) > 50 else job['prompt']
                    send_user_notification(
                        user_id=job['user_id'],
                        title='Audio Ready!',
                        message=f'Your {job["model"]} generation is complete: "{prompt_preview}"',
                        notification_type='success',
                        data={
                            'job_id': job_id,
                            'filename': filename,
                            'audio_url': f'/audio/{filename}',
                            'model': job['model']
                        }
                    )

                # Auto-regenerate if quality is bad (max 2 retries)
                if not quality['is_good'] and job.get('retry_count', 0) < 2:
                    job['progress'] = f"Low quality detected (score: {quality['score']}), regenerating..."
                    job['retry_count'] = job.get('retry_count', 0) + 1
                    # Re-queue the job - just set status, get_next_job_smart() will pick it up
                    job['status'] = 'queued'

            except Exception as e:
                job['status'] = 'failed'
                # Log full error for debugging, but show generic message to user
                print(f"[Generation] Job {job_id} failed: {e}")
                # Sanitize error - only show safe generic messages
                error_str = str(e).lower()
                if 'cuda' in error_str or 'gpu' in error_str or 'memory' in error_str:
                    job['error'] = 'GPU memory error - try a shorter duration'
                elif 'model' in error_str or 'load' in error_str:
                    job['error'] = 'Model temporarily unavailable'
                else:
                    job['error'] = 'Generation failed - please try again'

                # Notify user of failure
                if job.get('notify_on_complete') and job.get('user_id'):
                    send_user_notification(
                        user_id=job['user_id'],
                        title='Generation Failed',
                        message=job['error'],
                        notification_type='error',
                        data={'job_id': job_id}
                    )

            finally:
                with queue_lock:
                    current_job = None
                # Note: task_done() is NOT called here because get_next_job_smart()
                # selects from jobs dict, not from job_queue. The legacy queue drain
                # path at the top of the loop properly calls task_done() after get().

                # Periodically cleanup old jobs to prevent memory exhaustion
                cleanup_old_jobs()

        except Exception as e:
            print(f"Queue worker error: {e}")
            time.sleep(1)


def load_models():
    """
    Smart model preloading based on available GPU memory.

    Behavior:
    - Check available GPU memory first
    - If enough memory, preload most commonly used model (audio/SFX)
    - Other models marked as 'available' and load on-demand
    - If GPU memory is low (e.g., Ollama is running), skip preloading
    """
    global models, loading_status

    print("[GPU] Checking available memory for model preloading...", flush=True)
    free_memory = get_free_gpu_memory()
    print(f"[GPU] Free memory: {free_memory:.1f}GB", flush=True)

    # Mark all models as available (will load on-demand)
    for model_type in ['music', 'audio', 'magnet-music', 'magnet-audio']:
        loading_status[model_type] = 'available'

    # Preload AudioGen if we have enough memory (most commonly used for SFX)
    audio_memory = MODEL_MEMORY_GB.get('audio', 5.0)
    if free_memory >= audio_memory + _MIN_FREE_MEMORY_GB:
        print(f"[GPU] Preloading AudioGen (have {free_memory:.1f}GB, need {audio_memory:.1f}GB)...", flush=True)
        loading_status['audio'] = 'loading'
        try:
            models['audio'] = AudioGen.get_pretrained('facebook/audiogen-medium')
            loading_status['audio'] = 'ready'
            print("[GPU] AudioGen preloaded!", flush=True)

            # Check if we can also preload MusicGen
            free_memory = get_free_gpu_memory()
            music_memory = MODEL_MEMORY_GB.get('music', 4.0)
            if free_memory >= music_memory + _MIN_FREE_MEMORY_GB:
                print(f"[GPU] Also preloading MusicGen (have {free_memory:.1f}GB)...", flush=True)
                loading_status['music'] = 'loading'
                try:
                    models['music'] = MusicGen.get_pretrained('facebook/musicgen-small')
                    loading_status['music'] = 'ready'
                    print("[GPU] MusicGen preloaded!", flush=True)
                except Exception as e:
                    loading_status['music'] = 'available'
                    print(f"[GPU] MusicGen preload failed (will load on-demand): {e}", flush=True)
        except Exception as e:
            loading_status['audio'] = 'available'
            print(f"[GPU] AudioGen preload failed (will load on-demand): {e}", flush=True)
    else:
        print(f"[GPU] Not enough memory for preloading (need {audio_memory:.1f}GB, have {free_memory:.1f}GB)", flush=True)
        print("[GPU] Models will load on-demand when needed", flush=True)

    print("[GPU] Model initialization complete. Models load on-demand based on GPU memory.", flush=True)


def get_model(model_type):
    return models.get(model_type)


@app.route('/')
def index():
    return render_template('index.html', open_access_mode=OPEN_ACCESS_MODE)


@app.route('/track/<track_id>')
def track_page(track_id):
    """Shareable track page - loads app with specific track."""
    if not is_valid_gen_id(track_id):
        return render_template('index.html', open_access_mode=OPEN_ACCESS_MODE)
    # Pass track_id to template for auto-loading
    return render_template('index.html', shared_track_id=track_id, open_access_mode=OPEN_ACCESS_MODE)


@app.route('/status')
@limiter.limit("60 per minute")  # SECURITY: Rate limit to prevent DoS via repeated status checks
def status():
    """Return model loading status, GPU info, and queue status."""
    # Calculate queue length and estimated wait
    with queue_lock:
        queued_jobs = [j for j in jobs.values() if j['status'] in ['queued', 'processing']]
        queue_length = len(queued_jobs)
        # Estimate wait time: ~0.5s per second of audio duration
        total_duration = sum(j.get('duration', 8) for j in queued_jobs)
        estimated_wait = total_duration * 0.5

        # Group jobs by model type
        jobs_by_model = {}
        for j in queued_jobs:
            model = j.get('model', 'unknown')
            jobs_by_model[model] = jobs_by_model.get(model, 0) + 1

    # Enhanced GPU info with system-wide memory check
    gpu_info = get_gpu_info()
    gpu_info['free_memory_gb'] = round(get_free_gpu_memory(), 2)
    gpu_info['loaded_models'] = get_loaded_models()
    gpu_info['loaded_models_memory_gb'] = round(get_loaded_models_memory(), 2)

    # SECURITY: Don't expose internal scheduler state to public
    # Internal values like batch_count and starvation timeouts are implementation details
    return jsonify({
        'models': loading_status,
        'gpu': gpu_info,
        'queue_length': queue_length,
        'queue_by_model': jobs_by_model,
        'estimated_wait': estimated_wait
    })


@app.route('/queue-status')
@limiter.limit("60 per minute")  # SECURITY: Rate limit to prevent DoS
def queue_status():
    """Return current queue status (public, no sensitive data)."""
    with queue_lock:
        queue_list = []
        for job_id, job in jobs.items():
            if job['status'] in ['queued', 'processing']:
                queue_list.append({
                    'id': job_id,
                    'status': job['status'],
                    'model': job.get('model', 'music'),
                    'priority': job.get('priority', 'standard'),
                    'position': job.get('position', 0)
                })

        return jsonify({
            'queue_length': len(queue_list),
            'current_job': current_job,
            'jobs': queue_list
        })


@app.route('/api/queue')
def api_queue():
    """Get detailed queue status with all jobs for the Queue Explorer (no sensitive data)."""
    with queue_lock:
        queue_list = []
        for job_id, job in jobs.items():
            if job['status'] in ['queued', 'processing']:
                queue_list.append({
                    'id': job_id,
                    'status': job['status'],
                    'model': job.get('model', 'music'),
                    'duration': job.get('duration', 8),
                    'priority': job.get('priority', 'standard'),
                    'created': job.get('created'),
                    'progress': job.get('progress', ''),
                    'progress_pct': job.get('progress_pct', 0)
                })

        # Sort by priority (lower = higher priority) then by creation time
        queue_list.sort(key=lambda x: (
            PRIORITY_LEVELS.get(x['priority'], 2),
            x.get('created', '')
        ))

        # Add position numbers
        for i, item in enumerate(queue_list):
            item['position'] = i + 1

        return jsonify({
            'jobs': queue_list,
            'current_job': current_job,
            'total': len(queue_list)
        })


@app.route('/api/queue/<job_id>/cancel', methods=['POST'])
@limiter.limit("60 per hour")  # Rate limit job cancellation
@require_auth
def api_cancel_job(job_id):
    """Cancel a queued job. Only the job owner can cancel."""
    # Use verified user_id from auth token, not client request
    user_id = request.user_id

    with queue_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404

        job = jobs[job_id]

        # Only allow canceling own jobs
        if job.get('user_id') != user_id:
            return jsonify({'error': 'Not authorized to cancel this job'}), 403

        # Can't cancel a job that's already processing
        if job['status'] == 'processing':
            return jsonify({'error': 'Cannot cancel a job that is already processing'}), 400

        # Can't cancel completed/failed jobs
        if job['status'] not in ['queued']:
            return jsonify({'error': 'Job is not in queue'}), 400

        # Mark as cancelled and remove from active jobs
        job['status'] = 'cancelled'
        del jobs[job_id]

    return jsonify({'success': True, 'message': 'Job cancelled'})


@app.route('/api/queue/skip-pricing')
def api_skip_pricing():
    """
    Get skip-the-queue pricing info for UI display.

    Returns pricing tiers so the UI can show users what it costs to skip.
    """
    return jsonify({
        'pricing': get_skip_pricing_info(),
        'currency': 'aura',
        'description': 'Pay with Aura to skip the queue and get your audio faster'
    })


@app.route('/api/queue/<job_id>/skip', methods=['POST'])
@limiter.limit("30 per hour")  # Limit skip attempts
@require_auth
def api_skip_queue(job_id):
    """
    Skip the queue by paying Aura.

    Moves the job to the front of the queue (highest priority).
    User must own the job and have enough Aura.

    The cost is based on job duration:
    - Short SFX (1-10s): 1 Aura
    - Medium (11-30s): 3 Aura
    - Long SFX (31-60s): 5 Aura
    - Song (61-120s): 10 Aura
    - Long song (121s+): 15 Aura

    SECURITY: Uses skip_pending flag to prevent TOCTOU race conditions where
    concurrent requests could cause double-charging or race past validation.
    """
    user_id = request.user_id
    token = get_auth_token()

    with queue_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404

        job = jobs[job_id]

        # Only allow skipping own jobs
        if job.get('user_id') != user_id:
            return jsonify({'error': 'Not authorized to skip this job'}), 403

        # Can only skip queued jobs
        if job['status'] != 'queued':
            return jsonify({'error': 'Job is not in queue (may already be processing)'}), 400

        # Already skipped or skip in progress?
        # SECURITY: Check skip_pending to prevent TOCTOU race condition
        if job.get('skipped') or job.get('skip_pending'):
            return jsonify({'error': 'Job has already been skipped'}), 400

        # Calculate cost
        duration = job.get('duration', 30)
        skip_cost = get_skip_cost(duration)

        # SECURITY: Set pending flag BEFORE releasing lock to prevent concurrent skip attempts
        job['skip_pending'] = True

    # Charge Aura (outside lock to avoid holding it during network call)
    payment = spend_aura(
        token=token,
        amount=skip_cost,
        item_description=f"Skip queue for {duration}s audio generation",
        job_id=job_id
    )

    if not payment['success']:
        # Payment failed - clear the pending flag
        with queue_lock:
            if job_id in jobs:
                jobs[job_id].pop('skip_pending', None)
        return jsonify({
            'error': payment.get('error', 'Payment failed'),
            'cost': skip_cost
        }), 402  # Payment Required

    # Payment succeeded - move job to front of queue
    with queue_lock:
        if job_id not in jobs:
            # Job disappeared while we were charging - this shouldn't happen
            # Log for manual review/refund
            print(f"[CRITICAL] Job {job_id} disappeared after Aura payment of {skip_cost}. Manual refund may be needed.")
            return jsonify({'error': 'Job no longer exists'}), 404

        job = jobs[job_id]

        # SECURITY: Verify job is still in valid state (wasn't processed during payment)
        if job['status'] != 'queued':
            # Job started processing during payment - log for refund review
            print(f"[WARN] Job {job_id} started processing during skip payment of {skip_cost}. May need refund.")
            job.pop('skip_pending', None)
            return jsonify({'error': 'Job started processing during payment'}), 409  # Conflict

        job.pop('skip_pending', None)
        job['skipped'] = True
        job['skip_cost'] = skip_cost
        job['priority'] = 'skipped'
        job['priority_num'] = -1  # Highest priority (lower = higher)
        job['progress'] = 'Skipped to front of queue!'

    return jsonify({
        'success': True,
        'message': f'Skipped to front of queue for {skip_cost} Aura',
        'cost': skip_cost,
        'new_balance': payment.get('new_balance')
    })


@app.route('/job/<job_id>')
@optional_auth
def job_status(job_id):
    """
    Get status of a specific job.

    Only the job owner can see full details. Unauthenticated requests
    or requests from non-owners get a 404 to prevent job enumeration.
    """
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]

    # Only the job owner can view job status (prevents enumeration)
    job_owner = job.get('user_id')
    if job_owner and request.user_id != job_owner:
        # Don't reveal that the job exists to non-owners
        return jsonify({'error': 'Job not found'}), 404

    # Calculate skip info for queued jobs
    skip_info = None
    if job['status'] == 'queued' and not job.get('skipped'):
        duration = job.get('duration', 30)
        skip_info = {
            'available': True,
            'cost': get_skip_cost(duration),
            'currency': 'aura'
        }
    elif job.get('skipped'):
        skip_info = {
            'available': False,
            'already_skipped': True,
            'cost_paid': job.get('skip_cost', 0)
        }

    return jsonify({
        'id': job_id,
        'status': job['status'],
        'progress': job.get('progress', ''),
        'progress_pct': job.get('progress_pct', 0),
        'filename': job.get('filename'),
        'spectrogram': job.get('spectrogram'),
        'quality': job.get('quality'),
        'error': job.get('error'),
        'position': job.get('position', 0),
        'retry_count': job.get('retry_count', 0),
        'skip': skip_info
    })


def is_email_verified(user):
    """
    Check if user has verified their email.

    Valnet account tiers that indicate verification:
    - 'verified', 'email_verified', 'oauth_verified' = verified
    - 'access_code', 'anonymous' = not verified
    """
    if not user:
        return False

    # Check explicit email_verified flag
    if user.get('email_verified'):
        return True

    # Check account tier (Valnet uses tier for verification status)
    account_tier = user.get('account_tier') or user.get('tier')
    if account_tier:
        tier_lower = account_tier.lower()
        if tier_lower in ('verified', 'email_verified', 'oauth_verified', 'organization'):
            return True

    # Check if they have an email set (OAuth users have verified emails)
    if user.get('email') and user.get('auth_provider') in ('google', 'oauth'):
        return True

    return False


@app.route('/generate', methods=['POST'])
@limiter.limit("60 per hour")  # Global rate limit (per-user limits are stricter)
@require_auth_or_localhost  # Auth required, but localhost can bypass for batch generation
def generate():
    """
    Submit an audio generation job. Requires authentication.

    Requirements:
    - All users must be authenticated
    - Free users must have verified email
    - Paying subscribers (supporter/premium/creator) can generate without email verification

    Rate limits and queue limits are enforced based on user tier:
    - Creator ($20/mo): 60/hour, max 20 pending jobs, up to 180s duration
    - Premium ($10/mo): 30/hour, max 10 pending jobs, up to 120s duration
    - Supporter ($5/mo): 15/hour, max 5 pending jobs, up to 60s duration
    - Free (verified): 3/hour, max 2 pending jobs, up to 30s duration
    """
    # SECURITY: Validate Content-Type to prevent CSRF and content-type confusion
    is_valid, error_response = require_json_content_type()
    if not is_valid:
        return error_response

    data = request.json or {}
    user_id = request.user_id
    user = request.user

    # Determine user tier and limits
    tier = get_user_tier(user)
    limits = GENERATION_LIMITS.get(tier, GENERATION_LIMITS['free'])

    # Free users must have verified email to generate
    # Paying subscribers (supporter, premium, creator) can generate without verification
    # In OPEN_ACCESS_MODE, skip email verification entirely
    if not OPEN_ACCESS_MODE and tier == 'free' and not is_email_verified(user):
        return jsonify({
            'success': False,
            'error': 'Please verify your email address to generate audio. Check your inbox for the verification link, or upgrade to a subscription plan.',
            'requires_verification': True
        }), 403

    # Check per-user pending job limit
    pending_count = count_user_pending_jobs(user_id)
    max_pending = MAX_PENDING_PER_USER.get(tier, 2)
    if pending_count >= max_pending:
        return jsonify({
            'success': False,
            'error': f'You have {pending_count} pending jobs. Please wait for them to complete.',
            'pending_count': pending_count,
            'max_pending': max_pending
        }), 429

    # Check global queue size
    with queue_lock:
        total_queued = sum(1 for j in jobs.values() if j['status'] in ['queued', 'processing'])
    if total_queued >= MAX_QUEUE_SIZE:
        return jsonify({
            'success': False,
            'error': 'The generation queue is full. Please try again in a few minutes.',
            'queue_size': total_queued
        }), 503

    # Check user's hourly generation count (simple in-memory check)
    # Note: flask-limiter handles the actual rate limiting, this is for informative error
    user_hourly_key = f'gen_count:{user_id}'
    # (Rate limiting is enforced by flask-limiter decorator below)

    # Validate prompt with content moderation
    raw_prompt = data.get('prompt', 'upbeat electronic music')
    is_adult = getattr(request, 'is_adult', False)
    is_valid, prompt, error = validate_prompt(raw_prompt, is_adult=is_adult)
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 400

    # Validate duration - enforce tier-based max duration
    max_duration = limits['max_duration']
    is_valid, duration, error = validate_integer(
        data.get('duration', 8), 'duration', min_val=1, max_val=max_duration, default=8
    )
    if not is_valid:
        if 'at most' in str(error):
            error = f'Duration limited to {max_duration}s for your account tier'
        return jsonify({'success': False, 'error': error}), 400

    # Validate model type
    model_type = data.get('model', 'music')
    if model_type not in ['music', 'audio', 'magnet-music', 'magnet-audio']:
        return jsonify({'success': False, 'error': 'Invalid model type'}), 400

    make_loop = bool(data.get('loop', False))
    # Set priority based on tier
    priority = 'premium' if tier == 'premium' else 'free'

    model_status = loading_status.get(model_type, 'unknown')
    if model_status not in ('ready', 'available'):
        return jsonify({
            'success': False,
            'error': f'Model still loading: {model_status}'
        }), 503

    # Create job
    job_id = uuid.uuid4().hex
    priority_num = PRIORITY_LEVELS.get(priority, 2)

    # Determine if this generation should be public immediately
    # Localhost requests (batch generation, admin scripts) are trusted
    # Admin users can also create public content directly
    is_admin = user.get('is_admin', False) if user else False
    is_public = is_localhost_request() or is_admin

    job = {
        'id': job_id,
        'prompt': prompt,
        'duration': duration,
        'model': model_type,
        'loop': make_loop,
        'priority': priority,
        'priority_num': priority_num,  # Store numeric priority for smart scheduler
        'tier': tier,
        'status': 'queued',
        'created': datetime.now().isoformat(),
        'progress': 'Waiting in queue...',
        'user_id': user_id,
        'is_public': is_public,  # Localhost/admin = public, user = needs review
        'notify_on_complete': True  # Flag to send notification when done
    }

    with queue_lock:
        # SECURITY: Final atomic check for pending job limit (prevents race condition)
        pending_count = sum(1 for j in jobs.values()
                           if j.get('user_id') == user_id and j['status'] in ['queued', 'processing'])
        if pending_count >= max_pending:
            return jsonify({
                'success': False,
                'error': f'You have {pending_count} pending jobs. Please wait for them to complete.',
                'pending_count': pending_count,
                'max_pending': max_pending
            }), 429

        # SECURITY: Final atomic check for global queue size
        total_queued = sum(1 for j in jobs.values() if j['status'] in ['queued', 'processing'])
        if total_queued >= MAX_QUEUE_SIZE:
            return jsonify({
                'success': False,
                'error': 'The generation queue is full. Please try again in a few minutes.',
                'queue_size': total_queued
            }), 503

        jobs[job_id] = job
        # NOTE: We don't add to job_queue here - get_next_job_smart() reads from jobs dict
        # The legacy job_queue is only used for backwards compatibility and is drained automatically

        # Calculate position (premium jobs count as ahead of free jobs)
        position = sum(1 for j in jobs.values() if j['status'] in ['queued', 'processing'])
        job['position'] = position

    # Inform user about queue position
    queue_message = None
    if position > 1:
        queue_message = f"You're #{position} in line. We'll notify you when your audio is ready!"

    return jsonify({
        'success': True,
        'job_id': job_id,
        'position': position,
        'queue_message': queue_message,
        'tier': tier,
        'limits': {
            'max_duration': limits['max_duration'],
            'per_hour': limits['per_hour']
        }
    })


@app.route('/audio/<filename>')
def serve_audio(filename):
    # Security: Validate filename to prevent path traversal
    if not is_safe_filename(filename) or not filename.endswith('.wav'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(OUTPUT_DIR, filename)

    # Additional security: Ensure resolved path is within OUTPUT_DIR
    real_path = os.path.realpath(filepath)
    real_output_dir = os.path.realpath(OUTPUT_DIR)
    if not real_path.startswith(real_output_dir + os.sep):
        return jsonify({'error': 'Invalid path'}), 400

    if os.path.exists(filepath):
        response = send_file(filepath, mimetype='audio/wav')
        # Add CORS headers for embedded widget support
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    return jsonify({'error': 'Not found'}), 404


@app.route('/spectrogram/<filename>')
def serve_spectrogram(filename):
    # Security: Validate filename to prevent path traversal
    if not is_safe_filename(filename) or not filename.endswith('.png'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(SPECTROGRAMS_DIR, filename)

    # Additional security: Ensure resolved path is within SPECTROGRAMS_DIR
    real_path = os.path.realpath(filepath)
    real_spec_dir = os.path.realpath(SPECTROGRAMS_DIR)
    if not real_path.startswith(real_spec_dir + os.sep):
        return jsonify({'error': 'Invalid path'}), 400

    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return jsonify({'error': 'Not found'}), 404


@app.route('/generate-spectrogram/<audio_filename>')
def generate_spectrogram_for_file(audio_filename):
    """Generate spectrogram for an existing audio file on demand."""
    # Security: Validate filename to prevent path traversal
    if not is_safe_filename(audio_filename) or not audio_filename.endswith('.wav'):
        return jsonify({'error': 'Invalid filename'}), 400

    audio_path = os.path.join(OUTPUT_DIR, audio_filename)

    # Additional security: Ensure resolved path is within OUTPUT_DIR
    real_path = os.path.realpath(audio_path)
    real_output_dir = os.path.realpath(OUTPUT_DIR)
    if not real_path.startswith(real_output_dir + os.sep):
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404

    spec_filename = audio_filename.replace('.wav', '.png')
    spec_path = os.path.join(SPECTROGRAMS_DIR, spec_filename)

    # Generate if doesn't exist
    if not os.path.exists(spec_path):
        success = generate_spectrogram(audio_path, spec_path)
        if not success:
            return jsonify({'error': 'Failed to generate spectrogram'}), 500

    return jsonify({'spectrogram': spec_filename})


@app.route('/history')
@limiter.limit("60 per minute")  # SECURITY: Rate limit directory scan operations
@optional_auth
def history():
    """
    Get recent generations from the output directory.

    PERFORMANCE NOTE: This endpoint scans the filesystem and should be used sparingly.
    For paginated access to generations, prefer /api/library which uses the database.
    """
    # Optional filters
    model_filter = request.args.get('model')  # 'music' or 'audio'
    requested_user_id = request.args.get('user_id')  # User ID from widget
    # SECURITY: Limit results to prevent DoS via large directory scans
    limit = safe_int(request.args.get('limit'), default=100, min_val=1, max_val=500)

    # Security: Only allow filtering by own user_id or admin access
    # If user_id filter is requested, verify it's the authenticated user's ID
    effective_user_id = None
    if requested_user_id:
        if hasattr(request, 'user_id') and request.user_id == requested_user_id:
            effective_user_id = requested_user_id
        elif hasattr(request, 'user') and request.user.get('is_admin'):
            effective_user_id = requested_user_id  # Admin can view any user
        # If not authenticated or not matching, ignore user_id filter (show public only)

    # PERFORMANCE: Only get modification times for files we need to sort
    # Limit the scan to avoid DoS with large directories
    try:
        all_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.wav')]
    except OSError:
        return jsonify([])

    # Sort by modification time (most recent first)
    files = sorted(
        all_files,
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
        reverse=True
    )[:limit * 2]  # Get more than limit to account for filtering

    metadata = load_metadata()
    result = []
    for f in files:
        if len(result) >= limit:
            break

        info = metadata.get(f, {})

        # Filter by model type if specified
        if model_filter and info.get('model') != model_filter:
            continue

        # Filter by user_id if specified (secured above)
        if effective_user_id and info.get('user_id') != effective_user_id:
            continue

        spec_filename = info.get('spectrogram', f.replace('.wav', '.png'))
        result.append({
            'filename': f,
            'prompt': info.get('prompt', 'Unknown'),
            'model': info.get('model', 'unknown'),
            'duration': info.get('duration', 0),
            'loop': info.get('loop', False),
            'rating': info.get('rating'),
            'created': info.get('created', ''),
            'quality_score': info.get('quality_score'),
            'quality_issues': info.get('quality_issues', []),
            'spectrogram': spec_filename,
            'user_id': info.get('user_id')
        })

    return jsonify(result)


@app.route('/rate', methods=['POST'])
@limiter.limit("100 per hour")  # Rate limit rating actions
@require_auth  # SECURITY: Require authentication to prevent anonymous rating manipulation
def rate():
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON body'}), 400

    filename = data.get('filename')
    rating = data.get('rating')

    if not filename:
        return jsonify({'success': False, 'error': 'No filename'}), 400

    # Validate rating: must be None (to clear) or integer 1-5
    if rating is not None:
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': 'Rating must be 1-5 or null'}), 400

    # Security: Validate filename to prevent path traversal
    if not is_safe_filename(filename):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    # Verify file actually exists
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]['rating'] = rating
        save_metadata(metadata)
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'File not found in metadata'}), 404


# =============================================================================
# NEW API: Library with Pagination & Search
# =============================================================================

@app.route('/api/library')
@limiter.limit("300 per minute")  # High limit for browsing
def api_library():
    """
    Get paginated library with filters.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        model: Filter by 'music', 'audio', or 'voice'
        search: Full-text search in prompts
        sort: 'recent', 'popular', or 'rating'
        user_id: Filter by creator
        category: Filter by genre/category (e.g., 'ambient', 'nature')
        source: Filter by Graphlings source (e.g., 'byk3s')
    """
    page, per_page = get_pagination_params()

    # Validate model parameter (whitelist)
    model = request.args.get('model')
    if model and model not in ('music', 'audio', 'voice'):
        model = None  # Invalid model, ignore

    search = request.args.get('search')

    # Check if search looks like a generation ID (32 hex chars or with dashes)
    if search and is_valid_gen_id(search.strip()):
        generation = db.get_generation(search.strip())
        if generation:
            # Return single item as a library result
            return jsonify({
                'items': [generation],
                'total': 1,
                'page': 1,
                'per_page': 1,
                'pages': 1,
                'id_search': True  # Flag to indicate this was an ID lookup
            })
        # ID not found, return empty results
        return jsonify({
            'items': [],
            'total': 0,
            'page': 1,
            'per_page': per_page,
            'pages': 0,
            'id_search': True
        })

    # Validate sort parameter (whitelist)
    sort = request.args.get('sort', 'recent')
    if sort not in ('recent', 'popular', 'rating'):
        sort = 'recent'

    user_id = request.args.get('user_id')

    # Validate category parameter - must be alphanumeric with underscores
    category = request.args.get('category')
    if category:
        # Sanitize: only allow alphanumeric, underscores, and hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', category):
            category = None  # Invalid category, ignore

    # Validate source parameter
    source = request.args.get('source')
    if source and source not in db.GRAPHLINGS_SOURCES:
        source = None  # Invalid source, ignore

    result = db.get_library(
        page=page,
        per_page=per_page,
        model=model,
        search=search,
        sort=sort,
        user_id=user_id,
        category=category,
        source=source
    )

    return jsonify(result)


@app.route('/api/library/<gen_id>')
def api_library_item(gen_id):
    """Get a single generation by ID."""
    if not is_valid_gen_id(gen_id):
        return jsonify({'error': 'Invalid generation ID format'}), 400
    generation = db.get_generation(gen_id)
    if not generation:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(generation)


@app.route('/api/library/counts')
@limiter.limit("120 per minute")  # SECURITY: Rate limit to prevent DoS
def api_library_counts():
    """Get counts for each content type."""
    counts = db.get_library_counts()
    return jsonify(counts)


# =============================================================================
# My Generations API - Private User Content
# =============================================================================

@app.route('/api/my-generations')
@limiter.limit("120 per minute")
@require_auth
def api_my_generations():
    """
    Get authenticated user's own generations.

    All generations are CC0 (public domain). New generations start private
    and are reviewed by admins before being added to the public library.
    Favorites are protected from auto-cleanup.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 50, max 100)
        model: Filter by 'music', 'audio', or 'voice'

    Returns:
        items: List of generations with is_favorite flag
        by_model: Count breakdown by model type
        storage: Storage usage info
        total, page, per_page, pages: Pagination info
    """
    page, per_page = get_pagination_params()
    model = request.args.get('model')
    user_id = request.user_id
    tier = get_user_tier(request.user)

    # Get user's generations
    result = db.get_user_generations(
        user_id=user_id,
        model=model,
        page=page,
        per_page=per_page
    )

    # Add storage info
    result['storage'] = db.get_user_storage_info(user_id, tier)

    # Add a reminder about CC0 licensing
    result['license_notice'] = (
        'All generations are CC0 (public domain). Good content may be '
        'added to the public library after admin review.'
    )

    return jsonify(result)


@app.route('/api/my-generations/storage')
@limiter.limit("60 per minute")
@require_auth
def api_my_storage():
    """
    Get storage usage info for authenticated user.

    Returns:
        used: Number of private generations
        limit: Max allowed for tier
        favorites: Number protected from deletion
        percent_used: Usage percentage
        near_limit: True if over 80%
        at_limit: True if at or over limit
    """
    user_id = request.user_id
    tier = get_user_tier(request.user)

    storage = db.get_user_storage_info(user_id, tier)

    # Add tier info
    storage['tier'] = tier
    storage['upgrade_url'] = '/pricing' if tier == 'free' else None

    return jsonify(storage)


@app.route('/api/my-generations/cleanup', methods=['POST'])
@limiter.limit("10 per hour")
@require_auth
def api_cleanup_generations():
    """
    Manually trigger cleanup of old generations.

    Removes oldest non-favorited generations to free up space.
    Favorites are never deleted.

    Body:
        keep_count: Optional override for number to keep
    """
    user_id = request.user_id
    tier = get_user_tier(request.user)
    data = request.json or {}

    # Validate keep_count if provided
    keep_count = data.get('keep_count')
    if keep_count is not None:
        try:
            keep_count = int(keep_count)
            max_limit = db.USER_STORAGE_LIMITS.get(tier, 20)
            keep_count = min(keep_count, max_limit)
        except (ValueError, TypeError):
            return jsonify({'error': 'keep_count must be an integer'}), 400

    deleted = db.cleanup_old_generations(user_id, tier, keep_count)

    return jsonify({
        'success': True,
        'deleted': deleted,
        'storage': db.get_user_storage_info(user_id, tier)
    })


# =============================================================================
# Admin Moderation API
# =============================================================================

@app.route('/api/admin/moderation')
@limiter.limit("60 per minute")
@require_auth
def api_pending_moderation():
    """
    Get generations pending admin review.

    Query params:
        page: Page number
        per_page: Items per page
        model: Filter by model type
    """
    # Check admin status
    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    page, per_page = get_pagination_params()
    model = request.args.get('model')

    result = db.get_pending_moderation(page=page, per_page=per_page, model=model)
    return jsonify(result)


@app.route('/api/admin/moderate/<gen_id>', methods=['POST'])
@limiter.limit("120 per hour")
@require_auth
def api_moderate(gen_id):
    """
    Moderate a generation (approve/reject for public library).

    Body:
        action: 'approve', 'reject', or 'delete'
        reason: Optional reason for rejection
    """
    # SECURITY: Validate Content-Type for admin endpoint
    is_valid, error_response = require_json_content_type()
    if not is_valid:
        return error_response

    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    data = request.json or {}
    action = data.get('action')

    if action not in ('approve', 'reject', 'delete'):
        return jsonify({'error': 'action must be approve, reject, or delete'}), 400

    result = db.moderate_generation(
        gen_id=gen_id,
        admin_user_id=request.user_id,
        action=action,
        reason=data.get('reason')
    )

    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/admin/moderate/bulk', methods=['POST'])
@limiter.limit("30 per hour")
@require_auth
def api_bulk_moderate():
    """
    Moderate multiple generations at once.

    Body:
        gen_ids: List of generation IDs (max 50)
        action: 'approve', 'reject', or 'delete'
    """
    # SECURITY: Validate Content-Type for admin endpoint
    is_valid, error_response = require_json_content_type()
    if not is_valid:
        return error_response

    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    data = request.json or {}
    gen_ids = data.get('gen_ids', [])
    action = data.get('action')

    if not isinstance(gen_ids, list) or len(gen_ids) > 50:
        return jsonify({'error': 'gen_ids must be a list with max 50 items'}), 400

    if not all(isinstance(gid, str) for gid in gen_ids):
        return jsonify({'error': 'Each gen_id must be a string'}), 400

    if action not in ('approve', 'reject', 'delete'):
        return jsonify({'error': 'action must be approve, reject, or delete'}), 400

    result = db.bulk_moderate(gen_ids, request.user_id, action)
    return jsonify(result)


# =============================================================================
# Backup API
# =============================================================================

@app.route('/api/backup/status')
@require_auth
def api_backup_status():
    """
    Get backup system status.
    Shows if backups are enabled, last backup time, and configuration.
    """
    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    return jsonify(backup.get_backup_status())


@app.route('/api/backup/run', methods=['POST'])
@limiter.limit("2 per hour")
@require_auth
def api_backup_run():
    """
    Trigger a manual backup (admin only).
    Runs backup in background thread.
    """
    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    if not os.environ.get('BACKUP_DIR'):
        return jsonify({'error': 'BACKUP_DIR not configured'}), 400

    # Run backup in background
    backup_thread = threading.Thread(target=backup.run_backup, daemon=True)
    backup_thread.start()

    return jsonify({'status': 'started', 'message': 'Backup started in background'})


@app.route('/api/stats/user/<user_id>')
@require_auth
def api_user_stats(user_id):
    """
    Get generation and usage statistics for a specific user.

    Returns generation counts by model, plays received, downloads, votes, etc.
    Requires authentication - users can only view their own stats unless admin.
    """
    # Security: Only allow users to see their own stats, unless admin
    if request.user_id != user_id and not request.user.get('is_admin'):
        return jsonify({'error': 'Access denied - can only view your own stats'}), 403

    stats = db.get_user_stats(user_id)
    return jsonify(stats)


@app.route('/api/stats/system')
@require_auth
def api_system_stats():
    """
    Get system-wide statistics (admin only).

    Returns total generations, unique users, generation rates, top users, etc.
    """
    # Require admin privileges
    if not request.user.get('is_admin'):
        return jsonify({'error': 'Admin access required'}), 403

    stats = db.get_system_stats()
    return jsonify(stats)


@app.route('/api/library/category-counts')
def api_category_counts():
    """
    Get counts for each category/genre.

    Query params:
        model: Optional filter by 'music' or 'audio'

    Returns:
        Dict mapping category names to counts
    """
    model = request.args.get('model')
    counts = db.get_category_counts(model=model)
    return jsonify(counts)


# =============================================================================
# NEW API: Voting with Private Feedback
# =============================================================================

@app.route('/api/library/<gen_id>/vote', methods=['POST'])
@limiter.limit("100 per hour")
@require_auth
def api_vote(gen_id):
    """
    Cast or update a vote with optional private feedback.

    Requires authentication via Bearer token.

    Body:
        vote: 1 (upvote), -1 (downvote), or 0 (remove)
        feedback_reasons: Optional list of feedback tags (e.g., ['catchy', 'quality'])
        notes: Optional private notes (not displayed publicly)
        suggested_model: Optional reclassification suggestion ('music' or 'audio')
    """
    if not is_valid_gen_id(gen_id):
        return jsonify({'error': 'Invalid generation ID format'}), 400
    data = request.json or {}
    vote_value = data.get('vote', 0)
    user_id = request.user_id  # From verified auth token
    feedback_reasons = data.get('feedback_reasons')  # List of tags
    notes = data.get('notes')  # Private notes
    suggested_model = data.get('suggested_model')  # Reclassification suggestion

    if vote_value not in [-1, 0, 1]:
        return jsonify({'error': 'vote must be -1, 0, or 1'}), 400

    # Validate suggested_model if provided
    if suggested_model and suggested_model not in ('music', 'audio'):
        return jsonify({'error': 'suggested_model must be "music" or "audio"'}), 400

    # Validate notes if provided (with content moderation)
    if notes:
        is_valid, notes, error = validate_text_input(
            notes, 'Notes', MAX_NOTES_LENGTH, required=False
        )
        if not is_valid:
            return jsonify({'error': error}), 400

    # Validate feedback_reasons if provided
    if feedback_reasons:
        if not isinstance(feedback_reasons, list):
            return jsonify({'error': 'feedback_reasons must be a list'}), 400
        if len(feedback_reasons) > 10:
            return jsonify({'error': 'Too many feedback reasons (max 10)'}), 400
        # Validate each reason is a string and reasonable length
        validated_reasons = []
        for reason in feedback_reasons:
            if not isinstance(reason, str):
                return jsonify({'error': 'Each feedback reason must be a string'}), 400
            reason = reason.strip()[:50]  # Limit reason length
            if reason:
                validated_reasons.append(reason)
        feedback_reasons = validated_reasons if validated_reasons else None

    # Verify generation exists
    generation = db.get_generation(gen_id)
    if not generation:
        return jsonify({'error': 'Not found'}), 404

    result = db.vote(gen_id, user_id, vote_value, feedback_reasons, notes, suggested_model)
    return jsonify(result)


@app.route('/api/library/votes', methods=['POST'])
@limiter.limit("200 per hour")  # Rate limit batch vote lookups
@require_auth
def api_get_votes():
    """
    Get user's votes for multiple generations.
    Requires authentication via Bearer token.

    Body:
        generation_ids: List of generation IDs (max 100)
    """
    data = request.json or {}
    generation_ids = data.get('generation_ids', [])
    user_id = request.user_id  # From verified auth token

    # Limit array size to prevent DoS
    if not isinstance(generation_ids, list) or len(generation_ids) > 100:
        return jsonify({'error': 'generation_ids must be a list with max 100 items'}), 400

    votes = db.get_user_votes(generation_ids, user_id)
    return jsonify({'votes': votes})


@app.route('/api/library/<gen_id>/feedback')
def api_get_feedback(gen_id):
    """
    Get feedback summary for a generation.
    Returns positive and negative feedback reason counts.
    """
    feedback = db.get_generation_feedback(gen_id)
    return jsonify(feedback)


# =============================================================================
# Tag Suggestions API - Crowdsourced Categorization
# =============================================================================

@app.route('/api/library/<gen_id>/suggest-tag', methods=['POST'])
@limiter.limit("50 per hour")
@optional_auth
def api_suggest_tag(gen_id):
    """
    Submit a tag/category suggestion for a generation.
    When 3+ users agree, the category is automatically applied or removed.

    Body:
        category: The category to suggest
        action: 'add' (default) or 'remove'

    SECURITY NOTE: Anonymous users are tracked by IP address (request.remote_addr).
    This means:
    - Users behind shared IPs (corporate, VPN) count as one vote
    - IP changes allow re-voting (acceptable for low-stakes tagging)
    - Rate limiting (50/hour) prevents mass manipulation
    - Requires 3+ unique voters for consensus, limiting single-actor impact
    """
    if not is_valid_gen_id(gen_id):
        return jsonify({'error': 'Invalid generation ID format'}), 400
    data = request.get_json()
    # SECURITY: Use verified user_id from auth token when available.
    # Fallback to IP for anonymous users - see docstring for implications.
    # We use request.remote_addr (not X-Forwarded-For) to prevent header spoofing.
    user_id = request.user_id or request.remote_addr

    if not data or 'category' not in data:
        return jsonify({'error': 'Missing category'}), 400

    action = data.get('action', 'add')
    if action not in ('add', 'remove'):
        return jsonify({'error': 'Invalid action. Must be "add" or "remove"'}), 400

    result = db.submit_tag_suggestion(gen_id, user_id, data['category'], action)

    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/library/<gen_id>/cancel-tag', methods=['POST'])
@limiter.limit("50 per hour")
@optional_auth
def api_cancel_tag(gen_id):
    """
    Cancel a user's own tag suggestion.

    Body:
        category: The category suggestion to cancel
        action: 'add' (default) or 'remove' - which type of suggestion to cancel
    """
    data = request.get_json()
    # SECURITY: Same user identification as suggest-tag (see that endpoint for details)
    user_id = request.user_id or request.remote_addr

    if not data or 'category' not in data:
        return jsonify({'error': 'Missing category'}), 400

    action = data.get('action', 'add')
    if action not in ('add', 'remove'):
        return jsonify({'error': 'Invalid action. Must be "add" or "remove"'}), 400

    result = db.cancel_tag_suggestion(gen_id, user_id, data['category'], action)

    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/library/<gen_id>/tag-suggestions')
@optional_auth
def api_get_tag_suggestions(gen_id):
    """
    Get all tag suggestions for a generation with vote counts.
    """
    # Use authenticated user_id if available, fallback to IP for anonymous
    user_id = request.user_id or request.remote_addr

    # Get all suggestions with counts
    suggestions = db.get_tag_suggestions(gen_id)

    # Get user's own suggestions
    user_suggestions = db.get_user_suggestions(gen_id, user_id)

    # Get the generation info
    with db.get_db() as conn:
        gen = conn.execute(
            "SELECT model, category FROM generations WHERE id = ?",
            (gen_id,)
        ).fetchone()

    if not gen:
        return jsonify({'error': 'Generation not found'}), 404

    try:
        current_categories = json.loads(gen['category'] or '[]')
    except (json.JSONDecodeError, TypeError):
        current_categories = []

    return jsonify({
        'suggestions': suggestions,
        'user_suggestions': user_suggestions,
        'current_categories': current_categories,
        'threshold': db.TAG_CONSENSUS_THRESHOLD
    })


@app.route('/api/categories/<model>')
@limiter.limit("60 per minute")  # SECURITY: Rate limit to prevent DoS
def api_get_categories(model):
    """
    Get all available categories for a model type (music, audio, or voice).
    Includes usage counts for sorting by popularity.
    """
    if model not in ('music', 'audio', 'voice'):
        return jsonify({'error': 'Invalid model type'}), 400

    categories = db.get_available_categories(model)

    # Get usage counts for each category
    counts = db.get_category_counts(model)

    # Build response with usage data
    categories_with_counts = {}
    for cat_key, display_name in categories.items():
        categories_with_counts[cat_key] = {
            'display': display_name,
            'count': counts.get(cat_key, 0)
        }

    return jsonify({
        'categories': categories,
        'categories_with_counts': categories_with_counts
    })


# =============================================================================
# Graphlings Game/App Sources API
# =============================================================================

@app.route('/api/graphlings/sources')
def api_graphlings_sources():
    """
    Get all available Graphlings sources (games/apps) with counts.

    Returns:
        sources: dict of source_id -> source info
        counts: dict of source_id -> {music, audio, voice, total}
    """
    sources = db.get_graphlings_sources()
    counts = db.get_graphlings_source_counts()

    return jsonify({
        'sources': sources,
        'counts': counts
    })


@app.route('/api/graphlings/sources/<source_id>')
def api_graphlings_source_detail(source_id):
    """
    Get details for a specific Graphlings source.

    Returns source info and library filtered to that source.
    """
    sources = db.get_graphlings_sources()

    if source_id not in sources:
        return jsonify({'error': 'Source not found'}), 404

    source = sources[source_id]
    counts = db.get_graphlings_source_counts().get(source_id, {
        'music': 0, 'audio': 0, 'voice': 0, 'total': 0
    })

    return jsonify({
        'source_id': source_id,
        'source': source,
        'counts': counts
    })


@app.route('/api/graphlings/library')
def api_graphlings_library():
    """
    Get library filtered by Graphlings source.

    Query params:
        source: Required - Graphlings source ID (e.g., 'byk3s')
        model: Optional - Filter by 'music', 'audio', or 'voice'
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        sort: 'recent', 'popular', or 'rating'
    """
    source = request.args.get('source')

    if not source:
        return jsonify({'error': 'source parameter required'}), 400

    sources = db.get_graphlings_sources()
    if source not in sources:
        return jsonify({'error': 'Invalid source'}), 400

    page, per_page = get_pagination_params()
    model = request.args.get('model')
    if model and model not in ('music', 'audio', 'voice'):
        model = None
    sort = request.args.get('sort', 'recent')
    if sort not in ('recent', 'popular', 'rating'):
        sort = 'recent'

    result = db.get_library(
        page=page,
        per_page=per_page,
        model=model,
        sort=sort,
        source=source
    )

    return jsonify(result)


@app.route('/api/graphlings/set-source', methods=['POST'])
@limiter.limit("60 per minute")
@require_auth
def api_set_graphlings_source():
    """
    Set or update the source for one or more generations.
    Requires admin authentication.

    Body:
        generation_ids: List of generation IDs
        source: Source ID (e.g., 'byk3s') or null to clear
    """
    # Check if user is admin
    if not request.user.get('is_admin', False):
        return jsonify({'error': 'Admin access required'}), 403

    data = request.json or {}
    generation_ids = data.get('generation_ids', [])
    source = data.get('source')

    if not generation_ids:
        return jsonify({'error': 'generation_ids required'}), 400

    if not isinstance(generation_ids, list):
        return jsonify({'error': 'generation_ids must be a list'}), 400

    # Validate source if provided
    if source:
        sources = db.get_graphlings_sources()
        if source not in sources:
            return jsonify({'error': f'Invalid source: {source}'}), 400

    updated = db.bulk_set_source(generation_ids, source)

    return jsonify({
        'success': True,
        'updated': updated,
        'source': source
    })


# =============================================================================
# NEW API: Radio Station
# =============================================================================

@app.route('/api/radio/shuffle')
@limiter.limit("120 per minute")  # Rate limit for shuffle
def api_radio_shuffle():
    """
    Get random tracks for radio shuffle.

    Query params:
        model: Filter by 'music' or 'audio' (recommended)
        search: Optional keyword filter
        count: Number of tracks (default 10, max 50)
    """
    model = request.args.get('model')
    search = request.args.get('search')
    count = safe_int(request.args.get('count'), default=10, min_val=1, max_val=50)

    tracks = db.get_random_tracks(model=model, search=search, count=count)

    return jsonify({
        'tracks': tracks,
        'filters': {
            'model': model,
            'search': search
        }
    })


@app.route('/api/radio/next')
def api_radio_next():
    """
    Get more tracks for continuous radio playback, excluding recently played.

    Query params:
        model: Filter by 'music' or 'audio'
        search: Optional keyword filter
        count: Number of tracks (default 5, max 20)
        exclude: Comma-separated list of track IDs to exclude (recently played)
    """
    model = request.args.get('model')
    search = request.args.get('search')
    count = safe_int(request.args.get('count'), default=5, min_val=1, max_val=20)
    exclude_str = request.args.get('exclude', '')

    # Parse exclude list (limit to 100 to prevent abuse)
    exclude_ids = [id.strip() for id in exclude_str.split(',') if id.strip()][:100]

    tracks = db.get_random_tracks_excluding(
        model=model,
        search=search,
        count=count,
        exclude_ids=exclude_ids if exclude_ids else None
    )

    return jsonify({
        'tracks': tracks,
        'filters': {
            'model': model,
            'search': search
        }
    })


# =============================================================================
# Favorites - Requires authentication
# =============================================================================

@app.route('/api/favorites/<gen_id>', methods=['POST'])
@limiter.limit("100 per hour")
@require_auth
def api_add_favorite(gen_id):
    """Add a generation to user's favorites. Requires authentication."""
    if not is_valid_gen_id(gen_id):
        return jsonify({'error': 'Invalid generation ID format'}), 400
    user_id = request.user_id  # From verified auth token

    # Verify generation exists
    generation = db.get_generation(gen_id)
    if not generation:
        return jsonify({'error': 'Not found'}), 404

    added = db.add_favorite(user_id, gen_id)
    return jsonify({
        'success': True,
        'favorited': True,
        'was_new': added
    })


@app.route('/api/favorites/<gen_id>', methods=['DELETE'])
@limiter.limit("100 per hour")
@require_auth
def api_remove_favorite(gen_id):
    """Remove a generation from user's favorites. Requires authentication."""
    if not is_valid_gen_id(gen_id):
        return jsonify({'error': 'Invalid generation ID format'}), 400
    user_id = request.user_id  # From verified auth token

    removed = db.remove_favorite(user_id, gen_id)
    return jsonify({
        'success': True,
        'favorited': False,
        'was_removed': removed
    })


@app.route('/api/favorites')
@require_auth
def api_get_favorites():
    """Get user's favorites (paginated). Requires authentication."""
    user_id = request.user_id  # From verified auth token

    page, per_page = get_pagination_params()
    model = request.args.get('model')

    result = db.get_favorites(user_id, page=page, per_page=per_page, model=model)
    return jsonify(result)


@app.route('/api/favorites/check', methods=['POST'])
@limiter.limit("200 per hour")  # Rate limit batch favorite checks
@require_auth
def api_check_favorites():
    """Check which generations are favorited by user. Requires authentication."""
    data = request.json or {}
    user_id = request.user_id  # From verified auth token
    generation_ids = data.get('generation_ids', [])

    # Limit array size to prevent DoS
    if not isinstance(generation_ids, list) or len(generation_ids) > 100:
        return jsonify({'error': 'generation_ids must be a list with max 100 items'}), 400

    favorites = db.get_user_favorites(user_id, generation_ids)
    return jsonify({'favorites': list(favorites)})


@app.route('/api/radio/favorites')
@require_auth
def api_radio_favorites():
    """Shuffle play user's favorites. Requires authentication."""
    user_id = request.user_id  # From verified auth token

    model = request.args.get('model')
    count = safe_int(request.args.get('count'), default=10, min_val=1, max_val=50)

    tracks = db.get_random_favorites(user_id, count=count, model=model)
    return jsonify({
        'tracks': tracks,
        'source': 'favorites'
    })


@app.route('/api/radio/top-rated')
def api_radio_top_rated():
    """Get top rated tracks for radio."""
    model = request.args.get('model')
    count = safe_int(request.args.get('count'), default=10, min_val=1, max_val=50)

    tracks = db.get_top_rated_tracks(model=model, count=count)
    return jsonify({
        'tracks': tracks,
        'source': 'top-rated'
    })


@app.route('/api/radio/new')
def api_radio_new():
    """Get recently created tracks for radio."""
    model = request.args.get('model')
    count = safe_int(request.args.get('count'), default=10, min_val=1, max_val=50)
    hours = safe_int(request.args.get('hours'), default=168, min_val=1, max_val=8760)  # Default 7 days, max 1 year

    tracks = db.get_recent_tracks(model=model, count=count, hours=hours)
    return jsonify({
        'tracks': tracks,
        'source': 'new'
    })


# =============================================================================
# User History - Requires authenticated user from Graphlings/Valnet widget
# =============================================================================

@app.route('/api/history/plays')
@require_auth
def api_play_history():
    """Get user's play history. Requires authentication."""
    user_id = request.user_id  # From verified auth token

    limit = safe_int(request.args.get('limit'), default=50, min_val=1, max_val=100)
    offset = safe_int(request.args.get('offset'), default=0, min_val=0)

    history = db.get_user_play_history(user_id, limit=limit, offset=offset)
    return jsonify({
        'history': history,
        'limit': limit,
        'offset': offset,
        'has_more': len(history) == limit
    })


@app.route('/api/history/votes')
@require_auth
def api_vote_history():
    """Get user's vote history. Requires authentication."""
    user_id = request.user_id  # From verified auth token

    limit = safe_int(request.args.get('limit'), default=50, min_val=1, max_val=100)
    offset = safe_int(request.args.get('offset'), default=0, min_val=0)

    history = db.get_user_vote_history(user_id, limit=limit, offset=offset)
    return jsonify({
        'history': history,
        'limit': limit,
        'offset': offset,
        'has_more': len(history) == limit
    })


# =============================================================================
# Playlists - Requires authentication via Bearer token
# =============================================================================

@app.route('/api/playlists', methods=['POST'])
@limiter.limit("20 per hour")  # Playlist creation is less frequent
@require_auth
def api_create_playlist():
    """Create a new playlist. Requires authentication."""
    data = request.get_json() or {}
    user_id = request.user_id  # From verified auth token

    # Validate name with content moderation
    is_valid, name, error = validate_text_input(
        data.get('name'), 'Playlist name', MAX_PLAYLIST_NAME_LENGTH, required=True
    )
    if not is_valid:
        return jsonify({'error': error}), 400

    # Validate description (optional)
    is_valid, description, error = validate_text_input(
        data.get('description'), 'Description', MAX_DESCRIPTION_LENGTH, required=False
    )
    if not is_valid:
        return jsonify({'error': error}), 400

    # Generate unique playlist ID
    playlist_id = 'pl_' + uuid.uuid4().hex[:12]

    result = db.create_playlist(playlist_id, user_id, name, description)
    if result:
        return jsonify(result), 201
    return jsonify({'error': 'Failed to create playlist'}), 500


@app.route('/api/playlists')
@require_auth
def api_get_playlists():
    """Get user's playlists. Requires authentication."""
    user_id = request.user_id  # From verified auth token

    page, per_page = get_pagination_params()

    result = db.get_user_playlists(user_id, page, per_page)
    return jsonify(result)


@app.route('/api/playlists/<playlist_id>')
@optional_auth
def api_get_playlist(playlist_id):
    """Get a playlist with its tracks. Optional authentication for private playlists."""
    playlist = db.get_playlist(playlist_id)
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404

    # Check ownership for private playlists (future feature)
    # For now, all playlists are public/viewable

    tracks = db.get_playlist_tracks(playlist_id, include_metadata=True)
    playlist['tracks'] = tracks
    playlist['is_owner'] = (request.user_id == playlist.get('user_id')) if request.user_id else False

    return jsonify(playlist)


@app.route('/api/playlists/<playlist_id>', methods=['PUT'])
@limiter.limit("50 per hour")
@require_auth
def api_update_playlist(playlist_id):
    """Update playlist name/description. Requires authentication and ownership."""
    data = request.get_json() or {}
    user_id = request.user_id  # From verified auth token

    # Validate name if provided
    name = None
    if 'name' in data:
        is_valid, name, error = validate_text_input(
            data.get('name'), 'Playlist name', MAX_PLAYLIST_NAME_LENGTH, required=True
        )
        if not is_valid:
            return jsonify({'error': error}), 400

    # Validate description if provided
    description = None
    if 'description' in data:
        is_valid, description, error = validate_text_input(
            data.get('description'), 'Description', MAX_DESCRIPTION_LENGTH, required=False
        )
        if not is_valid:
            return jsonify({'error': error}), 400

    result = db.update_playlist(playlist_id, user_id, name, description)
    if result:
        return jsonify(result)
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>', methods=['DELETE'])
@limiter.limit("20 per hour")
@require_auth
def api_delete_playlist(playlist_id):
    """Delete a playlist. Requires authentication and ownership."""
    user_id = request.user_id  # From verified auth token

    if db.delete_playlist(playlist_id, user_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>/tracks', methods=['POST'])
@limiter.limit("200 per hour")  # Adding tracks is common operation
@require_auth
def api_add_playlist_track(playlist_id):
    """Add a track to a playlist. Requires authentication and ownership."""
    data = request.get_json() or {}
    user_id = request.user_id  # From verified auth token
    generation_id = data.get('generation_id')

    if not generation_id:
        return jsonify({'error': 'generation_id required'}), 400

    result = db.add_track_to_playlist(playlist_id, generation_id, user_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/playlists/<playlist_id>/tracks/<generation_id>', methods=['DELETE'])
@limiter.limit("200 per hour")
@require_auth
def api_remove_playlist_track(playlist_id, generation_id):
    """Remove a track from a playlist. Requires authentication and ownership."""
    user_id = request.user_id  # From verified auth token

    if db.remove_track_from_playlist(playlist_id, generation_id, user_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Track not found in playlist or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>/reorder', methods=['PUT'])
@limiter.limit("50 per hour")
@require_auth
def api_reorder_playlist(playlist_id):
    """Reorder tracks in a playlist. Requires authentication and ownership."""
    data = request.get_json() or {}
    user_id = request.user_id  # From verified auth token
    track_order = data.get('track_order', [])

    if not track_order:
        return jsonify({'error': 'track_order required'}), 400

    # Limit array size to prevent DoS (reasonable playlist size limit)
    if not isinstance(track_order, list) or len(track_order) > 500:
        return jsonify({'error': 'track_order must be a list with max 500 items'}), 400

    if db.reorder_playlist_tracks(playlist_id, user_id, track_order):
        return jsonify({'success': True})
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/radio/playlist/<playlist_id>')
def api_radio_playlist(playlist_id):
    """Get playlist tracks for radio playback. Public access for sharing."""
    shuffle = request.args.get('shuffle', 'false').lower() == 'true'

    playlist = db.get_playlist(playlist_id)
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404

    tracks = db.get_playlist_for_radio(playlist_id, shuffle=shuffle)
    return jsonify({
        'tracks': tracks,
        'source': 'playlist',
        'playlist_id': playlist_id,
        'playlist_name': playlist['name']
    })


# =============================================================================
# Database Stats
# =============================================================================

@app.route('/api/stats')
@limiter.limit("30 per minute")  # SECURITY: Rate limit to prevent DoS on aggregation queries
def api_stats():
    """Get database statistics."""
    return jsonify(db.get_stats())


# =============================================================================
# Play & Download Tracking
# =============================================================================

@app.route('/api/track/<gen_id>/play', methods=['POST', 'OPTIONS'])
@limiter.limit("300 per hour")  # Rate limit play tracking to prevent inflation
@optional_auth
def api_record_play(gen_id):
    """Record a play event for analytics."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    data = request.get_json() or {}
    # Security: Use authenticated user_id from token, not client-provided value
    # Fall back to session_id for anonymous tracking
    user_id = request.user_id if request.user_id else None
    session_id = data.get('session_id')
    play_duration = data.get('duration')
    source = data.get('source', 'radio')

    # SECURITY: Validate session_id to prevent abuse
    # Session IDs should be reasonable length (UUID-like) and alphanumeric
    if session_id:
        if not isinstance(session_id, str) or len(session_id) > 64:
            session_id = None  # Reject oversized session IDs silently
        elif not all(c.isalnum() or c == '-' for c in session_id):
            session_id = None  # Reject non-alphanumeric session IDs

    # SECURITY: Validate play_duration to prevent unreasonable values
    if play_duration is not None:
        try:
            play_duration = float(play_duration)
            if play_duration < 0 or play_duration > 3600:  # Max 1 hour
                play_duration = None
        except (TypeError, ValueError):
            play_duration = None

    # SECURITY: Validate source to prevent injection
    allowed_sources = ('radio', 'library', 'embed', 'widget', 'direct', 'playlist')
    if source not in allowed_sources:
        source = 'unknown'

    result = db.record_play(gen_id, user_id, session_id, play_duration, source)
    response = jsonify(result)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/api/track/<gen_id>/stats')
def api_play_stats(gen_id):
    """Get play statistics for a track."""
    stats = db.get_play_stats(gen_id)
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'Track not found'}), 404


@app.route('/api/trending')
def api_trending():
    """Get trending tracks based on recent plays."""
    hours = request.args.get('hours', 24, type=int)
    hours = max(1, min(hours, 8760))  # Clamp to 1 hour - 1 year
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(limit, 100))  # Clamp to 1-100
    model = request.args.get('model')
    if model and model not in ('music', 'audio', 'voice'):
        model = None

    tracks = db.get_trending_tracks(hours, limit, model)
    return jsonify({'tracks': tracks})


@app.route('/api/most-played')
def api_most_played():
    """Get most played tracks."""
    limit = request.args.get('limit', 50, type=int)
    limit = max(1, min(limit, 100))  # Clamp to 1-100
    model = request.args.get('model')
    if model and model not in ('music', 'audio', 'voice'):
        model = None
    days = request.args.get('days', type=int)
    if days is not None:
        days = max(1, min(days, 365))  # Clamp to 1-365 days

    tracks = db.get_most_played(limit, model, days)
    return jsonify({'tracks': tracks})


@app.route('/api/log-error', methods=['POST'])
@limiter.limit("10 per minute")  # Strict rate limit to prevent log flooding
def api_log_error():
    """Log frontend errors to backend."""
    data = request.get_json() or {}

    def sanitize_log_input(text, max_length):
        """Sanitize user input for safe logging.

        SECURITY: Removes control characters that could:
        - Inject ANSI escape codes to manipulate terminal output
        - Add fake log entries via newlines
        - Corrupt log parsing via special characters
        """
        text = str(text)[:max_length]
        # Replace control chars (except space) with '?', keep printable ASCII and common Unicode
        return ''.join(c if c.isprintable() or c == ' ' else '?' for c in text)

    # Truncate and sanitize all inputs to prevent log injection attacks
    message = sanitize_log_input(data.get('message', 'Unknown error'), 500)
    url = sanitize_log_input(data.get('url', ''), 200)
    user_agent = sanitize_log_input(data.get('userAgent', ''), 100)
    timestamp = sanitize_log_input(data.get('timestamp', ''), 50)

    # Log to console with formatting
    print(f"\n{'='*60}")
    print(f"[FRONTEND ERROR] {timestamp}")
    print(f"Message: {message}")
    print(f"URL: {url}")
    print(f"User-Agent: {user_agent}...")
    print(f"{'='*60}\n")

    return jsonify({'logged': True})


# =============================================================================
# TTS / Voice Endpoints
# =============================================================================

# Voice list cache to avoid repeated filesystem scans
_voices_cache = {'voices': None, 'time': 0}
_VOICES_CACHE_TTL = 300  # 5 minutes


def get_available_voices():
    """Scan voices directory and return available voice models (cached)."""
    global _voices_cache

    # Return cached value if fresh
    now = time.time()
    if _voices_cache['voices'] is not None and now - _voices_cache['time'] < _VOICES_CACHE_TTL:
        return _voices_cache['voices']

    voices = []
    if not os.path.exists(VOICES_DIR):
        _voices_cache = {'voices': voices, 'time': now}
        return voices

    for filename in os.listdir(VOICES_DIR):
        if filename.endswith('.onnx') and not filename.endswith('.onnx.json'):
            voice_id = filename.replace('.onnx', '')
            json_path = os.path.join(VOICES_DIR, f"{voice_id}.onnx.json")

            # Parse voice metadata from filename (e.g., "en_US-lessac-medium")
            parts = voice_id.split('-')
            locale = parts[0] if parts else 'unknown'
            name = parts[1] if len(parts) > 1 else 'unknown'
            quality = parts[2] if len(parts) > 2 else 'medium'

            # Try to read JSON config for additional metadata
            description = ""
            sample_rate = 22050
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        # Handle explicit null values with (x or {}) pattern
                        sample_rate = (config.get('audio') or {}).get('sample_rate', 22050)
                        description = config.get('description', '')
                except (json.JSONDecodeError, OSError):
                    pass  # Use defaults if config is invalid

            # Get license information
            license_info = voice_licenses.get_voice_license_info(voice_id)
            license_data = (license_info.get('license') or {})

            voices.append({
                'id': voice_id,
                'name': name.replace('_', ' ').title(),
                'locale': locale,
                'quality': quality,
                'description': description,
                'sample_rate': sample_rate,
                'onnx_path': os.path.join(VOICES_DIR, filename),
                # License information
                'commercial_ok': license_info.get('commercial_ok', False),
                'license': license_data.get('name', 'Unknown'),
                'license_short': license_data.get('short', 'Unknown'),
                'attribution': license_info.get('attribution_text', ''),
                'attribution_url': license_info.get('attribution_url'),
                'license_url': license_data.get('url'),
                'license_warning': license_info.get('warning')
            })

    # Sort by locale, then name
    voices.sort(key=lambda v: (v['locale'], v['name']))

    # Cache the result
    _voices_cache['voices'] = voices
    _voices_cache['time'] = now

    return voices


def get_voice_model(voice_id):
    """Load and cache a Piper voice model with LRU eviction (thread-safe)."""
    # Security: Defense-in-depth validation of voice_id
    if not is_safe_voice_id(voice_id):
        return None

    with voice_models_lock:
        if voice_id in voice_models:
            # Move to end (most recently used)
            voice_models.move_to_end(voice_id)
            return voice_models[voice_id]

    onnx_path = os.path.join(VOICES_DIR, f"{voice_id}.onnx")
    json_path = os.path.join(VOICES_DIR, f"{voice_id}.onnx.json")

    if not os.path.exists(onnx_path):
        return None

    try:
        # Load model with GPU if available (outside lock to avoid blocking)
        voice = PiperVoice.load(onnx_path, config_path=json_path, use_cuda=torch.cuda.is_available())

        with voice_models_lock:
            # Double-check in case another thread loaded it
            if voice_id in voice_models:
                return voice_models[voice_id]

            voice_models[voice_id] = voice

            # Evict oldest models if cache is full
            while len(voice_models) > _VOICE_CACHE_MAX_SIZE:
                oldest_id, _ = voice_models.popitem(last=False)
                print(f"[Voice] Evicted {oldest_id} from cache (cache full)")

        return voice
    except Exception as e:
        print(f"Failed to load voice {voice_id}: {e}")
        return None


@app.route('/api/voices')
def api_voices():
    """List all available TTS voices with license information."""
    voices = get_available_voices()
    return jsonify({
        'voices': voices,
        'total': len(voices)
    })


@app.route('/api/voice-licenses')
def api_voice_licenses():
    """Get detailed license information for all voice datasets."""
    return jsonify(voice_licenses.get_all_voice_licenses())


@app.route('/api/tts/generate', methods=['POST'])
@limiter.limit("60 per hour")  # Base rate limit (tier-based limits checked in handler)
@require_auth_or_localhost  # Authentication required, but localhost can bypass for batch generation
def api_tts_generate():
    """
    Generate speech from text using Piper TTS. Requires authentication.

    Requirements:
    - All users must be authenticated
    - Free users must have verified email
    - Paying subscribers can generate without email verification

    Rate limits by tier:
    - Creator ($20/mo): 120/hour
    - Premium ($10/mo): 60/hour
    - Supporter ($5/mo): 30/hour
    - Free (verified): 10/hour

    By default, audio is returned as base64 WITHOUT saving to server/library.
    This prevents the library from being polluted with arbitrary user narrations.

    To save to library, pass save_to_library=true (requires content moderation).
    """
    # Check user tier for rate limiting info
    tier = get_user_tier(request.user)

    # Free users must have verified email to use TTS (skip in open access mode)
    if not OPEN_ACCESS_MODE and tier == 'free' and not is_email_verified(request.user):
        return jsonify({
            'error': 'Please verify your email address to use text-to-speech. Check your inbox for the verification link, or upgrade to a subscription plan.',
            'requires_verification': True
        }), 403

    # TTS limits per hour by tier (matching subscription levels)
    tts_limits = {
        'creator': 120,   # $20/mo - AI features tier
        'premium': 60,    # $10/mo
        'supporter': 30,  # $5/mo
        'free': 10        # Free tier
    }
    # Note: Actual rate limiting should be dynamic, but flask-limiter doesn't easily support this
    # For now, we use a reasonable limit that works for all tiers
    import base64
    import tempfile

    data = request.get_json() or {}
    text = data.get('text', '').strip()
    voice_id = data.get('voice') or 'en_US-lessac-medium'  # Handle empty string
    save_to_library = data.get('save_to_library', False)
    tags = data.get('tags', [])  # Optional category tags

    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if len(text) > 5000:
        return jsonify({'error': 'Text too long (max 5000 chars)'}), 400

    # Always check for blocked content (even for local-only generation)
    is_blocked, reason = contains_blocked_content(text)
    if is_blocked:
        return jsonify({'error': f'Content blocked: {reason}'}), 400

    voice = get_voice_model(voice_id)
    if not voice:
        return jsonify({'error': f'Voice not found: {voice_id}'}), 404

    try:
        gen_id = uuid.uuid4().hex

        if save_to_library:
            # Save to server - permanent storage
            filename = f"tts_{gen_id}.wav"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with wave.open(filepath, 'wb') as wav_file:
                voice.synthesize_wav(text, wav_file)

            # Get duration from file
            import scipy.io.wavfile as wav_reader
            sample_rate, audio_data = wav_reader.read(filepath)
            duration = len(audio_data) / max(sample_rate, 1)  # Guard against zero

            # Save to database - clean up file on failure
            # Localhost/admin TTS generations are public by default
            is_public = is_localhost_request() or (hasattr(request, 'user') and request.user.get('is_admin', False))
            try:
                db.create_generation(
                    gen_id=gen_id,
                    prompt=text[:200],
                    model='voice',
                    filename=filename,
                    duration=duration,
                    is_loop=False,
                    is_public=is_public,
                    voice_id=voice_id,
                    tags=tags if tags else None
                )
            except Exception as db_err:
                # Clean up orphaned file on DB failure
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError as e:
                        print(f"[TTS] Warning: Failed to clean up orphaned file {filepath}: {e}")
                print(f"[TTS] Database save failed, cleaned up file: {db_err}")
                return jsonify({'error': 'Failed to save to library'}), 500

            return jsonify({
                'success': True,
                'saved_to_library': True,
                'filename': filename,
                'gen_id': gen_id,
                'duration': round(duration, 2),
                'voice': voice_id
            })
        else:
            # Local-only mode - use temp file, return base64, don't save to DB
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with wave.open(tmp_path, 'wb') as wav_file:
                    voice.synthesize_wav(text, wav_file)

                # Read and encode as base64
                with open(tmp_path, 'rb') as f:
                    audio_bytes = f.read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                # Get duration
                import scipy.io.wavfile as wav_reader
                sample_rate, audio_data = wav_reader.read(tmp_path)
                duration = len(audio_data) / max(sample_rate, 1)  # Guard against zero
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError as e:
                        print(f"Warning: Failed to clean up temp file {tmp_path}: {e}")

            return jsonify({
                'success': True,
                'saved_to_library': False,
                'audio_base64': audio_base64,
                'duration': round(duration, 2),
                'voice': voice_id
            })

    except Exception as e:
        import traceback
        print(f"TTS generation error: {e}")
        traceback.print_exc()
        return jsonify({'error': 'TTS generation failed'}), 500


@app.route('/api/tts/sample/<voice_id>')
def api_tts_sample(voice_id):
    """Get or generate a sample for a voice."""
    # Security: Validate voice_id to prevent path traversal
    if not is_safe_voice_id(voice_id):
        return jsonify({'error': 'Invalid voice ID format'}), 400

    # Check for cached sample
    sample_dir = os.path.join(OUTPUT_DIR, 'voice_samples')
    os.makedirs(sample_dir, exist_ok=True)
    sample_path = os.path.join(sample_dir, f"{voice_id}_sample.wav")

    if os.path.exists(sample_path):
        return send_file(sample_path, mimetype='audio/wav')

    # Generate sample
    voice = get_voice_model(voice_id)
    if not voice:
        return jsonify({'error': f'Voice not found: {voice_id}'}), 404

    try:
        # Use a standard sample text
        sample_text = "Hello! This is a sample of my voice. I can read any text you give me."

        # Use synthesize_wav to write directly to file
        with wave.open(sample_path, 'wb') as wav_file:
            voice.synthesize_wav(sample_text, wav_file)

        return send_file(sample_path, mimetype='audio/wav')

    except Exception as e:
        print(f"Sample generation error: {e}")
        return jsonify({'error': 'Sample generation failed'}), 500


def slugify_prompt(prompt, max_length=30):
    """Convert a prompt to a clean filename-safe slug."""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = prompt.lower().strip()
    # Remove special characters, keep alphanumeric and spaces
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    # Replace multiple spaces/hyphens with single hyphen
    slug = re.sub(r'[\s-]+', '-', slug)
    # Trim to max length, avoiding cutting mid-word if possible
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]
    return slug.strip('-')


@app.route('/download/<filename>')
@optional_auth
def download(filename):
    # Security: Validate filename to prevent path traversal
    if not is_safe_filename(filename) or not filename.endswith('.wav'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(OUTPUT_DIR, filename)

    # Additional security: Ensure resolved path is within OUTPUT_DIR
    real_path = os.path.realpath(filepath)
    real_output_dir = os.path.realpath(OUTPUT_DIR)
    if not real_path.startswith(real_output_dir + os.sep):
        return jsonify({'error': 'Invalid path'}), 400

    if os.path.exists(filepath):
        # Generate a clean download name from metadata
        metadata = load_metadata()
        file_info = metadata.get(filename, {})
        prompt = file_info.get('prompt', '')

        if prompt:
            # Create clean name: prompt-slug_6-char-id.wav
            slug = slugify_prompt(prompt)
            # Get last 6 chars of the UUID (filename without .wav)
            short_id = filename.replace('.wav', '')[-6:]
            clean_name = f"{slug}_{short_id}.wav"
        else:
            clean_name = filename

        # Track the download - SECURITY: Use authenticated user_id only
        # Don't accept user_id from query params to prevent spoofing analytics
        gen_id = filename.replace('.wav', '')
        db.record_download(gen_id, request.user_id, 'wav')

        return send_file(filepath, as_attachment=True, download_name=clean_name)
    return jsonify({'error': 'Not found'}), 404


@app.route('/random-prompt', methods=['POST'])
@limiter.limit("120 per hour")  # Rate limit prompt generation
def random_prompt():
    """Generate a random prompt using varied pattern templates with extensive vocabulary."""
    import random

    data = request.json or {}
    model_type = data.get('model', 'music')

    if model_type == 'music':
        # Extensive word lists
        moods = [
            'melancholic', 'upbeat', 'dreamy', 'intense', 'peaceful', 'energetic', 'mysterious',
            'triumphant', 'dark', 'chill', 'aggressive', 'romantic', 'nostalgic', 'epic', 'groovy',
            'haunting', 'euphoric', 'somber', 'playful', 'majestic', 'anxious', 'hopeful', 'serene',
            'chaotic', 'meditative', 'bittersweet', 'whimsical', 'ominous', 'tender', 'fierce',
            'contemplative', 'jubilant', 'wistful', 'rebellious', 'ethereal', 'gritty', 'soulful',
            'hypnotic', 'anthemic', 'intimate', 'grandiose', 'minimalistic', 'lush', 'raw',
            'polished', 'vintage', 'futuristic', 'organic', 'synthetic', 'warm', 'cold', 'bright',
            'murky', 'crystalline', 'hazy', 'sharp', 'smooth', 'rough', 'delicate', 'powerful',
            'subtle', 'bold', 'introspective', 'extroverted', 'lonely', 'communal', 'sacred',
            'profane', 'innocent', 'worldly', 'naive', 'sophisticated', 'primal', 'refined'
        ]

        genres = [
            'lo-fi', 'synthwave', 'jazz', 'orchestral', 'rock', 'ambient', 'funk', 'classical',
            'hip-hop', 'EDM', 'chiptune', 'metal', 'blues', 'reggae', 'folk', 'disco', 'soul',
            'country', 'bossa nova', 'trap', 'dubstep', 'house', 'techno', 'indie', 'punk',
            'grunge', 'R&B', 'gospel', 'latin', 'afrobeat', 'shoegaze', 'post-rock', 'math rock',
            'prog rock', 'psychedelic', 'krautrock', 'new wave', 'post-punk', 'darkwave',
            'industrial', 'EBM', 'trance', 'drum and bass', 'jungle', 'garage', 'grime',
            'UK drill', 'phonk', 'vaporwave', 'future bass', 'melodic dubstep', 'hardstyle',
            'hardcore', 'gabber', 'breakbeat', 'electro', 'italo disco', 'eurobeat', 'city pop',
            'J-pop', 'K-pop', 'C-pop', 'Bollywood', 'flamenco', 'tango', 'salsa', 'merengue',
            'bachata', 'cumbia', 'reggaeton', 'dancehall', 'dub', 'ska', 'rocksteady', 'calypso',
            'soca', 'zouk', 'highlife', 'afropop', 'mbalax', 'soukous', 'kwaito', 'amapiano',
            'gqom', 'kuduro', 'baile funk', 'fado', 'chanson', 'schlager', 'volksmusik',
            'klezmer', 'gamelan', 'raga', 'qawwali', 'gnawa', 'rai', 'throat singing',
            'bluegrass', 'Americana', 'outlaw country', 'honky tonk', 'western swing',
            'surf rock', 'garage rock', 'stoner rock', 'doom metal', 'black metal',
            'death metal', 'thrash metal', 'power metal', 'symphonic metal', 'nu metal',
            'metalcore', 'deathcore', 'djent', 'post-metal', 'sludge metal', 'drone metal',
            'noise rock', 'no wave', 'art rock', 'glam rock', 'hard rock', 'soft rock',
            'yacht rock', 'AOR', 'arena rock', 'southern rock', 'heartland rock',
            'Britpop', 'Madchester', 'dream pop', 'noise pop', 'jangle pop', 'twee pop',
            'chamber pop', 'baroque pop', 'sunshine pop', 'bubblegum pop', 'synth-pop',
            'electropop', 'dance-pop', 'teen pop', 'art pop', 'experimental pop',
            'avant-garde', 'free jazz', 'bebop', 'cool jazz', 'hard bop', 'modal jazz',
            'fusion', 'smooth jazz', 'acid jazz', 'nu jazz', 'swing', 'big band',
            'ragtime', 'stride', 'boogie-woogie', 'jump blues', 'rhythm and blues',
            'Chicago blues', 'Delta blues', 'Texas blues', 'British blues', 'blues rock',
            'neo-soul', 'quiet storm', 'new jack swing', 'contemporary R&B', 'alternative R&B',
            'boom bap', 'conscious hip-hop', 'gangsta rap', 'Southern rap', 'West Coast rap',
            'East Coast rap', 'Midwest rap', 'crunk', 'snap music', 'cloud rap', 'emo rap',
            'mumble rap', 'drill', 'Chicago drill', 'Brooklyn drill', 'horrorcore',
            'abstract hip-hop', 'jazz rap', 'trip-hop', 'downtempo', 'chillwave', 'witch house',
            'seapunk', 'PC Music', 'hyperpop', 'glitchcore', 'nightcore', 'speedcore',
            'happy hardcore', 'UK hardcore', 'freeform', 'Makina', 'hands up', 'hard dance',
            'hard trance', 'psytrance', 'Goa trance', 'progressive trance', 'uplifting trance',
            'tech trance', 'vocal trance', 'Balearic beat', 'Ibiza', 'deep house', 'tech house',
            'progressive house', 'electro house', 'big room', 'bass house', 'UK bass',
            'future house', 'tropical house', 'slap house', 'Brazilian bass', 'minimal techno',
            'dub techno', 'Detroit techno', 'Berlin techno', 'acid techno', 'hard techno',
            'industrial techno', 'peak time techno', 'melodic techno', 'organic house',
            'Afro house', 'tribal house', 'Latin house', 'soulful house', 'gospel house',
            'Chicago house', 'New York house', 'French house', 'filter house', 'disco house',
            'nu-disco', 'space disco', 'cosmic disco', 'Hi-NRG', 'freestyle', 'Miami bass',
            'booty bass', 'Baltimore club', 'Jersey club', 'Philly club', 'footwork', 'juke',
            'UK funky', '2-step', 'speed garage', 'bassline', 'UK garage', 'future garage',
            'post-dubstep', 'brostep', 'riddim', 'tearout', 'hybrid trap', 'festival trap',
            'wave', 'hardwave', 'dark ambient', 'space ambient', 'drone', 'dark drone'
        ]

        instruments = [
            'piano', 'guitar', 'synth', 'drums', 'strings', 'brass', 'bass', 'violin', 'saxophone',
            'flute', 'organ', 'harp', 'electric guitar', 'acoustic guitar', 'bells', 'marimba',
            'cello', 'trumpet', 'clarinet', 'harmonica', 'accordion', 'banjo', 'mandolin',
            'ukulele', 'sitar', 'tabla', 'didgeridoo', 'bagpipes', 'hurdy-gurdy', 'dulcimer',
            'zither', 'koto', 'shamisen', 'erhu', 'pipa', 'guzheng', 'oud', 'bouzouki',
            'balalaika', 'charango', 'cuatro', 'tres', 'steel drums', 'djembe', 'congas',
            'bongos', 'timbales', 'cajon', 'tambourine', 'shaker', 'cowbell', 'triangle',
            'glockenspiel', 'xylophone', 'vibraphone', 'celesta', 'tubular bells', 'timpani',
            'snare drum', 'kick drum', 'hi-hats', 'cymbals', 'tom-toms', 'electronic drums',
            '808', '909', 'drum machine', 'synth bass', 'Moog', 'Juno', 'Prophet', 'DX7',
            'Minimoog', 'ARP', 'Oberheim', 'Roland', 'Korg', 'Buchla', 'modular synth',
            'analog synth', 'digital synth', 'FM synth', 'wavetable synth', 'granular synth',
            'vocoder', 'talk box', 'keytar', 'Rhodes', 'Wurlitzer', 'Fender Rhodes',
            'Hammond organ', 'pipe organ', 'church organ', 'harmonium', 'melodica',
            'recorder', 'pan flute', 'ocarina', 'penny whistle', 'Native American flute',
            'shakuhachi', 'bansuri', 'ney', 'duduk', 'oboe', 'English horn', 'bassoon',
            'contrabassoon', 'piccolo', 'alto flute', 'bass flute', 'alto sax', 'tenor sax',
            'baritone sax', 'soprano sax', 'bass clarinet', 'French horn', 'trombone',
            'tuba', 'euphonium', 'cornet', 'flugelhorn', 'piccolo trumpet', 'muted trumpet',
            'viola', 'double bass', 'contrabass', 'electric bass', 'fretless bass', 'slap bass',
            'upright bass', 'synth strings', 'string section', 'orchestra', 'choir',
            'vocal harmonies', 'falsetto', 'whistle', 'humming', 'scat singing', 'throat singing',
            'beatboxing', 'samples', 'loops', 'field recordings', 'found sounds', 'noise',
            'feedback', 'distortion pedal', 'wah pedal', 'phaser', 'flanger', 'chorus',
            'delay', 'reverb', 'tremolo', 'vibrato', 'auto-tune', 'pitch shifter'
        ]

        textures = [
            'layered synths', 'organic textures', 'glitchy beats', 'warm pads', 'crisp percussion',
            'soaring melodies', 'deep basslines', 'atmospheric drones', 'shimmering arpeggios',
            'pulsing rhythms', 'swirling effects', 'crunchy distortion', 'silky smooth leads',
            'punchy kicks', 'snappy snares', 'rolling hi-hats', 'wobbling bass', 'sparkling highs',
            'rumbling lows', 'sweeping filters', 'gated reverb', 'sidechain compression',
            'vinyl crackle', 'tape hiss', 'bit-crushed sounds', 'granular textures',
            'stuttering glitches', 'chopped samples', 'pitched vocals', 'reversed sounds',
            'time-stretched audio', 'frequency modulation', 'ring modulation', 'vocoded voices',
            'lush reverb tails', 'tight dry sounds', 'stereo width', 'mono punch',
            'parallel compression', 'multiband dynamics', 'harmonic saturation', 'soft clipping',
            'hard limiting', 'pumping compression', 'breathing dynamics', 'sustaining notes',
            'staccato hits', 'legato phrases', 'portamento slides', 'vibrato expressions',
            'tremolo picking', 'palm muting', 'hammer-ons', 'pull-offs', 'string bends',
            'whammy bar dives', 'feedback squeals', 'harmonic overtones', 'sub-bass rumble',
            'mid-range warmth', 'high-end sparkle', 'full frequency spectrum', 'telephone EQ',
            'lo-fi filtering', 'hi-fi clarity', 'analog warmth', 'digital precision'
        ]

        scenes = [
            'a rainy day', 'driving at night', 'a sunset beach', 'a coffee shop', 'a space voyage',
            'an epic battle', 'a romantic dinner', 'meditation', 'working out', 'studying',
            'a chase scene', 'waking up slowly', 'a victory celebration', 'a mysterious forest',
            'an underwater adventure', 'walking through a city', 'stargazing', 'a campfire',
            'a thunderstorm', 'falling asleep', 'a sunrise hike', 'cooking dinner',
            'reading a book', 'a road trip', 'dancing alone', 'a first kiss', 'saying goodbye',
            'reuniting with a friend', 'exploring ruins', 'discovering a secret',
            'escaping danger', 'finding peace', 'overcoming fear', 'falling in love',
            'heartbreak', 'nostalgia', 'childhood memories', 'future dreams', 'inner turmoil',
            'finding clarity', 'letting go', 'new beginnings', 'final moments',
            'transcendence', 'awakening', 'transformation', 'reflection', 'celebration',
            'mourning', 'healing', 'growing', 'learning', 'teaching', 'creating', 'destroying',
            'building', 'exploring', 'discovering', 'hiding', 'seeking', 'finding', 'losing',
            'a neon-lit cyberpunk city', 'a medieval tavern', 'an alien planet',
            'a haunted mansion', 'a tropical paradise', 'a frozen wasteland',
            'a bustling marketplace', 'a quiet library', 'a smoky jazz club',
            'a packed stadium', 'an empty theater', 'a sacred temple', 'a dark dungeon',
            'a floating castle', 'a underwater city', 'a sky fortress', 'a desert oasis',
            'a volcanic island', 'a crystal cave', 'a mushroom forest', 'a clockwork tower',
            'a steampunk airship', 'a space station', 'a parallel dimension', 'the end of time'
        ]

        eras = [
            '1920s', '1930s', '1940s', '1950s', '1960s', '1970s', '1980s', '1990s', '2000s', '2010s',
            'retro', 'vintage', 'classic', 'modern', 'futuristic', 'timeless', 'ancient',
            'medieval', 'Renaissance', 'Baroque', 'Romantic era', 'Victorian', 'Edwardian',
            'Jazz Age', 'Swing era', 'post-war', 'Space Age', 'Atomic Age', 'hippie era',
            'disco era', 'New Wave era', 'MTV era', 'grunge era', 'Y2K', 'MySpace era',
            'SoundCloud era', 'TikTok era', 'pre-digital', 'early digital', 'streaming era',
            'AI era', 'near future', 'distant future', 'post-apocalyptic', 'alternate history',
            'cyberpunk future', 'solarpunk future', 'retrofuturistic', 'afrofuturistic'
        ]

        world_regions = [
            'African', 'West African', 'East African', 'South African', 'North African',
            'Asian', 'East Asian', 'Southeast Asian', 'South Asian', 'Central Asian',
            'Middle Eastern', 'Persian', 'Arabic', 'Turkish', 'Israeli', 'Lebanese',
            'Celtic', 'Irish', 'Scottish', 'Welsh', 'Breton', 'Nordic', 'Scandinavian',
            'Swedish', 'Norwegian', 'Finnish', 'Icelandic', 'Danish', 'Caribbean',
            'Jamaican', 'Cuban', 'Puerto Rican', 'Haitian', 'Trinidadian', 'Brazilian',
            'Argentine', 'Mexican', 'Colombian', 'Peruvian', 'Chilean', 'Venezuelan',
            'Indian', 'Pakistani', 'Bangladeshi', 'Nepali', 'Sri Lankan', 'Japanese',
            'Korean', 'Chinese', 'Taiwanese', 'Vietnamese', 'Thai', 'Indonesian',
            'Filipino', 'Malaysian', 'Hawaiian', 'Polynesian', 'Maori', 'Aboriginal',
            'Native American', 'Inuit', 'Andean', 'Amazonian', 'Balkan', 'Greek',
            'Italian', 'Spanish', 'Portuguese', 'French', 'German', 'Austrian',
            'Swiss', 'Dutch', 'Belgian', 'Polish', 'Russian', 'Ukrainian', 'Romanian',
            'Hungarian', 'Czech', 'Bulgarian', 'Serbian', 'Croatian', 'Slovenian',
            'Baltic', 'Estonian', 'Latvian', 'Lithuanian', 'Georgian', 'Armenian',
            'Azerbaijani', 'Mongolian', 'Tibetan', 'Uyghur', 'Kazakh', 'Uzbek'
        ]

        soundtrack_types = [
            'video game', 'movie trailer', 'documentary', 'action film', 'horror movie',
            'fantasy epic', 'sci-fi', 'noir thriller', 'romantic comedy', 'drama',
            'indie film', 'blockbuster', 'art house', 'silent film', 'animated movie',
            'anime', 'TV series', 'streaming show', 'web series', 'podcast intro',
            'YouTube video', 'commercial', 'advertisement', 'corporate video', 'wedding',
            'graduation', 'birthday party', 'New Year', 'Halloween', 'Christmas',
            'fashion show', 'runway', 'art gallery', 'museum exhibit', 'theater play',
            'musical', 'opera', 'ballet', 'contemporary dance', 'circus', 'magic show',
            'sports event', 'boxing match', 'wrestling entrance', 'Olympic ceremony',
            'political rally', 'protest march', 'meditation app', 'sleep app', 'fitness app',
            'RPG', 'JRPG', 'MMORPG', 'first-person shooter', 'battle royale', 'fighting game',
            'racing game', 'sports game', 'simulation', 'strategy game', 'puzzle game',
            'platformer', 'metroidvania', 'roguelike', 'survival horror', 'walking simulator',
            'visual novel', 'rhythm game', 'music game', 'indie game', 'AAA game',
            'mobile game', 'arcade game', 'retro game', 'VR experience', 'AR experience',
            'escape room', 'theme park ride', 'haunted house', 'immersive theater'
        ]

        production_styles = [
            'electronic production', 'live instruments', 'orchestral backing', 'minimal arrangement',
            'full band sound', 'bedroom production', 'studio polish', 'live recording',
            'field recording', 'found sound collage', 'sample-based', 'synthesis-heavy',
            'acoustic purity', 'electric energy', 'hybrid approach', 'layered production',
            'sparse arrangement', 'dense orchestration', 'wall of sound', 'intimate recording',
            'lo-fi aesthetic', 'hi-fi clarity', 'vintage warmth', 'modern crispness',
            'analog character', 'digital precision', 'tape saturation', 'tube warmth',
            'transistor bite', 'transformer color', 'console summing', 'in-the-box mixing',
            'outboard processing', 'hardware synths', 'software instruments', 'sample libraries',
            'live drumming', 'programmed beats', 'drum machine patterns', 'breakbeat sampling',
            'chopped and screwed', 'time-stretched', 'pitch-shifted', 'granular processing',
            'spectral manipulation', 'convolution reverb', 'algorithmic reverb', 'spring reverb',
            'plate reverb', 'room ambience', 'chamber echo', 'tape delay', 'digital delay',
            'analog delay', 'modulated delay', 'reverse reverb', 'gated reverb', 'shimmer reverb'
        ]

        # Many different pattern templates for variety
        patterns = [
            # Pattern 1: mood + genre + instrument
            lambda: f"{random.choice(moods)} {random.choice(genres)} with {random.choice(instruments)}",

            # Pattern 2: era/decade style
            lambda: f"{random.choice(eras)} {random.choice(genres)} {random.choice(['hit', 'track', 'jam', 'groove', 'anthem', 'ballad', 'banger', 'classic', 'deep cut', 'B-side', 'single', 'album track'])}",

            # Pattern 3: scene/setting based
            lambda: f"music for {random.choice(scenes)}",

            # Pattern 4: texture-focused
            lambda: f"{random.choice(['cinematic', 'experimental', 'minimalist', 'maximalist', 'psychedelic', 'progressive', 'neo-classical', 'industrial', 'ethereal', 'tribal', 'ambient', 'noise', 'glitch', 'IDM', 'avant-garde', 'post-modern', 'deconstructed', 'abstract'])} {random.choice(['soundscape', 'composition', 'piece', 'arrangement', 'track', 'journey', 'exploration', 'meditation', 'experience'])} with {random.choice(textures)}",

            # Pattern 5: tempo + feel + genre
            lambda: f"{random.choice(['slow', 'mid-tempo', 'fast', 'uptempo', 'downtempo', 'walking pace', 'racing', 'crawling', 'moderate', 'brisk', 'leisurely', 'frantic', 'relaxed', 'driving', 'pulsing', 'steady', 'shifting', 'accelerating', 'decelerating'])} {random.choice(['and groovy', 'and punchy', 'and smooth', 'and aggressive', 'and gentle', 'and hypnotic', 'and bouncy', 'and heavy', 'and light', 'and tight', 'and loose', 'and swinging', 'and straight', 'and syncopated', 'and polyrhythmic'])} {random.choice(['beats', 'rhythm', 'groove', 'pulse', 'flow', 'vibe', 'energy', 'momentum'])} with {random.choice(genres)} influences",

            # Pattern 6: instrument-focused
            lambda: f"{random.choice(['solo', 'duet', 'trio', 'quartet', 'quintet', 'ensemble', 'orchestra', 'band', 'group'])} {random.choice(instruments)} {random.choice(['performance', 'improvisation', 'piece', 'melody', 'solo', 'concerto', 'sonata', 'etude', 'prelude', 'nocturne', 'rhapsody', 'fantasia', 'variations'])} in {random.choice(['major key', 'minor key', 'jazz style', 'classical style', 'blues style', 'modal style', 'chromatic style', 'pentatonic scale', 'whole tone scale', 'diminished scale', 'Dorian mode', 'Mixolydian mode', 'Phrygian mode', 'Lydian mode'])}",

            # Pattern 7: texture + atmosphere
            lambda: f"{random.choice(['lush', 'sparse', 'dense', 'airy', 'warm', 'cold', 'bright', 'dark', 'thick', 'thin', 'wide', 'narrow', 'deep', 'shallow', 'rich', 'minimal', 'complex', 'simple', 'layered', 'stripped'])} {random.choice(['textures', 'layers', 'sounds', 'tones', 'harmonies', 'frequencies', 'spectrums', 'palettes', 'colors', 'shades'])} with {random.choice(['reverb-drenched', 'dry', 'lo-fi', 'pristine', 'distorted', 'filtered', 'compressed', 'expanded', 'saturated', 'clean', 'dirty', 'processed', 'natural', 'artificial', 'organic', 'synthetic'])} {random.choice(instruments)}",

            # Pattern 8: world music fusion
            lambda: f"{random.choice(world_regions)} {random.choice(['rhythms', 'melodies', 'influences', 'vibes', 'scales', 'modes', 'instruments', 'percussion', 'vocals', 'harmonies', 'traditions', 'folk songs', 'dance music'])} fused with {random.choice(['electronic beats', 'jazz harmonies', 'orchestral swells', 'rock energy', 'ambient textures', 'hip-hop production', 'pop sensibility', 'classical structure', 'minimalist approach', 'maximalist production'])}",

            # Pattern 9: soundtrack style
            lambda: f"{random.choice(soundtrack_types)} {random.choice(['soundtrack', 'score', 'theme', 'background music', 'underscore', 'cue', 'motif', 'leitmotif'])} - {random.choice(['tense', 'heroic', 'mysterious', 'emotional', 'exciting', 'peaceful', 'ominous', 'triumphant', 'melancholic', 'whimsical', 'dark', 'light', 'epic', 'intimate', 'action-packed', 'contemplative', 'suspenseful', 'romantic', 'comedic', 'dramatic'])}",

            # Pattern 10: production style
            lambda: f"{random.choice(['catchy', 'memorable', 'infectious', 'hypnotic', 'powerful', 'delicate', 'raw', 'polished', 'experimental', 'accessible', 'challenging', 'rewarding', 'immediate', 'grower', 'timeless', 'contemporary', 'classic', 'fresh', 'innovative', 'traditional'])} {random.choice(['melody', 'hook', 'riff', 'groove', 'beat', 'bassline', 'chord progression', 'breakdown', 'drop', 'build-up', 'climax', 'outro', 'intro', 'verse', 'chorus', 'bridge'])} with {random.choice(production_styles)}",

            # Pattern 11: mood combination
            lambda: f"{random.choice(moods)} yet {random.choice(moods)} {random.choice(genres)}",

            # Pattern 12: contrasting elements
            lambda: f"{random.choice(['heavy', 'light', 'fast', 'slow', 'loud', 'quiet', 'complex', 'simple', 'old', 'new', 'Eastern', 'Western'])} meets {random.choice(['heavy', 'light', 'fast', 'slow', 'loud', 'quiet', 'complex', 'simple', 'old', 'new', 'Eastern', 'Western'])} {random.choice(genres)}",

            # Pattern 13: specific BPM range
            lambda: f"{random.choice(['60-80 BPM', '80-100 BPM', '100-120 BPM', '120-140 BPM', '140-160 BPM', '160-180 BPM', '180+ BPM'])} {random.choice(genres)} with {random.choice(moods)} energy",

            # Pattern 14: time signature focus
            lambda: f"{random.choice(['4/4', '3/4', '6/8', '5/4', '7/8', '12/8', 'odd time', 'polyrhythmic', 'shifting meter'])} {random.choice(genres)} {random.choice(['groove', 'beat', 'rhythm', 'feel'])}",

            # Pattern 15: key/scale focus
            lambda: f"{random.choice(genres)} in {random.choice(['C major', 'A minor', 'G major', 'E minor', 'D major', 'B minor', 'F major', 'D minor', 'Bb major', 'G minor', 'Eb major', 'C minor', 'Ab major', 'F minor', 'Db major', 'Bb minor', 'F# major', 'D# minor'])} with {random.choice(moods)} mood",

            # Pattern 16: band/ensemble type
            lambda: f"{random.choice(['power trio', 'four-piece band', 'five-piece band', 'big band', 'chamber ensemble', 'string quartet', 'brass quintet', 'jazz combo', 'rock band', 'electronic duo', 'solo artist', 'supergroup', 'session musicians', 'house band', 'backing band'])} playing {random.choice(moods)} {random.choice(genres)}",

            # Pattern 17: recording style
            lambda: f"{random.choice(['live in the studio', 'bedroom recorded', 'professionally produced', 'DIY aesthetic', 'one-take wonder', 'meticulously crafted', 'spontaneously captured', 'heavily layered', 'stripped down', 'audiophile quality', 'lo-fi charm', 'cassette tape warmth', 'vinyl-ready', 'radio-friendly', 'underground sound'])} {random.choice(genres)}",

            # Pattern 18: emotional journey
            lambda: f"{random.choice(genres)} that goes from {random.choice(moods)} to {random.choice(moods)}",

            # Pattern 19: specific instrument feature
            lambda: f"{random.choice(instruments)}-driven {random.choice(genres)} with {random.choice(moods)} atmosphere",

            # Pattern 20: hybrid genre
            lambda: f"{random.choice(genres)}-{random.choice(genres)} fusion with {random.choice(textures)}"
        ]

        prompt = random.choice(patterns)()

    else:
        # Extensive sound effect vocabulary
        environments = [
            'forest', 'city street', 'beach', 'factory', 'office', 'home', 'cave', 'spaceship',
            'underwater', 'stadium', 'church', 'hospital', 'school', 'library', 'museum',
            'airport', 'train station', 'bus station', 'subway', 'parking garage', 'warehouse',
            'construction site', 'farm', 'jungle', 'desert', 'mountain', 'valley', 'canyon',
            'river', 'lake', 'ocean', 'swamp', 'tundra', 'arctic', 'volcano', 'island',
            'castle', 'dungeon', 'tower', 'fortress', 'palace', 'mansion', 'cottage', 'cabin',
            'apartment', 'penthouse', 'basement', 'attic', 'garage', 'shed', 'barn', 'stable',
            'greenhouse', 'garden', 'park', 'playground', 'cemetery', 'marketplace', 'bazaar',
            'mall', 'supermarket', 'convenience store', 'restaurant', 'cafe', 'bar', 'club',
            'theater', 'cinema', 'concert hall', 'opera house', 'arena', 'colosseum',
            'courtroom', 'prison', 'police station', 'fire station', 'military base', 'bunker',
            'laboratory', 'observatory', 'planetarium', 'aquarium', 'zoo', 'circus',
            'amusement park', 'carnival', 'fair', 'festival', 'wedding venue', 'funeral home',
            'spa', 'gym', 'dojo', 'boxing ring', 'wrestling arena', 'ice rink', 'ski resort',
            'golf course', 'tennis court', 'basketball court', 'football field', 'baseball diamond',
            'race track', 'drag strip', 'motocross track', 'skate park', 'BMX track',
            'harbor', 'dock', 'pier', 'marina', 'lighthouse', 'oil rig', 'submarine',
            'aircraft carrier', 'cruise ship', 'ferry', 'yacht', 'rowboat', 'canoe', 'kayak',
            'helicopter', 'airplane cabin', 'cockpit', 'control tower', 'hangar',
            'space station', 'moon base', 'Mars colony', 'alien world', 'asteroid',
            'wormhole', 'black hole vicinity', 'nebula', 'dying star', 'cosmic void'
        ]

        sound_sources = [
            'footsteps', 'doors', 'machinery', 'vehicles', 'animals', 'weather', 'water', 'fire',
            'crowd', 'nature', 'electronics', 'appliances', 'tools', 'weapons', 'instruments',
            'voices', 'breathing', 'heartbeat', 'bones cracking', 'joints popping', 'muscles stretching',
            'fabric rustling', 'leather creaking', 'metal clanging', 'wood creaking', 'glass breaking',
            'plastic crinkling', 'paper shuffling', 'cardboard folding', 'tape peeling', 'velcro ripping',
            'zipper opening', 'buttons clicking', 'snaps fastening', 'buckles clinking', 'chains rattling',
            'keys jingling', 'coins dropping', 'dice rolling', 'cards shuffling', 'chips stacking',
            'pencil writing', 'pen clicking', 'marker squeaking', 'chalk scraping', 'eraser rubbing',
            'keyboard typing', 'mouse clicking', 'touchscreen tapping', 'phone vibrating', 'notification chimes',
            'dial-up modem', 'fax machine', 'printer printing', 'scanner scanning', 'copier copying',
            'coffee maker brewing', 'microwave beeping', 'oven timer', 'toaster popping', 'blender whirring',
            'dishwasher running', 'washing machine spinning', 'dryer tumbling', 'vacuum cleaning',
            'air conditioner humming', 'heater clicking', 'fan oscillating', 'refrigerator buzzing',
            'ice maker dropping', 'water dispenser', 'garbage disposal', 'toilet flushing', 'shower running',
            'bathtub filling', 'sink draining', 'faucet dripping', 'pipes clanking', 'radiator hissing',
            'elevator moving', 'escalator running', 'automatic doors', 'revolving doors', 'garage doors',
            'car starting', 'engine revving', 'tires screeching', 'brakes squealing', 'horn honking',
            'turn signal clicking', 'windshield wipers', 'car door closing', 'trunk slamming', 'seatbelt clicking',
            'motorcycle rumbling', 'bicycle bell', 'skateboard rolling', 'roller skates', 'scooter buzzing',
            'bus hydraulics', 'train wheels', 'subway doors', 'airplane engines', 'helicopter blades',
            'boat motor', 'ship horn', 'anchor dropping', 'sails flapping', 'oars splashing',
            'horse hooves', 'carriage wheels', 'wagon creaking', 'sleigh bells', 'whip cracking',
            'sword unsheathing', 'arrow flying', 'bowstring twanging', 'shield blocking', 'armor clanking',
            'gun cocking', 'bullet firing', 'shell casing', 'reload clicking', 'silencer shot',
            'explosion', 'grenade pin', 'detonator beeping', 'fuse burning', 'dynamite blast',
            'laser beam', 'plasma shot', 'energy charge', 'force field', 'teleporter',
            'magic spell', 'potion bubbling', 'crystal humming', 'enchantment shimmer', 'curse whisper'
        ]

        modifiers = [
            'heavy', 'light', 'distant', 'close', 'echoing', 'muffled', 'sharp', 'soft',
            'loud', 'quiet', 'constant', 'intermittent', 'rhythmic', 'random', 'patterned', 'chaotic',
            'fast', 'slow', 'accelerating', 'decelerating', 'steady', 'fluctuating', 'pulsing', 'throbbing',
            'high-pitched', 'low-pitched', 'mid-range', 'full-spectrum', 'filtered', 'clean', 'distorted', 'processed',
            'natural', 'artificial', 'organic', 'synthetic', 'realistic', 'stylized', 'exaggerated', 'subtle',
            'wet', 'dry', 'reverberant', 'dead', 'spacious', 'intimate', 'cavernous', 'enclosed',
            'metallic', 'wooden', 'plastic', 'glass', 'stone', 'concrete', 'fabric', 'leather',
            'hollow', 'solid', 'dense', 'sparse', 'thick', 'thin', 'rough', 'smooth',
            'creaky', 'squeaky', 'crunchy', 'squishy', 'snappy', 'wobbly', 'rattling', 'buzzing',
            'humming', 'droning', 'whirring', 'clicking', 'ticking', 'beeping', 'chirping', 'whistling',
            'howling', 'roaring', 'growling', 'hissing', 'sizzling', 'crackling', 'popping', 'bubbling',
            'splashing', 'dripping', 'flowing', 'rushing', 'crashing', 'thundering', 'rumbling', 'booming',
            'eerie', 'peaceful', 'tense', 'relaxing', 'unsettling', 'comforting', 'alien', 'familiar'
        ]

        actions = [
            'ambient sounds', 'footsteps walking', 'machinery humming', 'wind blowing', 'crowd murmuring',
            'birds chirping', 'rain falling', 'fire crackling', 'water dripping', 'door creaking',
            'clock ticking', 'keyboard typing', 'engine running', 'phone ringing', 'alarm sounding',
            'glass shattering', 'metal scraping', 'wood splintering', 'fabric tearing', 'paper crumpling',
            'liquid pouring', 'gas hissing', 'steam releasing', 'ice cracking', 'snow crunching',
            'leaves rustling', 'branches snapping', 'trees falling', 'rocks tumbling', 'sand shifting',
            'waves crashing', 'river flowing', 'waterfall roaring', 'bubbles rising', 'fish splashing',
            'insects buzzing', 'bees swarming', 'flies hovering', 'mosquitoes whining', 'crickets chirping',
            'frogs croaking', 'owls hooting', 'wolves howling', 'dogs barking', 'cats meowing',
            'horses neighing', 'cows mooing', 'pigs oinking', 'chickens clucking', 'roosters crowing',
            'lions roaring', 'elephants trumpeting', 'monkeys chattering', 'birds flocking', 'bats screeching',
            'whales singing', 'dolphins clicking', 'seals barking', 'penguins squawking', 'seagulls calling',
            'people talking', 'children playing', 'babies crying', 'crowds cheering', 'audiences applauding',
            'protesters chanting', 'monks chanting', 'choir singing', 'orchestra tuning', 'band practicing',
            'construction working', 'demolition destroying', 'drilling penetrating', 'hammering nailing', 'sawing cutting',
            'welding sparking', 'grinding smoothing', 'polishing buffing', 'painting spraying', 'cleaning scrubbing',
            'cooking sizzling', 'baking timer', 'chopping vegetables', 'boiling water', 'frying food',
            'eating crunching', 'drinking gulping', 'swallowing', 'chewing', 'slurping',
            'sports playing', 'balls bouncing', 'bats hitting', 'rackets swinging', 'goals scoring',
            'fighting punching', 'kicking striking', 'blocking defending', 'falling tumbling', 'landing impacting',
            'magic casting', 'spells activating', 'potions brewing', 'transformations occurring', 'teleportation happening',
            'sci-fi technology', 'robots moving', 'AI processing', 'holograms projecting', 'forcefields activating',
            'spaceship launching', 'warp drives engaging', 'lasers firing', 'shields deflecting', 'systems failing'
        ]

        time_contexts = [
            'at dawn', 'at sunrise', 'in the morning', 'at noon', 'in the afternoon',
            'at sunset', 'at dusk', 'in the evening', 'at night', 'at midnight',
            'in spring', 'in summer', 'in autumn', 'in winter', 'during a storm',
            'after the rain', 'during a heatwave', 'during a cold snap', 'during a drought',
            'during rush hour', 'late at night', 'early morning', 'weekend afternoon',
            'holiday celebration', 'during a blackout', 'in an emergency', 'in peacetime',
            'during wartime', 'in the distant past', 'in the near future', 'in another dimension'
        ]

        # Many different sound effect patterns
        patterns = [
            # Pattern 1: action in environment
            lambda: f"{random.choice(sound_sources)} sounds in {random.choice(environments)}",

            # Pattern 2: modified specific sound
            lambda: f"{random.choice(modifiers)} {random.choice(sound_sources)}",

            # Pattern 3: ambient scene
            lambda: f"{random.choice(['busy', 'quiet', 'peaceful', 'chaotic', 'eerie', 'lively', 'abandoned', 'crowded', 'empty', 'haunted', 'serene', 'tense', 'relaxing', 'oppressive', 'welcoming'])} {random.choice(environments)} ambience",

            # Pattern 4: mechanical/tech
            lambda: f"{random.choice(['old', 'modern', 'futuristic', 'broken', 'powerful', 'delicate', 'massive', 'tiny', 'ancient', 'prototype', 'industrial', 'consumer', 'military', 'medical', 'scientific'])} {random.choice(['machine', 'engine', 'motor', 'robot', 'computer', 'generator', 'fan', 'printer', 'device', 'gadget', 'mechanism', 'apparatus', 'contraption', 'system'])} {random.choice(['starting up', 'running', 'shutting down', 'malfunctioning', 'idling', 'overheating', 'cooling down', 'processing', 'computing', 'activating', 'deactivating', 'calibrating', 'self-destructing'])}",

            # Pattern 5: nature sounds with time
            lambda: f"{random.choice(['birds', 'insects', 'frogs', 'wolves', 'owls', 'whales', 'dolphins', 'cicadas', 'crickets', 'coyotes', 'crows', 'eagles', 'hawks', 'songbirds', 'seabirds'])} {random.choice(['calling', 'singing', 'howling', 'chirping', 'croaking', 'clicking', 'screeching', 'cooing', 'cawing', 'tweeting', 'warbling', 'trilling'])} {random.choice(time_contexts)}",

            # Pattern 6: human activities in location
            lambda: f"{random.choice(['people', 'crowd', 'children', 'workers', 'athletes', 'musicians', 'actors', 'students', 'soldiers', 'monks', 'protesters', 'shoppers', 'tourists', 'commuters'])} {random.choice(['talking', 'laughing', 'arguing', 'cheering', 'working', 'playing', 'singing', 'praying', 'marching', 'dancing', 'fighting', 'celebrating', 'mourning', 'meditating'])} in {random.choice(environments)}",

            # Pattern 7: weather with detail
            lambda: f"{random.choice(['gentle', 'heavy', 'violent', 'steady', 'intermittent', 'approaching', 'receding', 'sudden', 'prolonged', 'tropical', 'arctic', 'desert'])} {random.choice(['rain', 'snow', 'hail', 'wind', 'storm', 'thunderstorm', 'blizzard', 'hurricane', 'tornado', 'sandstorm', 'fog', 'mist', 'drizzle', 'downpour', 'squall'])} with {random.choice(['thunder', 'lightning', 'wind gusts', 'calm moments', 'hail impacts', 'flooding sounds', 'tree branches breaking', 'debris flying', 'sirens wailing', 'people running'])}",

            # Pattern 8: sci-fi/fantasy
            lambda: f"{random.choice(['alien', 'magical', 'robotic', 'supernatural', 'dimensional', 'cosmic', 'ethereal', 'demonic', 'angelic', 'eldritch', 'cybernetic', 'biomechanical', 'quantum', 'interdimensional'])} {random.choice(['creature', 'machine', 'portal', 'weapon', 'vehicle', 'entity', 'artifact', 'phenomenon', 'anomaly', 'construct', 'being', 'force', 'energy'])} {random.choice(['activating', 'moving', 'attacking', 'transforming', 'appearing', 'disappearing', 'communicating', 'feeding', 'hibernating', 'evolving', 'dying', 'being born', 'phasing', 'materializing'])}",

            # Pattern 9: vehicle sounds
            lambda: f"{random.choice(['vintage', 'modern', 'futuristic', 'military', 'civilian', 'racing', 'heavy-duty', 'electric', 'hybrid', 'diesel', 'jet-powered', 'rocket-powered'])} {random.choice(['car', 'truck', 'motorcycle', 'bus', 'train', 'airplane', 'helicopter', 'boat', 'ship', 'submarine', 'spacecraft', 'hovercraft', 'tank', 'ATV', 'snowmobile'])} {random.choice(['starting', 'idling', 'accelerating', 'cruising', 'braking', 'crashing', 'exploding', 'landing', 'taking off', 'docking', 'racing', 'drifting'])}",

            # Pattern 10: household sounds
            lambda: f"{random.choice(['kitchen', 'bathroom', 'bedroom', 'living room', 'basement', 'attic', 'garage', 'laundry room', 'home office', 'nursery', 'dining room', 'hallway'])} sounds: {random.choice(actions)}",

            # Pattern 11: industrial sounds
            lambda: f"{random.choice(['factory', 'warehouse', 'shipyard', 'mine', 'foundry', 'refinery', 'power plant', 'processing facility', 'assembly line', 'loading dock'])} {random.choice(['machinery', 'equipment', 'tools', 'vehicles', 'workers', 'alarms', 'ventilation', 'conveyors', 'presses', 'furnaces'])} {random.choice(time_contexts)}",

            # Pattern 12: combat/action sounds
            lambda: f"{random.choice(['medieval', 'modern', 'futuristic', 'fantasy', 'sci-fi', 'steampunk', 'cyberpunk', 'post-apocalyptic'])} {random.choice(['battle', 'skirmish', 'duel', 'siege', 'raid', 'ambush', 'standoff', 'chase', 'escape', 'infiltration'])} with {random.choice(['swords clashing', 'guns firing', 'explosions', 'energy weapons', 'magic spells', 'hand-to-hand combat', 'vehicle warfare', 'aerial combat', 'naval battle'])}",

            # Pattern 13: horror/suspense
            lambda: f"{random.choice(['creepy', 'terrifying', 'unsettling', 'ominous', 'dreadful', 'spine-chilling', 'blood-curdling', 'nightmare', 'paranormal', 'demonic'])} {random.choice(['whispers', 'footsteps', 'breathing', 'scratching', 'knocking', 'screaming', 'laughing', 'crying', 'growling', 'chittering', 'slithering', 'dripping'])} in {random.choice(['haunted house', 'abandoned asylum', 'dark forest', 'underground tunnel', 'ancient tomb', 'cursed mansion', 'foggy cemetery', 'derelict ship', 'forgotten basement'])}",

            # Pattern 14: UI/interface sounds
            lambda: f"{random.choice(['futuristic', 'retro', 'minimal', 'playful', 'professional', 'gaming', 'mobile', 'desktop', 'holographic', 'neural'])} {random.choice(['interface', 'menu', 'notification', 'alert', 'confirmation', 'error', 'loading', 'transition', 'selection', 'activation'])} {random.choice(['beep', 'chime', 'click', 'swoosh', 'ping', 'blip', 'tone', 'jingle', 'whoosh', 'zap'])}",

            # Pattern 15: sports/recreation
            lambda: f"{random.choice(['basketball', 'football', 'soccer', 'baseball', 'tennis', 'golf', 'hockey', 'swimming', 'boxing', 'wrestling', 'skiing', 'skateboarding', 'surfing', 'cycling', 'running'])} {random.choice(['game', 'match', 'practice', 'training', 'competition', 'tournament', 'championship'])} sounds with {random.choice(['crowd cheering', 'referee whistles', 'equipment sounds', 'athlete exertion', 'commentator announcing', 'music playing'])}",

            # Pattern 16: food/cooking
            lambda: f"{random.choice(['sizzling', 'boiling', 'frying', 'baking', 'grilling', 'chopping', 'mixing', 'blending', 'pouring', 'plating'])} {random.choice(['steak', 'vegetables', 'eggs', 'pasta', 'soup', 'sauce', 'bread', 'cake', 'cocktail', 'coffee'])} in a {random.choice(['home kitchen', 'restaurant kitchen', 'food truck', 'outdoor grill', 'campfire', 'professional bakery', 'sushi bar', 'pizzeria', 'food market'])}",

            # Pattern 17: construction/destruction
            lambda: f"{random.choice(['building', 'demolishing', 'renovating', 'repairing', 'installing', 'removing', 'constructing', 'deconstructing'])} with {random.choice(['hammers', 'drills', 'saws', 'cranes', 'bulldozers', 'excavators', 'jackhammers', 'welding equipment', 'concrete mixers', 'pile drivers'])}",

            # Pattern 18: communication sounds
            lambda: f"{random.choice(['vintage', 'modern', 'futuristic', 'emergency', 'military', 'space'])} {random.choice(['phone', 'radio', 'intercom', 'PA system', 'walkie-talkie', 'communicator', 'transmitter', 'beacon'])} {random.choice(['ringing', 'static', 'dial tone', 'busy signal', 'voicemail', 'text notification', 'call connecting', 'signal lost', 'transmission received'])}"
        ]

        prompt = random.choice(patterns)()

    return jsonify({'success': True, 'prompt': prompt})


# ========================================
# SERVICE DISCOVERY ENDPOINTS
# ========================================

@app.route('/api/manifest')
def api_manifest():
    """Universal service discovery manifest. This is the hub that all
    discovery mechanisms (mDNS, agent cards, etc.) point to."""
    import socket
    host = request.host  # includes port
    base = request.url_root.rstrip('/')

    gpu_info = get_gpu_info()
    stats = db.get_stats()

    return jsonify({
        'name': 'Sound Box',
        'description': 'AI audio generation server - music, sound effects, and speech from text prompts',
        'version': '1.0.0',
        'base_url': base,
        'capabilities': ['music_generation', 'sfx_generation', 'speech_synthesis',
                         'audio_library', 'radio_streaming', 'playlists'],
        'models': {
            'music': loading_status.get('music', 'unknown'),
            'audio': loading_status.get('audio', 'unknown'),
            'magnet-music': loading_status.get('magnet-music', 'unknown'),
            'magnet-audio': loading_status.get('magnet-audio', 'unknown'),
        },
        'gpu': {
            'available': gpu_info.get('available', False),
        },
        'library': {
            'total_tracks': stats.get('total_generations', 0),
            'total_music': stats.get('total_music', 0),
            'total_sfx': stats.get('total_audio', 0),
        },
        'auth': {
            'open_access': OPEN_ACCESS_MODE,
            'method': 'anonymous_ip' if OPEN_ACCESS_MODE else 'bearer_token',
        },
        'rate_limits': {
            'free_tier': '10 generations/hour, 60s max duration',
            'creator_tier': '60 generations/hour, 180s max duration (whitelisted IPs)',
        },
        'endpoints': {
            'generate': {'method': 'POST', 'path': '/generate'},
            'job_status': {'method': 'GET', 'path': '/job/{job_id}'},
            'system_status': {'method': 'GET', 'path': '/status'},
            'library': {'method': 'GET', 'path': '/api/library'},
            'track': {'method': 'GET', 'path': '/api/library/{gen_id}'},
            'radio_shuffle': {'method': 'GET', 'path': '/api/radio/shuffle'},
            'audio_stream': {'method': 'GET', 'path': '/audio/{filename}'},
            'audio_download': {'method': 'GET', 'path': '/download/{filename}'},
            'stats': {'method': 'GET', 'path': '/api/stats'},
            'random_prompt': {'method': 'POST', 'path': '/random-prompt'},
            'vote': {'method': 'POST', 'path': '/api/library/{gen_id}/vote'},
            'favorite': {'method': 'POST', 'path': '/api/favorites/{gen_id}'},
        },
        'discovery': {
            'manifest': '/api/manifest',
            'agent_card': '/.well-known/agent-card.json',
            'openapi': '/openapi.json',
        },
    })


@app.route('/.well-known/agent-card.json')
def agent_card():
    """A2A agent discovery card (Google Agent-to-Agent protocol)."""
    base = request.url_root.rstrip('/')
    return jsonify({
        'name': 'Sound Box',
        'description': 'AI audio generation server. Generate music, sound effects, and speech from text prompts using Meta AudioCraft models.',
        'url': base,
        'version': '1.0.0',
        'capabilities': {
            'streaming': False,
            'pushNotifications': False,
        },
        'skills': [
            {
                'id': 'generate-music',
                'name': 'Generate Music',
                'description': 'Generate music from a text prompt using MusicGen',
                'examples': ['upbeat electronic music with synth pads', 'calm piano melody in C major'],
                'endpoint': {'method': 'POST', 'path': '/generate'},
            },
            {
                'id': 'generate-sfx',
                'name': 'Generate Sound Effects',
                'description': 'Generate sound effects from a text prompt using AudioGen',
                'examples': ['thunder rolling across a mountain valley', 'spaceship engine humming'],
                'endpoint': {'method': 'POST', 'path': '/generate'},
            },
            {
                'id': 'search-library',
                'name': 'Search Audio Library',
                'description': 'Search and browse the library of generated audio tracks',
                'examples': ['search for ambient music', 'find rain sound effects'],
                'endpoint': {'method': 'GET', 'path': '/api/library'},
            },
            {
                'id': 'check-status',
                'name': 'Check System Status',
                'description': 'Get GPU status, model loading state, and queue length',
                'endpoint': {'method': 'GET', 'path': '/status'},
            },
            {
                'id': 'get-radio-track',
                'name': 'Get Radio Track',
                'description': 'Get random or curated tracks for listening',
                'endpoint': {'method': 'GET', 'path': '/api/radio/shuffle'},
            },
        ],
        'openapi': f'{base}/openapi.json',
        'manifest': f'{base}/api/manifest',
    })


@app.route('/openapi.json')
def openapi_spec():
    """Serve the OpenAPI 3.1 specification."""
    return send_file('static/openapi.json', mimetype='application/json')


# ========================================
# WIDGET EMBED ENDPOINTS
# ========================================

@app.route('/widget/graphlings-radio.js')
def widget_js():
    """Serve the embeddable widget JavaScript with CORS headers."""
    response = send_file('static/dist/graphlings-radio.js', mimetype='application/javascript')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    return response


@app.route('/widget/graphlings-radio.css')
def widget_css():
    """Serve the embeddable widget CSS with CORS headers."""
    response = send_file('static/dist/graphlings-radio.css', mimetype='text/css')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    return response


@app.route('/api/radio')
@optional_auth
def api_radio():
    """Universal radio API endpoint for widget and internal use."""
    station = request.args.get('station', 'shuffle')
    limit = safe_int(request.args.get('limit', 10), default=10, min_val=1, max_val=50)
    model = request.args.get('model', 'music')

    # Map station names to search queries
    station_searches = {
        'ambient': 'ambient OR soundscape OR atmospheric',
        'lofi': 'lo-fi OR chill beats OR relaxed',
        'retro': 'chiptune OR 8-bit OR retro',
        'piano': 'piano OR keyboard OR gentle',
        'happy': 'happy OR upbeat OR bouncy',
        'dreamy': 'dreamy OR ethereal OR atmospheric'
    }

    # Get tracks based on station type
    if station == 'favorites':
        # SECURITY: Only allow authenticated users to access their own favorites
        # Prevents enumeration of other users' favorites via user_id parameter
        if request.user_id:
            tracks = db.get_random_favorites(request.user_id, count=limit, model=model)
        else:
            tracks = []  # Not authenticated - return empty
    elif station == 'trending':
        tracks = db.get_trending_tracks(limit=limit, model=model)
    elif station == 'top-rated':
        tracks = db.get_top_rated_tracks(model=model, count=limit)
    elif station == 'new':
        tracks = db.get_recent_tracks(model=model, count=limit)
    elif station in station_searches:
        # Search-based stations
        tracks = db.get_random_tracks(
            model=model,
            search=station_searches[station],
            count=limit
        )
    else:
        # Default shuffle - random tracks
        tracks = db.get_random_tracks(model=model, count=limit)

    # Add CORS headers for external widget use
    response = jsonify({
        'station': station,
        'queue': tracks
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


if __name__ == '__main__':
    # Server configuration from environment variables
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5309))
    DEBUG = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')

    # Initialize database and migrate from JSON if needed
    db.init_db()
    db.migrate_from_json()
    db.migrate_categories()  # Categorize any uncategorized generations

    # Start model loader thread
    loader_thread = threading.Thread(target=load_models, daemon=True)
    loader_thread.start()

    # Start queue worker thread
    worker_thread = threading.Thread(target=process_queue, daemon=True)
    worker_thread.start()

    # Start backup scheduler if BACKUP_DIR is configured
    if os.environ.get('BACKUP_DIR'):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler = BackgroundScheduler()
            backup_time = os.environ.get('BACKUP_TIME', '03:00')
            hour, minute = map(int, backup_time.split(':'))
            scheduler.add_job(backup.run_backup, 'cron', hour=hour, minute=minute)
            scheduler.start()
            print(f"Backup scheduler started - daily at {backup_time}")
        except ImportError:
            print("Warning: APScheduler not installed, backups disabled")
            print("Install with: pip install apscheduler")

    print("Starting server... Models loading in background.")
    print(f"Access at http://{HOST if HOST != '0.0.0.0' else 'localhost'}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
