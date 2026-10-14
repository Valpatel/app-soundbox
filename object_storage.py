"""Optional S3-compatible audio backing store and consistent recovery snapshots.

SQLite remains local. Snapshots use SQLite's online backup API; a manifest is
published only after every referenced audio object and the database are uploaded.
Credentials are read by the standard AWS credential provider chain, never returned
by the application. No local files or remote objects are automatically deleted.
"""
from datetime import datetime, timezone
import hashlib
import base64
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import uuid
from urllib.parse import urlsplit

LOG = logging.getLogger(__name__)
MAX_OBJECT_BYTES = 512 * 1024 * 1024


class StorageError(RuntimeError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audio_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,190}\.wav', name):
        raise StorageError('Invalid audio filename')
    return name


class S3Store:
    def __init__(self, client, bucket, prefix='soundbox'):
        if not bucket or not re.fullmatch(r'[A-Za-z0-9/_-]+', prefix.strip('/')):
            raise StorageError('Configure an S3 bucket and a simple nonempty key prefix')
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip('/')
        self.lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.status = {'backend': 's3', 'state': 'not_synced', 'last_success': None}

    @classmethod
    def from_env(cls):
        backend = os.environ.get('SOUNDBOX_STORAGE', 'local')
        if backend == 'local':
            return None
        if backend != 's3':
            raise StorageError('SOUNDBOX_STORAGE must be local or s3')
        endpoint = os.environ.get('SOUNDBOX_S3_ENDPOINT_URL') or None
        if endpoint:
            parsed = urlsplit(endpoint)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise StorageError('Use an HTTP(S) endpoint without embedded credentials')
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', endpoint_url=endpoint,
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
            config=Config(signature_version='s3v4', connect_timeout=5, read_timeout=30,
                retries={'max_attempts': 2, 'mode': 'standard'},
                s3={'addressing_style': os.environ.get('SOUNDBOX_S3_ADDRESSING_STYLE', 'path')},
                request_checksum_calculation='when_required', response_checksum_validation='when_required'))
        return cls(client, os.environ.get('SOUNDBOX_S3_BUCKET'), os.environ.get('SOUNDBOX_S3_PREFIX', 'soundbox'))

    def key(self, suffix):
        return self.prefix + '/' + suffix

    def head(self, key):
        from botocore.exceptions import ClientError
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
                return None
            raise

    def upload(self, path, key):
        path = Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_OBJECT_BYTES:
            raise StorageError('Unsafe or oversized source object')
        sha = digest(path)
        size = path.stat().st_size
        previous = self.head(key)
        if previous:
            if previous.get('Metadata', {}).get('sha256') != sha or previous['ContentLength'] != size:
                raise StorageError('Immutable object differs from existing S3 object')
        else:
            with path.open('rb') as source:
                md5 = base64.b64encode(hashlib.file_digest(source, 'md5').digest()).decode()
            with path.open('rb') as body:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=body,
                    ContentLength=size, ContentMD5=md5, Metadata={'sha256': sha},
                    ContentType='audio/wav' if path.suffix == '.wav' else 'application/octet-stream')
            verified = self.head(key)
            if not verified or verified['ContentLength'] != size or verified.get('Metadata', {}).get('sha256') != sha:
                raise StorageError('Uploaded object metadata verification failed')
        return {'key': key, 'sha256': sha, 'bytes': size}

    def download(self, key, target, expected=None):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        sha = (expected or {}).get('sha256') or response.get('Metadata', {}).get('sha256')
        size = response.get('ContentLength', 0)
        if not sha or not re.fullmatch('[a-f0-9]{64}', sha) or size > MAX_OBJECT_BYTES:
            response['Body'].close()
            raise StorageError('Missing integrity metadata or oversized remote object')
        if expected and size != expected['bytes']:
            response['Body'].close()
            raise StorageError('Remote object size differs from snapshot')
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.soundbox-', delete=False) as out:
                temp = Path(out.name)
                written = 0
                for chunk in iter(lambda: response['Body'].read(1024 * 1024), b''):
                    written += len(chunk)
                    if written > MAX_OBJECT_BYTES:
                        raise StorageError('Remote object exceeds size bound')
                    out.write(chunk)
            if written != size or digest(temp) != sha:
                raise StorageError('Remote object checksum mismatch')
            temp.replace(target)
        finally:
            response['Body'].close()
            if temp and temp.exists():
                temp.unlink()

    def ensure_audio(self, directory, filename):
        filename = audio_name(filename)
        directory = Path(directory).resolve()
        target = directory / filename
        if target.is_symlink():
            raise StorageError('Symlink cache entry refused')
        if target.is_file():
            return target
        with self.cache_lock:
            if not target.is_file():
                key = self.key('audio/' + filename)
                if not self.head(key):
                    return None
                self.download(key, target)
        return target

    def snapshot(self, database, directory, metadata=None):
        """Single-writer snapshot; publish latest only after complete upload."""
        if not self.lock.acquire(blocking=False):
            return None
        self.status['state'] = 'syncing'
        try:
            directory = Path(directory).resolve()
            database = Path(database).resolve()
            if not database.is_file():
                raise StorageError('Source database does not exist')
            with tempfile.TemporaryDirectory(prefix='soundbox-snapshot-') as temp:
                local_db = Path(temp) / 'soundbox.db'
                with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
                    with sqlite3.connect(local_db) as dest:
                        source.backup(dest)
                        if dest.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise StorageError('Database integrity check failed')
                        filenames = [row[0] for row in dest.execute(
                            "SELECT DISTINCT filename FROM generations WHERE filename IS NOT NULL AND filename != ''")]
                assets = {}
                for filename in filenames:
                    filename = audio_name(filename)
                    path = directory / filename
                    key = self.key('audio/' + filename)
                    if path.is_file():
                        assets[filename] = self.upload(path, key)
                    else:
                        remote = self.head(key)
                        if not remote or not remote.get('Metadata', {}).get('sha256'):
                            raise StorageError('Referenced audio has no local or remote copy')
                        assets[filename] = {'key': key, 'sha256': remote['Metadata']['sha256'], 'bytes': remote['ContentLength']}
                snapshot_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
                database_object = self.upload(local_db, self.key('snapshots/' + snapshot_id + '/soundbox.db'))
                legacy_object = None
                if metadata and Path(metadata).is_file():
                    legacy = Path(temp) / 'generations.json'
                    legacy.write_text(json.dumps(json.loads(Path(metadata).read_text()), sort_keys=True))
                    legacy_object = self.upload(legacy, self.key('snapshots/' + snapshot_id + '/generations.json'))
                manifest = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                            'snapshot_id': snapshot_id, 'database': database_object, 'audio': assets,
                            'legacy_metadata': legacy_object}
                content = json.dumps(manifest, sort_keys=True).encode()
                # Immutable manifest first, then a replaceable discovery pointer.
                manifest_key = self.key('snapshots/' + snapshot_id + '/manifest.json')
                self.client.put_object(Bucket=self.bucket, Key=manifest_key, Body=content, ContentType='application/json')
                pointer = json.dumps({'manifest': manifest_key, 'sha256': hashlib.sha256(content).hexdigest()}).encode()
                self.client.put_object(Bucket=self.bucket, Key=self.key('snapshots/latest.json'), Body=pointer, ContentType='application/json')
                self.status = {'backend': 's3', 'state': 'synced', 'last_success': manifest['created_at'],
                               'snapshot_id': snapshot_id, 'audio_objects': len(assets)}
                return manifest
        except Exception:
            self.status['state'] = 'error'
            LOG.exception('Soundbox S3 snapshot failed; local data retained')
            raise
        finally:
            self.lock.release()

    def read_json(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            data = response['Body'].read(16 * 1024 * 1024 + 1)
            if len(data) > 16 * 1024 * 1024:
                raise StorageError('Oversized snapshot manifest')
            return json.loads(data), data
        finally:
            response['Body'].close()

    def restore(self, destination):
        """Restore to a NEW directory, never overwrite a running installation."""
        destination = Path(destination)
        if destination.exists():
            raise StorageError('Restore destination must not exist')
        pointer, _ = self.read_json(self.key('snapshots/latest.json'))
        manifest_key = pointer['manifest']
        if not manifest_key.startswith(self.key('snapshots/')):
            raise StorageError('Snapshot pointer is outside configured prefix')
        manifest, content = self.read_json(manifest_key)
        if hashlib.sha256(content).hexdigest() != pointer['sha256'] or manifest.get('version') != 1:
            raise StorageError('Snapshot manifest integrity failed')
        destination.mkdir(parents=True)
        db_meta = manifest['database']
        if not db_meta['key'].startswith(self.key('snapshots/')):
            raise StorageError('Database object is outside snapshot prefix')
        self.download(db_meta['key'], destination / 'soundbox.db', db_meta)
        with sqlite3.connect(destination / 'soundbox.db') as restored:
            if restored.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise StorageError('Restored database is corrupt')
            references = {r[0] for r in restored.execute("SELECT DISTINCT filename FROM generations WHERE filename IS NOT NULL AND filename != ''")}
        if references != set(manifest['audio']):
            raise StorageError('Manifest does not cover database audio references')
        for filename, meta in manifest['audio'].items():
            filename = audio_name(filename)
            if meta['key'] != self.key('audio/' + filename):
                raise StorageError('Audio object is outside configured prefix')
            self.download(meta['key'], destination / 'generated' / filename, meta)
        legacy = manifest.get('legacy_metadata')
        if legacy:
            if not legacy['key'].startswith(self.key('snapshots/')):
                raise StorageError('Legacy metadata is outside snapshot prefix')
            self.download(legacy['key'], destination / 'generations.json', legacy)
        (destination / 'restore-receipt.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
