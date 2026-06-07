// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Real end-to-end generation tests.
 *
 * These tests actually invoke the AudioCraft pipeline (MusicGen / AudioGen)
 * and verify that audio files are produced, served, and have spectrograms.
 *
 * They are slow (~30-90s per generation) and require the server to be running
 * with models loaded. They are tagged @slow @generation so CI can opt them
 * in/out via `--grep` filters.
 *
 * Discovered API shapes (from app.py):
 *
 *   POST /generate          -> { success: true, job_id, position, queue_message,
 *                                 tier, limits: { max_duration, per_hour } }
 *                            (errors: 400/403/429/503 with { success:false, error })
 *
 *   GET  /job/<job_id>      -> { id, status, progress, progress_pct,
 *                                 filename, spectrogram, quality, error,
 *                                 position, retry_count, skip }
 *                            status ∈ {queued, processing, complete, failed}
 *                            (404 if not owner / not found)
 *
 *   GET  /audio/<filename>  -> audio/wav binary
 *   GET  /spectrogram/<png> -> image/png binary (may 404 if not yet built)
 *   GET  /generate-spectrogram/<wav> -> { spectrogram: "<file>.png" } (builds on demand)
 *
 * NOTE: /job does not return audio_url — it returns just `filename`. We
 * construct /audio/<filename> ourselves.
 */

const POLL_INTERVAL_MS = 2000;
const GEN_TIMEOUT_MS = 170000; // a little under test timeout to give clear error

/**
 * Submit a generation job. Returns { job_id } on success, throws on failure.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {{prompt: string, model: string, duration: number}} body
 */
async function submitJob(request, body) {
    const res = await request.post('/generate', {
        data: body,
        headers: { 'Content-Type': 'application/json' }
    });
    const status = res.status();
    const json = await res.json().catch(() => ({}));

    if (status === 503) {
        throw new Error(
            `Generation unavailable (503): ${json.error || 'unknown'}. ` +
            `Models may still be loading. Try again once /status reports ready.`
        );
    }
    if (status === 429) {
        throw new Error(
            `Rate limited (429): ${json.error || 'unknown'}. ` +
            `Wait for pending jobs to clear or relax limits in test env.`
        );
    }
    if (!res.ok() || !json.success) {
        throw new Error(`POST /generate failed (${status}): ${JSON.stringify(json)}`);
    }
    if (!json.job_id) {
        throw new Error(`POST /generate succeeded but returned no job_id: ${JSON.stringify(json)}`);
    }
    return json;
}

/**
 * Poll a job until it reaches a terminal state or the deadline passes.
 * Returns the final job payload.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} jobId
 * @param {number} timeoutMs
 * @param {(state: object) => void} [onTick] - called every poll with the job payload
 */
async function pollJob(request, jobId, timeoutMs, onTick) {
    const deadline = Date.now() + timeoutMs;
    let lastJob = null;
    while (Date.now() < deadline) {
        const res = await request.get(`/job/${jobId}`);
        if (res.status() === 404) {
            throw new Error(`Job ${jobId} returned 404 mid-poll (ownership mismatch?)`);
        }
        if (!res.ok()) {
            throw new Error(`GET /job/${jobId} failed: ${res.status()}`);
        }
        const job = await res.json();
        lastJob = job;
        if (onTick) onTick(job);
        if (job.status === 'complete') return job;
        if (job.status === 'failed') {
            throw new Error(
                `Job ${jobId} failed: ${job.error || 'no error message'} ` +
                `(last progress: ${job.progress})`
            );
        }
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
    }
    throw new Error(
        `Job ${jobId} did not complete within ${timeoutMs}ms. ` +
        `Last status: ${lastJob ? lastJob.status : 'unknown'}, ` +
        `progress: ${lastJob ? lastJob.progress : 'n/a'}, ` +
        `progress_pct: ${lastJob ? lastJob.progress_pct : 'n/a'}`
    );
}

/**
 * Verify an audio file is served correctly.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} filename
 */
async function verifyAudio(request, filename) {
    const res = await request.get(`/audio/${filename}`);
    expect(res.status(), `GET /audio/${filename} should return 200`).toBe(200);
    const ct = res.headers()['content-type'] || '';
    expect(ct, `audio content-type should be audio/*, got ${ct}`).toMatch(/audio\//);
    const body = await res.body();
    expect(body.length, `audio body should be > 1000 bytes, got ${body.length}`).toBeGreaterThan(1000);
}

/**
 * Verify spectrogram exists (or can be generated on demand) for a wav file.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} wavFilename
 */
async function verifySpectrogram(request, wavFilename) {
    const pngFilename = wavFilename.replace(/\.wav$/, '.png');

    // First try the direct spectrogram serve — it may already exist if the
    // generation pipeline produced one inline.
    let res = await request.get(`/spectrogram/${pngFilename}`);

    if (res.status() === 404) {
        // Not yet built — ask the on-demand generator.
        const gen = await request.get(`/generate-spectrogram/${wavFilename}`);
        expect(gen.status(), `generate-spectrogram should succeed`).toBe(200);
        const genJson = await gen.json();
        expect(genJson.spectrogram).toBe(pngFilename);
        // Now fetch the image.
        res = await request.get(`/spectrogram/${pngFilename}`);
    }

    expect(res.status(), `GET /spectrogram/${pngFilename} should return 200`).toBe(200);
    const ct = res.headers()['content-type'] || '';
    expect(ct, `spectrogram content-type should be image/png, got ${ct}`).toBe('image/png');
    const body = await res.body();
    expect(body.length, `spectrogram should be > 100 bytes, got ${body.length}`).toBeGreaterThan(100);
}

test.describe('@slow @generation Real generation pipeline', () => {

    test('music generation end-to-end produces playable audio + spectrogram', async ({ request }) => {
        test.setTimeout(180000);

        const submit = await submitJob(request, {
            prompt: 'soft piano melody',
            model: 'music',
            duration: 3
        });
        expect(submit.success).toBe(true);
        expect(typeof submit.job_id).toBe('string');
        expect(submit.job_id).toMatch(/^[a-f0-9]{32}$/);
        expect(typeof submit.position).toBe('number');

        const job = await pollJob(request, submit.job_id, GEN_TIMEOUT_MS);
        expect(job.status).toBe('complete');
        expect(job.filename, 'completed job should have filename').toBeTruthy();
        expect(job.filename).toMatch(/\.wav$/);

        await verifyAudio(request, job.filename);
        await verifySpectrogram(request, job.filename);
    });

    test('sfx (audiogen) generation end-to-end produces playable audio', async ({ request }) => {
        test.setTimeout(180000);

        const submit = await submitJob(request, {
            prompt: 'thunder rumbling',
            model: 'audio',
            duration: 3
        });
        expect(submit.success).toBe(true);

        const job = await pollJob(request, submit.job_id, GEN_TIMEOUT_MS);
        expect(job.status).toBe('complete');
        expect(job.filename).toBeTruthy();
        expect(job.filename).toMatch(/\.wav$/);

        await verifyAudio(request, job.filename);
    });

    test('job polling reports progress and transitions through expected states', async ({ request }) => {
        test.setTimeout(180000);

        const submit = await submitJob(request, {
            prompt: 'gentle acoustic guitar',
            model: 'music',
            duration: 3
        });

        /** @type {Set<string>} */
        const statusesSeen = new Set();
        /** @type {number[]} */
        const progressPctSeen = [];

        const job = await pollJob(request, submit.job_id, GEN_TIMEOUT_MS, (s) => {
            if (s.status) statusesSeen.add(s.status);
            if (typeof s.progress_pct === 'number') progressPctSeen.push(s.progress_pct);
        });

        expect(job.status).toBe('complete');

        // We expect to see at least one non-terminal state plus 'complete'.
        // Generation usually starts in 'queued' and moves to 'processing' before 'complete'.
        // We don't insist on both — fast machines may skip 'queued' between polls.
        expect(statusesSeen.has('complete'), 'should observe complete').toBe(true);
        const sawIntermediate = statusesSeen.has('queued') || statusesSeen.has('processing');
        expect(sawIntermediate,
            `should observe queued or processing at least once; saw: ${[...statusesSeen].join(',')}`
        ).toBe(true);

        // progress_pct should appear as a number on every payload (server defaults to 0)
        expect(progressPctSeen.length).toBeGreaterThan(0);
        for (const p of progressPctSeen) {
            expect(p).toBeGreaterThanOrEqual(0);
            expect(p).toBeLessThanOrEqual(100);
        }
    });

    test('concurrent generation: two jobs submitted in quick succession both complete', async ({ request }) => {
        test.setTimeout(300000);

        // Submit two jobs back-to-back. Per-user pending limit on free tier is
        // typically 2 — we stay within that. If the server rejects the second
        // for limit reasons, the helper will throw with a clear message.
        const submitA = await submitJob(request, {
            prompt: 'cheerful chiptune beat',
            model: 'music',
            duration: 3
        });
        const submitB = await submitJob(request, {
            prompt: 'mysterious ambient pad',
            model: 'music',
            duration: 3
        });

        expect(submitA.job_id).not.toBe(submitB.job_id);

        // The second submission should report a queue position >= the first
        // (queue is FIFO at equal priority). We don't assert strict equality
        // because positions are computed live and other test users may add jobs.
        expect(typeof submitA.position).toBe('number');
        expect(typeof submitB.position).toBe('number');
        expect(submitB.position,
            `second job position (${submitB.position}) should be >= first (${submitA.position})`
        ).toBeGreaterThanOrEqual(submitA.position);

        // Poll both. They may complete in either order depending on scheduler,
        // but both must reach 'complete' within the timeout.
        const [jobA, jobB] = await Promise.all([
            pollJob(request, submitA.job_id, 280000),
            pollJob(request, submitB.job_id, 280000),
        ]);

        expect(jobA.status).toBe('complete');
        expect(jobB.status).toBe('complete');
        expect(jobA.filename).toBeTruthy();
        expect(jobB.filename).toBeTruthy();
        expect(jobA.filename).not.toBe(jobB.filename);

        await verifyAudio(request, jobA.filename);
        await verifyAudio(request, jobB.filename);
    });
});
