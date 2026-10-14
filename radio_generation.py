"""Listener-triggered radio refill using the existing generation admission path."""
import threading
from flask import jsonify, request

STATIONS = {
    'ambient': ('ambient soundscape', 'Gentle ambient soundscape, atmospheric pads, evolving instrumental music'),
    'retro': ('chiptune 8-bit retro', 'Playful retro chiptune 8-bit instrumental music with a memorable melody'),
    'piano': ('piano gentle keys', 'Gentle piano and warm keys, expressive instrumental music'),
    'happy': ('happy upbeat bouncy', 'Happy upbeat bouncy instrumental music, bright melody and steady rhythm'),
    'dreamy': ('dreamy ethereal', 'Dreamy ethereal instrumental music with soft shimmering textures'),
    'lofi': ('lo-fi chill', 'Lo-fi chill instrumental music, mellow chords and relaxed drums'),
    'all': ('', 'Melodic instrumental music with a developing theme and steady rhythm'),
    'shuffle': ('', 'Melodic instrumental music with a developing theme and steady rhythm'),
    'trending': ('', 'Upbeat instrumental music with a catchy developing melody'),
    'top-rated': ('', 'Expressive instrumental music with a memorable melody'),
    'new': ('', 'Fresh instrumental music with evolving melody and rich harmony'),
    'surprise': ('', 'Imaginative instrumental music with playful melodic surprises'),
}


def install_radio_generation(app, db, jobs, queue_lock, generate):
    admission_lock = threading.Lock()

    @app.post('/api/radio/fill')
    def radio_fill():
        if not request.is_json:
            return jsonify(error='Content-Type must be application/json'), 415
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('station') not in STATIONS:
            return jsonify(error='Choose a supported music station'), 400
        station = data['station']
        excluded = data.get('exclude', [])
        if (not isinstance(excluded, list) or len(excluded) > 100
                or any(not isinstance(i, str) or len(i) > 64 for i in excluded)):
            return jsonify(error='Invalid radio history'), 400
        # Serializes station admission so simultaneous listeners share one job.
        # The model worker still uses its normal queue lock and scheduling policy.
        with admission_lock:
            tracks = db.get_random_tracks_excluding(model='music', search=STATIONS[station][0],
                                                    exclude_ids=excluded, count=5)
            if tracks:
                return jsonify(tracks=tracks)
            with queue_lock:
                pending = next((j['id'] for j in jobs.values()
                                if j.get('radio_station') == station
                                and j['status'] in ('queued', 'processing')), None)
            if pending:
                return jsonify(job_id=pending, shared=True), 202
            # Call the decorated handler, retaining authentication, quotas,
            # validation, model readiness and atomic global queue admission.
            data.clear()
            data.update(prompt=STATIONS[station][1], model='music', duration=90, loop=False)
            response = app.make_response(generate())
            result = response.get_json(silent=True) or {}
            if response.status_code == 200 and result.get('job_id'):
                with queue_lock:
                    jobs[result['job_id']]['radio_station'] = station
                return jsonify(job_id=result['job_id'], shared=False), 202
            return response
