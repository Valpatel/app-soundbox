import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
import pytest
from radio_generation import install_radio_generation


@pytest.fixture
def radio():
    app=Flask(__name__)
    class DB:
        tracks=[]
        def get_random_tracks_excluding(self, **kw):
            return [t for t in self.tracks if t['id'] not in kw['exclude_ids']]
    db=DB(); jobs={}; calls=[]
    def generate():
        calls.append(dict(request.json))
        if request.headers.get('X-Test-Deny'):
            return jsonify(error='Admission denied'),429
        job_id=str(len(calls));jobs[job_id]={'id':job_id,'status':'queued'}
        return jsonify(job_id=job_id)
    install_radio_generation(app,db,jobs,threading.Lock(),generate)
    return app,db,jobs,calls


def test_existing_tracks_prevent_generation(radio):
    app,db,jobs,calls=radio;db.tracks=[{'id':'old'}]
    r=app.test_client().post('/api/radio/fill',json={'station':'ambient'})
    assert r.json['tracks']==db.tracks and not calls
    r=app.test_client().post('/api/radio/fill',json={'station':'ambient','exclude':['old']})
    assert r.status_code==202 and calls[0]['duration']==90
    assert calls[0]['model']=='music'
    assert 'ambient' in calls[0]['prompt']


def test_concurrent_station_requests_share_one_admission(radio):
    app,db,jobs,calls=radio
    def request_fill(_):
        with app.test_client() as client:
            return client.post('/api/radio/fill',json={'station':'piano'}).json['job_id']
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(request_fill,range(12)))
    assert len(set(ids))==1 and len(calls)==1
    jobs[ids[0]]['status']='completed';db.tracks=[{'id':ids[0]}]
    assert app.test_client().post('/api/radio/fill',json={'station':'piano'}).json['tracks']==db.tracks


def test_validation_and_existing_admission_failure(radio):
    app,db,jobs,calls=radio;c=app.test_client()
    assert c.post('/api/radio/fill',data='{}').status_code==415
    for payload in [[],{'station':[]},{'station':{}},{'station':'favorites'},{'station':'ambient','exclude':'bad'},
                    {'station':'ambient','exclude':['x']*101},{'station':'ambient','exclude':[{}]}]:
        assert c.post('/api/radio/fill',json=payload).status_code==400
    assert not calls
    assert c.post('/api/radio/fill',json={'station':'happy'},headers={'X-Test-Deny':'1'}).status_code==429
    assert not jobs


def test_failure_can_be_retried_but_unrelated_station_not_reused(radio):
    app,db,jobs,calls=radio;c=app.test_client()
    first=c.post('/api/radio/fill',json={'station':'piano'}).json['job_id']
    second=c.post('/api/radio/fill',json={'station':'retro'}).json['job_id']
    assert second!=first
    jobs[first]['status']='failed'
    assert c.post('/api/radio/fill',json={'station':'piano'}).json['job_id']!=first
