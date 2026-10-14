import ast
import json
from pathlib import Path
import sqlite3
from unittest.mock import Mock
import boto3
from flask import Flask, jsonify, send_file
from moto import mock_aws
import pytest
from object_storage import S3Store, StorageError, digest


@pytest.fixture
def storage(tmp_path):
    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket='soundbox-test')
        store = S3Store(client, 'soundbox-test', 'instance')
        audio = tmp_path / 'generated'
        audio.mkdir()
        (audio / 'abc12345.wav').write_bytes(b'RIFFtest-audio')
        database = tmp_path / 'soundbox.db'
        with sqlite3.connect(database) as db:
            db.executescript("""
                CREATE TABLE generations (id TEXT, filename TEXT, upvotes INTEGER, downvotes INTEGER);
                INSERT INTO generations VALUES ('abc12345', 'abc12345.wav', 4, 1);
                CREATE TABLE votes (user_id TEXT, generation_id TEXT, vote INTEGER);
                INSERT INTO votes VALUES ('listener', 'abc12345', 1);
                CREATE TABLE playlists (name TEXT);
                INSERT INTO playlists VALUES ('Favorites');
            """)
        yield store, database, audio


def test_snapshot_restore_preserves_audio_ratings_and_playlists(storage, tmp_path):
    store, database, audio = storage
    manifest = store.snapshot(database, audio)
    restored = tmp_path / 'restored'
    result = store.restore(restored)
    assert result['snapshot_id'] == manifest['snapshot_id']
    assert (restored / 'generated/abc12345.wav').read_bytes() == (audio / 'abc12345.wav').read_bytes()
    with sqlite3.connect(restored / 'soundbox.db') as db:
        assert db.execute('SELECT upvotes, downvotes FROM generations').fetchone() == (4, 1)
        assert db.execute('SELECT * FROM votes').fetchall() == [('listener', 'abc12345', 1)]
        assert db.execute('SELECT * FROM playlists').fetchall() == [('Favorites',)]
    assert store.status['state'] == 'synced'
    with pytest.raises(StorageError, match='must not exist'):
        store.restore(restored)


def test_missing_local_audio_hydrates_and_cached_playback_survives_outage(storage, tmp_path):
    store, database, audio = storage
    store.snapshot(database, audio)
    cache = tmp_path / 'empty-cache'
    result = store.ensure_audio(cache, 'abc12345.wav')
    assert digest(result) == digest(audio / 'abc12345.wav')
    store.client = Mock(side_effect=RuntimeError('offline'))
    assert store.ensure_audio(cache, 'abc12345.wav') == result


def test_changed_ratings_produce_new_consistent_snapshot(storage, tmp_path):
    store, database, audio = storage
    first = store.snapshot(database, audio)
    with sqlite3.connect(database) as db:
        db.execute('UPDATE generations SET downvotes=7')
    second = store.snapshot(database, audio)
    assert first['snapshot_id'] != second['snapshot_id']
    store.restore(tmp_path / 'latest')
    with sqlite3.connect(tmp_path / 'latest/soundbox.db') as db:
        assert db.execute('SELECT downvotes FROM generations').fetchone()[0] == 7
    assert len(store.client.list_objects_v2(Bucket=store.bucket, Prefix=store.key('audio/'))['Contents']) == 1


def test_failed_snapshot_never_replaces_good_latest(storage):
    store, database, audio = storage
    first = store.snapshot(database, audio)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO generations VALUES ('missing', 'missing.wav', 0, 0)")
    with pytest.raises(StorageError, match='no local or remote copy'):
        store.snapshot(database, audio)
    pointer, _ = store.read_json(store.key('snapshots/latest.json'))
    assert first['snapshot_id'] in pointer['manifest']
    assert store.status['state'] == 'error'


def test_corrupted_object_is_never_published_as_cache(storage, tmp_path):
    store, database, audio = storage
    manifest = store.snapshot(database, audio)
    meta = manifest['audio']['abc12345.wav']
    store.client.put_object(Bucket=store.bucket, Key=meta['key'], Body=b'corrupt', Metadata={'sha256': meta['sha256']})
    with pytest.raises(StorageError, match='checksum'):
        store.ensure_audio(tmp_path / 'cache', 'abc12345.wav')
    assert not (tmp_path / 'cache/abc12345.wav').exists()


def test_immutable_audio_cannot_be_overwritten(storage):
    store, database, audio = storage
    store.snapshot(database, audio)
    (audio / 'abc12345.wav').write_bytes(b'changed')
    with pytest.raises(StorageError, match='Immutable'):
        store.snapshot(database, audio)


@pytest.mark.parametrize('name', ['../file.wav', '/file.wav', 'sub/file.wav', 'file.mp3', '..wav'])
def test_unsafe_names_rejected(storage, name):
    store, _, audio = storage
    with pytest.raises(StorageError):
        store.ensure_audio(audio, name)


def test_local_mode_does_not_construct_s3_client(monkeypatch):
    monkeypatch.setenv('SOUNDBOX_STORAGE', 'local')
    assert S3Store.from_env() is None


def test_actual_audio_route_hydrates_and_preserves_ranges(storage, tmp_path):
    store, database, audio = storage
    store.snapshot(database, audio)
    cache = tmp_path / 'playback-cache'
    cache.mkdir()
    app = Flask(__name__)
    import os
    ns = dict(app=app, object_store=store, OUTPUT_DIR=str(cache), os=os, jsonify=jsonify,
              send_file=send_file, is_safe_filename=lambda name: '/' not in name and '..' not in name)
    source = Path(__file__).resolve().parents[1] / 'app.py'
    nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name in ('hydrate_audio', 'serve_audio', 'storage_status')]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    response = app.test_client().get('/audio/abc12345.wav', headers={'Range': 'bytes=0-3'})
    assert response.status_code == 206 and response.data == b'RIFF'
    assert app.test_client().get('/audio/no-such.wav').status_code == 404
    status = app.test_client().get('/api/storage/status').json
    assert 'bucket' not in status and 'credentials' not in status
    store.client = Mock()
    store.client.head_object.side_effect = RuntimeError('offline')
    assert app.test_client().get('/audio/uncached.wav').status_code == 503
    assert app.test_client().get('/audio/abc12345.wav').status_code == 200


def test_legacy_star_ratings_are_restored(storage, tmp_path):
    store, database, audio = storage
    metadata = tmp_path / 'generations.json'
    metadata.write_text(json.dumps({'abc12345.wav': {'prompt': 'Test music', 'rating': 5}}))
    store.snapshot(database, audio, metadata)
    store.restore(tmp_path / 'legacy-restored')
    assert json.loads((tmp_path / 'legacy-restored/generations.json').read_text()) == json.loads(metadata.read_text())


def test_endpoint_rejects_embedded_credentials(monkeypatch):
    monkeypatch.setenv('SOUNDBOX_STORAGE', 's3')
    monkeypatch.setenv('SOUNDBOX_S3_ENDPOINT_URL', 'https://user:secret@example.com')
    with pytest.raises(StorageError, match='without embedded credentials'):
        S3Store.from_env()


def test_atomic_metadata_save_preserves_previous_ratings_on_failure(tmp_path, monkeypatch):
    import os
    import uuid
    target = tmp_path / 'data/generations.json'
    source = Path(__file__).resolve().parents[1] / 'app.py'
    nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name == 'save_metadata']
    ns = dict(METADATA_FILE=str(target), os=os, uuid=uuid, json=json)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    ns['save_metadata']({'track': {'rating': 5}})
    def fail_replace(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError):
        ns['save_metadata']({'track': {'rating': 1}})
    assert json.loads(target.read_text()) == {'track': {'rating': 5}}
    assert list(target.parent.iterdir()) == [target]
