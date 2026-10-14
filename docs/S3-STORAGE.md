# S3-compatible storage and recovery

Soundbox runs locally by default. Optional S3 storage adds a shared backing store
for music, sound effects and saved speech, with verified recovery snapshots of the
whole SQLite database (ratings, votes, play history, playlists, favorites and
metadata). Legacy star ratings in `generations.json` are retained as well. It works through the standard S3 API; SeaweedFS is one supported
provider, not a special storage path in the application.

SQLite remains on local disk. Do not mount an S3 bucket as a SQLite filesystem.
Run one active Soundbox writer per key prefix. This is recoverable storage, not
active-active database replication or automatic server failover.

## Configuration

For a Python installation, install `requirements-s3.txt` in the application venv.
The all-inclusive Docker image includes the SDK. Use a pre-created private bucket
and a dedicated credential with ListBucket, GetObject and PutObject permissions
restricted to that bucket/prefix. Soundbox does not require bucket administration
or object deletion rights. Keep environment files outside Git, readable only by
the service/operator (mode 0600). Never put credentials in a URL or browser code.

```dotenv
SOUNDBOX_STORAGE=s3
SOUNDBOX_S3_ENDPOINT_URL=https://s3.example.com
SOUNDBOX_S3_BUCKET=soundbox
SOUNDBOX_S3_PREFIX=production
SOUNDBOX_S3_ADDRESSING_STYLE=path
SOUNDBOX_S3_SYNC_SECONDS=300
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-scoped-access-key
AWS_SECRET_ACCESS_KEY=your-scoped-secret-key
```

Omit the endpoint to use AWS S3. Path addressing is convenient for compatible
providers; set `virtual` if your provider requires it. TLS verification remains
enabled. An HTTP endpoint is appropriate only on a trusted private network.
The standard AWS credential provider chain also supports deployment roles.

For Compose, add the protected host file with `env_file` on the Soundbox service.
Do not bake it into the image. The reviewed container-patch release tool supports
`--environment-file /absolute/protected/file.env`, preserves it in later releases,
and records the prior override for rollback. It refuses a busy generation queue.

## Behavior and limits

- Finished audio stays in the existing local generated directory. Every five
  minutes (configurable, minimum 60 seconds), the existing app scheduler snapshots
  SQLite and uploads the referenced audio to `<prefix>/audio/<filename>`.
- Audio object names are immutable. Different bytes under an existing filename
  fail verification instead of silently overwriting a previous song. MD5 checks
  uploads in transit; SHA-256 metadata verifies downloaded and restored bytes.
- Legacy JSON metadata defaults beside `DB_PATH` so container volumes preserve it;
  `METADATA_FILE` can override that location. Startup copies an existing root
  `generations.json` only when the persistent destination is absent. JSON saves
  use atomic replacement. Its snapshot is a separate point-in-time copy; SQLite
  remains the canonical transactionally consistent library.
- Each successful run creates an immutable database and manifest under
  `<prefix>/snapshots/<id>/`. The `latest.json` pointer changes only after all
  referenced audio and the database have uploaded successfully.
- A missing local audio file is fetched into an atomic local cache entry before
  serving. Normal HTTP byte-range playback and downloads continue to work.
- Existing local files play during an S3 outage. An unavailable uncached file
  returns 503; an absent remote file returns 404. Failed syncs retain local data
  and the last good recovery pointer, and retry at the next scheduled interval.
- No local cache or remote snapshots are automatically deleted. Configure storage
  provider retention separately after establishing recovery requirements. Do not
  add a blanket lifecycle rule that expires audio still referenced by snapshots.
- Recovery point is the last successful snapshot, not the latest local vote or
  newly generated song. Check timestamps before claiming data is protected.
- Models, application binaries, credentials, configuration, temporary voice
  samples and derived spectrogram images are not part of these snapshots. Keep
  reproducible deployment/model assets separately; spectrograms are regenerable.
- A single object is limited to 512 MiB. Oversized/missing referenced files stop
  publication of a new snapshot. The normal generated tracks are much smaller.

`GET /api/storage/status` reports backend, sync state, last successful snapshot
and protected audio count. It exposes no keys, endpoint or filesystem paths.
Use the existing `./start.sh` entry point to run the app and its scheduler. A
custom WSGI deployment must explicitly arrange one snapshot scheduler; importing
`app` alone does not start workers or the scheduler.

## Manual qualification and recovery

Load the protected environment in your shell or service manager. For qualification,
use a separate prefix so test snapshots never replace production's recovery point.
The CLI needs only the optional S3 SDK, not Torch or a GPU.

```sh
python3 scripts/storage_snapshot.py snapshot \
  --database /path/to/soundbox.db --audio-dir /path/to/generated \
  --metadata /path/to/generations.json
python3 scripts/storage_snapshot.py restore \
  --destination /path/to/new-empty-location
```

The destination must not exist. Restore downloads the manifest, verifies its
hash, restores `soundbox.db`, runs SQLite integrity checks, verifies every
referenced audio object, and writes `restore-receipt.json` only after success.
An interrupted/failed restore leaves an incomplete directory for inspection;
never point the application at it. Retry to a new directory.

To recover a failed Soundbox host:

1. Provision the pinned Soundbox release and models, and restore the protected
   S3 configuration using your credential recovery process.
2. Restore into a new directory. Inspect the receipt, generation/vote counts and
   SQLite integrity. Play representative music and SFX from restored storage.
3. With the old writer stopped, configure `DB_PATH` and the generated-directory
   volume to use the restored files. Start the app with `./start.sh` or Compose.
4. Verify `/api/storage/status`, library contents, ratings and playback. Keep
   the old data and prior image until recovery is accepted.

Use the provider's own replication and metadata-recovery procedures if its host
fails. Soundbox snapshots cannot recover an S3 cluster whose own metadata and
replicas were lost. Replication configuration alone is not a restore test.

## Tests

Install `boto3==1.43.113` and `moto[s3]==5.2.4` in a test venv, then run:

```sh
python3 -m pytest tests/test_object_storage.py
```

Tests cover real S3 SDK requests under Moto, consistent database/ratings restore,
immutable objects, changed votes, missing local files, corruption rejection,
failed snapshot publication, traversal prevention, local mode, and the actual
Flask audio route with Range requests and outage fallback.

For a live compatible provider, snapshot a consistent copy of the instance into a
qualification prefix, restore on another host into an empty directory, compare
all SQLite tables and every audio SHA-256. Then qualify a production cache miss
with a reversible local-file backup, verify HTTP 206 and matching bytes, and
confirm the next scheduled snapshot includes a newly completed generation.

SDK references: [S3 transfers](https://docs.aws.amazon.com/boto3/latest/guide/s3.html)
and [PutObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).
