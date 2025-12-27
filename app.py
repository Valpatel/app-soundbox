"""
Sound Box - AI Audio Generation Server

Flask server that generates music and sound effects from text prompts
using Meta's AudioCraft models (MusicGen/AudioGen). Features priority
queue processing, quality analysis with auto-retry, and spectrogram
visualization.

See docs/ARCHITECTURE.md for system overview.
"""
import os
import uuid
import json
import threading
import queue
import time
from datetime import datetime
import torch
import numpy as np
import librosa
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, jsonify, send_file
from audiocraft.models import MusicGen, AudioGen, MAGNeT
from audiocraft.data.audio import audio_write
import database as db

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
        return {'score': 75, 'issues': [], 'is_good': True}  # Assume good if analysis fails


# Priority levels (lower = higher priority)
PRIORITY_LEVELS = {
    'admin': 0,
    'premium': 1,
    'standard': 2,
    'free': 3
}

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_FILE, 'w') as f:
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

# Model state
models = {}
loading_status = {
    'music': 'pending',
    'audio': 'pending',
    'magnet-music': 'pending',
    'magnet-audio': 'pending'
}

# Queue and job tracking
job_queue = queue.PriorityQueue()
jobs = {}  # job_id -> job info
current_job = None
queue_lock = threading.Lock()


def get_gpu_info():
    """Get GPU utilization info."""
    if not torch.cuda.is_available():
        return {'available': False}

    try:
        gpu_mem_used = torch.cuda.memory_allocated() / 1024**3
        gpu_mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        gpu_mem_percent = (gpu_mem_used / gpu_mem_total) * 100

        return {
            'available': True,
            'name': torch.cuda.get_device_name(0),
            'memory_used_gb': round(gpu_mem_used, 2),
            'memory_total_gb': round(gpu_mem_total, 2),
            'memory_percent': round(gpu_mem_percent, 1),
            'busy': current_job is not None
        }
    except Exception as e:
        return {'available': True, 'error': str(e)}


def process_queue():
    """Worker thread that processes generation jobs."""
    global current_job

    while True:
        try:
            # Get next job (blocks until one is available)
            priority, timestamp, job_id = job_queue.get()

            with queue_lock:
                if job_id not in jobs:
                    continue
                job = jobs[job_id]
                job['status'] = 'processing'
                job['started'] = datetime.now().isoformat()
                current_job = job_id

            try:
                model_type = job['model']
                m = models.get(model_type)

                if m is None:
                    job['status'] = 'failed'
                    job['error'] = 'Model not available'
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
                def update_progress():
                    while job.get('status') == 'processing' and job.get('progress_pct', 0) < 95:
                        elapsed = time.time() - job['gen_start']
                        pct = min(95, int((elapsed / estimated_time) * 100))
                        job['progress_pct'] = pct
                        job['progress'] = f'Generating {gen_label}... {pct}%'
                        time.sleep(0.3)

                progress_thread = threading.Thread(target=update_progress, daemon=True)
                progress_thread.start()

                m.set_generation_params(duration=job['duration'])
                wav = m.generate([job['prompt']])

                job['progress_pct'] = 100

                audio_out = wav[0]
                if job.get('loop'):
                    job['progress'] = 'Applying loop crossfade...'
                    audio_out = make_loopable(audio_out, m.sample_rate)

                job['progress'] = 'Saving file...'
                # Note: audio_write automatically adds the extension
                filepath_base = os.path.join(OUTPUT_DIR, job_id)
                audio_write(filepath_base, audio_out.cpu(), m.sample_rate, strategy="loudness")
                filename = f"{job_id}.wav"  # This is the actual filename created
                filepath = os.path.join(OUTPUT_DIR, filename)

                # Analyze quality
                job['progress'] = 'Analyzing quality...'
                quality = analyze_audio_quality(filepath, m.sample_rate)

                # Generate spectrogram
                job['progress'] = 'Generating spectrogram...'
                spec_filename = f"{job_id}.png"
                spec_path = os.path.join(SPECTROGRAMS_DIR, spec_filename)
                generate_spectrogram(filepath, spec_path)

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

                # Also save to SQLite database
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
                        user_id=job.get('user_id')
                    )
                except Exception as e:
                    print(f"[DB] Failed to save generation: {e}")

                job['status'] = 'completed'
                job['filename'] = filename
                job['spectrogram'] = spec_filename
                job['quality'] = quality
                job['progress'] = 'Done!'

                # Auto-regenerate if quality is bad (max 2 retries)
                if not quality['is_good'] and job.get('retry_count', 0) < 2:
                    job['progress'] = f"Low quality detected (score: {quality['score']}), regenerating..."
                    job['retry_count'] = job.get('retry_count', 0) + 1
                    # Re-queue the job
                    job['status'] = 'queued'
                    job_queue.put((PRIORITY_LEVELS.get(job.get('priority', 'standard'), 2),
                                   time.time(), job_id))

            except Exception as e:
                job['status'] = 'failed'
                job['error'] = str(e)

            finally:
                with queue_lock:
                    current_job = None
                job_queue.task_done()

        except Exception as e:
            print(f"Queue worker error: {e}")
            time.sleep(1)


def load_models():
    """Preload both models on startup."""
    global models, loading_status
    import sys

    print("Loading MusicGen model...", flush=True)
    loading_status['music'] = 'loading'
    try:
        models['music'] = MusicGen.get_pretrained('facebook/musicgen-small')
        loading_status['music'] = 'ready'
        print("MusicGen loaded!", flush=True)
    except Exception as e:
        loading_status['music'] = f'error: {e}'
        print(f"MusicGen failed: {e}", flush=True)

    print("Loading AudioGen model...", flush=True)
    loading_status['audio'] = 'loading'
    try:
        models['audio'] = AudioGen.get_pretrained('facebook/audiogen-medium')
        loading_status['audio'] = 'ready'
        print("AudioGen loaded!", flush=True)
    except Exception as e:
        import traceback
        loading_status['audio'] = f'error: {e}'
        print(f"AudioGen failed: {e}", flush=True)
        traceback.print_exc()

    print("All models loaded!", flush=True)


def get_model(model_type):
    return models.get(model_type)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/status')
def status():
    """Return model loading status, GPU info, and queue status."""
    # Calculate queue length and estimated wait
    with queue_lock:
        queued_jobs = [j for j in jobs.values() if j['status'] in ['queued', 'processing']]
        queue_length = len(queued_jobs)
        # Estimate wait time: ~0.5s per second of audio duration
        total_duration = sum(j.get('duration', 8) for j in queued_jobs)
        estimated_wait = total_duration * 0.5

    return jsonify({
        'models': loading_status,
        'gpu': get_gpu_info(),
        'queue_length': queue_length,
        'estimated_wait': estimated_wait
    })


@app.route('/queue-status')
def queue_status():
    """Return current queue status."""
    with queue_lock:
        queue_list = []
        for job_id, job in jobs.items():
            if job['status'] in ['queued', 'processing']:
                queue_list.append({
                    'id': job_id,
                    'status': job['status'],
                    'prompt': job['prompt'][:50] + '...' if len(job['prompt']) > 50 else job['prompt'],
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
    """Get detailed queue status with all jobs for the Queue Explorer."""
    with queue_lock:
        queue_list = []
        for job_id, job in jobs.items():
            if job['status'] in ['queued', 'processing']:
                queue_list.append({
                    'id': job_id,
                    'status': job['status'],
                    'prompt': job['prompt'][:80] + '...' if len(job['prompt']) > 80 else job['prompt'],
                    'model': job.get('model', 'music'),
                    'duration': job.get('duration', 8),
                    'priority': job.get('priority', 'standard'),
                    'created': job.get('created'),
                    'progress': job.get('progress', ''),
                    'progress_pct': job.get('progress_pct', 0),
                    'user_id': job.get('user_id')
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
def api_cancel_job(job_id):
    """Cancel a queued job. Only the job owner can cancel."""
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

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


@app.route('/job/<job_id>')
def job_status(job_id):
    """Get status of a specific job."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
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
        'retry_count': job.get('retry_count', 0)
    })


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', 'upbeat electronic music')
    duration = min(int(data.get('duration', 8)), 120)
    model_type = data.get('model', 'music')
    make_loop = data.get('loop', False)
    priority = data.get('priority', 'standard')
    user_id = data.get('user_id')  # Optional user ID from widget

    if loading_status.get(model_type) != 'ready':
        return jsonify({
            'success': False,
            'error': f'Model still loading: {loading_status.get(model_type, "unknown")}'
        }), 503

    # Create job
    job_id = uuid.uuid4().hex
    priority_num = PRIORITY_LEVELS.get(priority, 2)

    job = {
        'id': job_id,
        'prompt': prompt,
        'duration': duration,
        'model': model_type,
        'loop': make_loop,
        'priority': priority,
        'status': 'queued',
        'created': datetime.now().isoformat(),
        'progress': 'Waiting in queue...',
        'user_id': user_id  # Track which user created this
    }

    with queue_lock:
        jobs[job_id] = job
        # Priority queue: (priority, timestamp, job_id)
        job_queue.put((priority_num, time.time(), job_id))

        # Calculate position
        position = sum(1 for j in jobs.values() if j['status'] in ['queued', 'processing'])
        job['position'] = position

    return jsonify({
        'success': True,
        'job_id': job_id,
        'position': position
    })


@app.route('/audio/<filename>')
def serve_audio(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        response = send_file(filepath, mimetype='audio/wav')
        # Add CORS headers for embedded widget support
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    return "Not found", 404


@app.route('/spectrogram/<filename>')
def serve_spectrogram(filename):
    filepath = os.path.join(SPECTROGRAMS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return "Not found", 404


@app.route('/generate-spectrogram/<audio_filename>')
def generate_spectrogram_for_file(audio_filename):
    """Generate spectrogram for an existing audio file on demand."""
    audio_path = os.path.join(OUTPUT_DIR, audio_filename)
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
def history():
    # Optional filters
    model_filter = request.args.get('model')  # 'music' or 'audio'
    user_id = request.args.get('user_id')  # User ID from widget

    files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.wav')],
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
        reverse=True
    )

    metadata = load_metadata()
    result = []
    for f in files:
        info = metadata.get(f, {})

        # Filter by model type if specified
        if model_filter and info.get('model') != model_filter:
            continue

        # Filter by user_id if specified
        if user_id and info.get('user_id') != user_id:
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
def rate():
    data = request.json
    filename = data.get('filename')
    rating = data.get('rating')

    if not filename:
        return jsonify({'success': False, 'error': 'No filename'}), 400

    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]['rating'] = rating
        save_metadata(metadata)
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'File not found'}), 404


# =============================================================================
# NEW API: Library with Pagination & Search
# =============================================================================

@app.route('/api/library')
def api_library():
    """
    Get paginated library with filters.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        model: Filter by 'music' or 'audio'
        search: Full-text search in prompts
        sort: 'recent', 'popular', or 'rating'
        user_id: Filter by creator
        category: Filter by genre/category (e.g., 'ambient', 'nature')
    """
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    model = request.args.get('model')
    search = request.args.get('search')
    sort = request.args.get('sort', 'recent')
    user_id = request.args.get('user_id')
    category = request.args.get('category')

    result = db.get_library(
        page=page,
        per_page=per_page,
        model=model,
        search=search,
        sort=sort,
        user_id=user_id,
        category=category
    )

    return jsonify(result)


@app.route('/api/library/<gen_id>')
def api_library_item(gen_id):
    """Get a single generation by ID."""
    generation = db.get_generation(gen_id)
    if not generation:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(generation)


@app.route('/api/library/counts')
def api_library_counts():
    """Get counts for each content type."""
    counts = db.get_library_counts()
    return jsonify(counts)


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
def api_vote(gen_id):
    """
    Cast or update a vote with optional private feedback.

    Body:
        vote: 1 (upvote), -1 (downvote), or 0 (remove)
        user_id: The voter's user ID
        feedback_reasons: Optional list of feedback tags (e.g., ['catchy', 'quality'])
        notes: Optional private notes (not displayed publicly)
        suggested_model: Optional reclassification suggestion ('music' or 'audio')
    """
    data = request.json or {}
    vote_value = data.get('vote', 0)
    user_id = data.get('user_id')
    feedback_reasons = data.get('feedback_reasons')  # List of tags
    notes = data.get('notes')  # Private notes
    suggested_model = data.get('suggested_model')  # Reclassification suggestion

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    if vote_value not in [-1, 0, 1]:
        return jsonify({'error': 'vote must be -1, 0, or 1'}), 400

    # Validate suggested_model if provided
    if suggested_model and suggested_model not in ('music', 'audio'):
        return jsonify({'error': 'suggested_model must be "music" or "audio"'}), 400

    # Verify generation exists
    generation = db.get_generation(gen_id)
    if not generation:
        return jsonify({'error': 'Not found'}), 404

    result = db.vote(gen_id, user_id, vote_value, feedback_reasons, notes, suggested_model)
    return jsonify(result)


@app.route('/api/library/votes', methods=['POST'])
def api_get_votes():
    """
    Get user's votes for multiple generations.

    Body:
        generation_ids: List of generation IDs
        user_id: The user's ID
    """
    data = request.json or {}
    generation_ids = data.get('generation_ids', [])
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

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
def api_suggest_tag(gen_id):
    """
    Submit a tag/category suggestion for a generation.
    When 3+ users agree, the category is automatically applied or removed.

    Body:
        category: The category to suggest
        action: 'add' (default) or 'remove'
        user_id: (optional) User identifier
    """
    data = request.get_json()
    user_id = data.get('user_id') if data else None
    if not user_id:
        user_id = request.args.get('user_id') or request.remote_addr

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


@app.route('/api/library/<gen_id>/tag-suggestions')
def api_get_tag_suggestions(gen_id):
    """
    Get all tag suggestions for a generation with vote counts.
    """
    user_id = request.args.get('user_id') or request.remote_addr

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

    current_categories = json.loads(gen['category'] or '[]')

    return jsonify({
        'suggestions': suggestions,
        'user_suggestions': user_suggestions,
        'current_categories': current_categories,
        'threshold': db.TAG_CONSENSUS_THRESHOLD
    })


@app.route('/api/categories/<model>')
def api_get_categories(model):
    """
    Get all available categories for a model type (music or audio).
    Includes usage counts for sorting by popularity.
    """
    if model not in ('music', 'audio'):
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
# NEW API: Radio Station
# =============================================================================

@app.route('/api/radio/shuffle')
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
    count = min(int(request.args.get('count', 10)), 50)

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
    count = min(int(request.args.get('count', 5)), 20)
    exclude_str = request.args.get('exclude', '')

    # Parse exclude list
    exclude_ids = [id.strip() for id in exclude_str.split(',') if id.strip()]

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
# Favorites
# =============================================================================

@app.route('/api/favorites/<gen_id>', methods=['POST'])
def api_add_favorite(gen_id):
    """Add a generation to user's favorites."""
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

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
def api_remove_favorite(gen_id):
    """Remove a generation from user's favorites."""
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    removed = db.remove_favorite(user_id, gen_id)
    return jsonify({
        'success': True,
        'favorited': False,
        'was_removed': removed
    })


@app.route('/api/favorites')
def api_get_favorites():
    """Get user's favorites (paginated)."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    model = request.args.get('model')

    result = db.get_favorites(user_id, page=page, per_page=per_page, model=model)
    return jsonify(result)


@app.route('/api/favorites/check', methods=['POST'])
def api_check_favorites():
    """Check which generations are favorited by user."""
    data = request.json or {}
    user_id = data.get('user_id')
    generation_ids = data.get('generation_ids', [])

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    favorites = db.get_user_favorites(user_id, generation_ids)
    return jsonify({'favorites': list(favorites)})


@app.route('/api/radio/favorites')
def api_radio_favorites():
    """Shuffle play user's favorites."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    model = request.args.get('model')
    count = min(int(request.args.get('count', 10)), 50)

    tracks = db.get_random_favorites(user_id, count=count, model=model)
    return jsonify({
        'tracks': tracks,
        'source': 'favorites'
    })


@app.route('/api/radio/top-rated')
def api_radio_top_rated():
    """Get top rated tracks for radio."""
    model = request.args.get('model')
    count = min(int(request.args.get('count', 10)), 50)

    tracks = db.get_top_rated_tracks(model=model, count=count)
    return jsonify({
        'tracks': tracks,
        'source': 'top-rated'
    })


@app.route('/api/radio/new')
def api_radio_new():
    """Get recently created tracks for radio."""
    model = request.args.get('model')
    count = min(int(request.args.get('count', 10)), 50)
    hours = int(request.args.get('hours', 168))  # Default 7 days

    tracks = db.get_recent_tracks(model=model, count=count, hours=hours)
    return jsonify({
        'tracks': tracks,
        'source': 'new'
    })


# =============================================================================
# User History - Requires authenticated user from Graphlings/Valnet widget
# =============================================================================

@app.route('/api/history/plays')
def api_play_history():
    """Get user's play history."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    history = db.get_user_play_history(user_id, limit=limit, offset=offset)
    return jsonify({
        'history': history,
        'limit': limit,
        'offset': offset,
        'has_more': len(history) == limit
    })


@app.route('/api/history/votes')
def api_vote_history():
    """Get user's vote history."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    history = db.get_user_vote_history(user_id, limit=limit, offset=offset)
    return jsonify({
        'history': history,
        'limit': limit,
        'offset': offset,
        'has_more': len(history) == limit
    })


# =============================================================================
# Playlists - Requires authenticated user from Graphlings/Valnet widget
# =============================================================================

@app.route('/api/playlists', methods=['POST'])
def api_create_playlist():
    """Create a new playlist."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not user_id:
        return jsonify({'error': 'Authentication required. Please log in via Graphlings.'}), 401
    if not name:
        return jsonify({'error': 'Playlist name is required'}), 400

    # Generate unique playlist ID
    playlist_id = 'pl_' + uuid.uuid4().hex[:12]

    result = db.create_playlist(playlist_id, user_id, name, description or None)
    if result:
        return jsonify(result), 201
    return jsonify({'error': 'Failed to create playlist'}), 500


@app.route('/api/playlists')
def api_get_playlists():
    """Get user's playlists."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required. Please log in via Graphlings.'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    result = db.get_user_playlists(user_id, page, per_page)
    return jsonify(result)


@app.route('/api/playlists/<playlist_id>')
def api_get_playlist(playlist_id):
    """Get a playlist with its tracks."""
    playlist = db.get_playlist(playlist_id)
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404

    tracks = db.get_playlist_tracks(playlist_id, include_metadata=True)
    playlist['tracks'] = tracks

    return jsonify(playlist)


@app.route('/api/playlists/<playlist_id>', methods=['PUT'])
def api_update_playlist(playlist_id):
    """Update playlist name/description."""
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    name = data.get('name')
    description = data.get('description')

    result = db.update_playlist(playlist_id, user_id, name, description)
    if result:
        return jsonify(result)
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>', methods=['DELETE'])
def api_delete_playlist(playlist_id):
    """Delete a playlist."""
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    if db.delete_playlist(playlist_id, user_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>/tracks', methods=['POST'])
def api_add_playlist_track(playlist_id):
    """Add a track to a playlist."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    generation_id = data.get('generation_id')

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    if not generation_id:
        return jsonify({'error': 'generation_id required'}), 400

    result = db.add_track_to_playlist(playlist_id, generation_id, user_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/playlists/<playlist_id>/tracks/<generation_id>', methods=['DELETE'])
def api_remove_playlist_track(playlist_id, generation_id):
    """Remove a track from a playlist."""
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    if db.remove_track_from_playlist(playlist_id, generation_id, user_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Track not found in playlist or not authorized'}), 404


@app.route('/api/playlists/<playlist_id>/reorder', methods=['PUT'])
def api_reorder_playlist(playlist_id):
    """Reorder tracks in a playlist."""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    track_order = data.get('track_order', [])

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    if not track_order:
        return jsonify({'error': 'track_order required'}), 400

    if db.reorder_playlist_tracks(playlist_id, user_id, track_order):
        return jsonify({'success': True})
    return jsonify({'error': 'Playlist not found or not authorized'}), 404


@app.route('/api/radio/playlist/<playlist_id>')
def api_radio_playlist(playlist_id):
    """Get playlist tracks for radio playback."""
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
def api_stats():
    """Get database statistics."""
    return jsonify(db.get_stats())


# =============================================================================
# Play & Download Tracking
# =============================================================================

@app.route('/api/track/<gen_id>/play', methods=['POST', 'OPTIONS'])
def api_record_play(gen_id):
    """Record a play event for analytics."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    data = request.get_json() or {}
    user_id = data.get('user_id')
    session_id = data.get('session_id')
    play_duration = data.get('duration')
    source = data.get('source', 'radio')

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
    limit = request.args.get('limit', 20, type=int)
    model = request.args.get('model')

    tracks = db.get_trending_tracks(hours, limit, model)
    return jsonify({'tracks': tracks})


@app.route('/api/most-played')
def api_most_played():
    """Get most played tracks."""
    limit = request.args.get('limit', 50, type=int)
    model = request.args.get('model')
    days = request.args.get('days', type=int)

    tracks = db.get_most_played(limit, model, days)
    return jsonify({'tracks': tracks})


@app.route('/api/log-error', methods=['POST'])
def api_log_error():
    """Log frontend errors to backend."""
    data = request.get_json() or {}
    message = data.get('message', 'Unknown error')
    url = data.get('url', '')
    user_agent = data.get('userAgent', '')
    timestamp = data.get('timestamp', '')

    # Log to console with formatting
    print(f"\n{'='*60}")
    print(f"[FRONTEND ERROR] {timestamp}")
    print(f"Message: {message}")
    print(f"URL: {url}")
    print(f"User-Agent: {user_agent[:80]}...")
    print(f"{'='*60}\n")

    return jsonify({'logged': True})


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
def download(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
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

        # Track the download
        gen_id = filename.replace('.wav', '')
        user_id = request.args.get('user_id')
        db.record_download(gen_id, user_id, 'wav')

        return send_file(filepath, as_attachment=True, download_name=clean_name)
    return "Not found", 404


@app.route('/random-prompt', methods=['POST'])
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
def api_radio():
    """Universal radio API endpoint for widget and internal use."""
    station = request.args.get('station', 'shuffle')
    limit = min(int(request.args.get('limit', 10)), 50)
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
        user_id = request.args.get('user_id')
        if user_id:
            tracks = db.get_random_favorites(user_id, count=limit, model=model)
        else:
            tracks = []
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

    print("Starting server... Models loading in background.")
    print(f"Access at http://{HOST if HOST != '0.0.0.0' else 'localhost'}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
