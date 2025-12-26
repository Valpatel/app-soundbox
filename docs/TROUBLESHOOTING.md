# Sound Box Troubleshooting Guide

## Model Loading Issues

### Models stuck on "loading" or "pending"

**Symptoms:**
- Status page shows models not ready
- Generate button disabled
- HTTP 503 errors on generation requests

**Causes & Solutions:**

1. **First run downloading models**
   - AudioCraft models are ~1-2GB each
   - First startup takes 30-60 seconds
   - Check console for download progress

2. **CUDA not available**
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```
   Should print `True`. If `False`:
   - Verify NVIDIA drivers installed: `nvidia-smi`
   - Reinstall PyTorch with CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu121`

3. **Model loading crashed**
   - Check console for tracebacks
   - Try restarting the server
   - Verify GPU memory available: `nvidia-smi`

### HTTP 503: Model still loading

**Meaning:** Model requested for generation isn't ready yet.

**Solutions:**
- Wait for models to finish loading (check `/status` endpoint)
- If stuck, restart server and monitor console output

## GPU/Memory Issues

### CUDA out of memory

**Symptoms:**
- Generation fails mid-process
- Error: "CUDA out of memory"
- Server may become unresponsive

**Solutions:**

1. **Reduce generation duration**
   - Longer audio = more VRAM needed
   - Try shorter durations (8-15 seconds)

2. **Close other GPU applications**
   ```bash
   nvidia-smi  # Check what's using GPU
   ```

3. **Use smaller models**
   - Currently using MusicGen Small and AudioGen Medium
   - Can modify to use smaller variants

4. **Enable memory-efficient attention**
   - If using transformers with attention, enable `xformers`

### GPU not detected

**Symptoms:**
- `torch.cuda.is_available()` returns `False`
- Models load on CPU (very slow)

**Solutions:**

1. **Check NVIDIA drivers**
   ```bash
   nvidia-smi
   ```
   Should show GPU info. If not:
   ```bash
   sudo apt install nvidia-driver-535  # or latest version
   sudo reboot
   ```

2. **Check CUDA installation**
   ```bash
   nvcc --version
   ```

3. **Reinstall PyTorch with CUDA**
   ```bash
   pip uninstall torch torchaudio
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

## Database Issues

### "no such table" errors

**Symptoms:**
- API returns 500 errors
- Console shows SQLite errors about missing tables

**Solutions:**

1. **Initialize database**
   ```bash
   python database.py init
   ```

2. **Run migrations**
   ```bash
   python database.py migrate
   ```

3. **Check database file exists**
   ```bash
   ls -la soundbox.db
   ```

### Database locked

**Symptoms:**
- Intermittent failures on writes
- Error: "database is locked"

**Solutions:**

1. **Check for multiple writers**
   - Ensure only one server instance running
   - Don't run database.py commands while server is running

2. **Increase timeout**
   - SQLite default timeout is 5 seconds
   - Can increase in `get_db()` function

### Full-text search not working

**Symptoms:**
- Search returns no results
- Error about FTS5

**Solutions:**

1. **Rebuild FTS index**
   ```sql
   INSERT INTO generations_fts(generations_fts) VALUES('rebuild');
   ```

2. **Verify FTS5 support**
   ```python
   import sqlite3
   conn = sqlite3.connect(':memory:')
   conn.execute("CREATE VIRTUAL TABLE test USING fts5(content)")
   ```
   If this fails, rebuild SQLite with FTS5 enabled.

## Frontend Issues

### Page loads but nothing works

**Symptoms:**
- Blank page or broken UI
- No response to clicks
- Console errors in browser

**Solutions:**

1. **Check browser console (F12)**
   - Look for JavaScript errors
   - Note any 404 errors for resources

2. **Clear browser cache**
   - Hard refresh: Ctrl+Shift+R
   - Or clear site data in DevTools

3. **Verify API endpoints**
   ```bash
   curl http://localhost:5309/status
   curl http://localhost:5309/api/library
   ```

### Audio won't play

**Symptoms:**
- Click play but no sound
- Audio element shows error

**Solutions:**

1. **Check file exists**
   ```bash
   curl -I http://localhost:5309/audio/filename.wav
   ```
   Should return 200, not 404

2. **Check browser audio permissions**
   - Some browsers block autoplay
   - User interaction required before play

3. **Verify audio file is valid**
   ```bash
   file generated/filename.wav
   ffprobe generated/filename.wav
   ```

### Votes/favorites not saving

**Symptoms:**
- Votes show briefly then disappear
- Favorites don't persist

**Solutions:**

1. **Check user identification**
   - User ID from Graphlings, or
   - Device ID from localStorage

2. **Check API response**
   - Open browser DevTools → Network
   - Look for errors on vote/favorite requests

3. **Verify database writes**
   ```bash
   sqlite3 soundbox.db "SELECT COUNT(*) FROM votes"
   ```

## Generation Issues

### Generation fails immediately

**Symptoms:**
- Job goes to "failed" status instantly
- No audio produced

**Solutions:**

1. **Check model status**
   ```bash
   curl http://localhost:5309/status | jq '.models'
   ```

2. **Check server logs**
   - Look for Python tracebacks
   - Note any model-specific errors

3. **Try simple prompt**
   - Use basic prompt like "piano music"
   - Avoid special characters

### Low quality output

**Symptoms:**
- Audio has noise/clipping
- Quality score < 50
- Auto-retry not helping

**Solutions:**

1. **Check quality analysis**
   - Quality issues logged in console
   - Common: clipping, silence, noise

2. **Adjust prompt**
   - More specific descriptions help
   - Avoid conflicting terms

3. **Try different duration**
   - Very short (<5s) may produce artifacts
   - Very long (>60s) may degrade

### Generation stuck in queue

**Symptoms:**
- Job shows "queued" indefinitely
- Position doesn't decrease

**Solutions:**

1. **Check if worker is stuck**
   ```bash
   curl http://localhost:5309/queue-status
   ```
   Look for `current_job` - if same for long time, worker may be stuck

2. **Restart server**
   - Queue is in-memory only
   - Jobs will be lost on restart

3. **Check GPU utilization**
   ```bash
   watch -n 1 nvidia-smi
   ```
   Should show activity during generation

## Network/Connection Issues

### Connection refused

**Symptoms:**
- Browser shows "connection refused"
- Cannot reach server

**Solutions:**

1. **Verify server is running**
   ```bash
   ps aux | grep app.py
   ```

2. **Check port binding**
   ```bash
   netstat -tlnp | grep 5309
   ```

3. **Check firewall**
   ```bash
   sudo ufw status
   sudo ufw allow 5309
   ```

### Slow responses

**Symptoms:**
- API calls take many seconds
- Timeouts on long operations

**Solutions:**

1. **Check CPU/GPU load**
   ```bash
   htop
   nvidia-smi
   ```

2. **Increase timeouts**
   - Nginx: `proxy_read_timeout 300s;`
   - Gunicorn: `--timeout 300`

3. **Check disk I/O**
   - Audio writing may be slow on HDD
   - Use SSD for generated/ directory

## Logging

### Enable debug logging

```bash
FLASK_DEBUG=true python app.py
```

### Check logs

```bash
# If using systemd
journalctl -u soundbox -f

# If running directly
python app.py 2>&1 | tee soundbox.log
```

### Database statistics

```bash
python database.py stats
```

Outputs generation counts, vote counts, etc.

## Getting Help

1. **Check documentation**
   - API.md for endpoint issues
   - DATABASE.md for schema questions
   - ARCHITECTURE.md for system overview

2. **Gather diagnostic info**
   ```bash
   python -c "import torch; print(f'PyTorch: {torch.__version__}')"
   python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
   nvidia-smi
   curl http://localhost:5309/status
   ```

3. **Report issues**
   - Include error messages
   - Include diagnostic info above
   - Note reproduction steps
