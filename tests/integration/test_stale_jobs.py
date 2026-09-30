"""A restarted app must not let orphaned job rows block project cleanup."""
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import RenderJob
from app.workers import jobs

checks = 0


def check(name, ok):
    global checks
    assert ok, name
    checks += 1
    print('PASS ' + name, flush=True)


with TestClient(app) as client:
    project = client.post('/api/projects', json={'title': 'Interrupted jobs'}).json()
    with SessionLocal() as db:
        stale = [RenderJob(project_id=project['id'], scope='part', status=status)
                 for status in ('queued', 'running', 'cancelling')]
        db.add_all(stale)
        db.commit()
        stale_ids = [job.id for job in stale]

    check('restart recovery closes queued, running, and cancelling jobs', jobs.recover_interrupted_jobs() == 3)
    with SessionLocal() as db:
        recovered = [db.get(RenderJob, job_id) for job_id in stale_ids]
        check('recovered jobs retain an actionable interrupted status',
              all(job.status == 'failed' and job.stage == 'interrupted' and 'Start the render' in job.error
                  for job in recovered))
    check('project deletion succeeds after its stale render rows are recovered',
          client.delete('/api/projects/' + project['id']).status_code == 200)

    open_editor_project = client.post('/api/projects', json={'title': 'Stale job while editor stays open'}).json()
    with SessionLocal() as db:
        db.add(RenderJob(project_id=open_editor_project['id'], scope='full_export', status='running'))
        db.commit()
    check('project deletion recovers a stale job without restarting SceneForge',
          client.delete('/api/projects/' + open_editor_project['id']).status_code == 200)

    active_project = client.post('/api/projects', json={'title': 'Active job protection'}).json()
    with SessionLocal() as db:
        active = RenderJob(project_id=active_project['id'], scope='full_export', status='running')
        db.add(active)
        db.commit()
        active_id = active.id
    jobs._active_jobs.add(active_id)
    try:
        check('recovery leaves a job that is live in this process alone', jobs.recover_interrupted_jobs() == 0)
        check('project deletion remains protected while a render is live',
              client.delete('/api/projects/' + active_project['id']).status_code == 409)
    finally:
        jobs._active_jobs.discard(active_id)

    # End to end with a real FFmpeg render. The worker is held at a gate so the delete
    # deterministically lands while the job is live (reserved before its row existed).
    image = pathlib.Path(tmp.name) / 'still.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=teal:s=320x180', '-frames:v', '1', str(image)], check=True)
    real = client.post('/api/projects', json={'title': 'Real render protection', 'aspect': '16:9', 'fps': 25}).json()
    asset = client.post(f"/api/assets/upload?project_id={real['id']}", files={'file': ('still.png', image.read_bytes(), 'image/png')}).json()
    scene_id = client.get('/api/projects/' + real['id']).json()['scenes'][0]['id']
    client.post(f'/api/scenes/{scene_id}/shots', json={'asset_id': asset['id']}).raise_for_status()
    client.patch(f'/api/scenes/{scene_id}', json={'timing_mode': 'fixed', 'requested_duration_ms': 1000})
    gate, original = threading.Event(), jobs._run_part_job
    def gated(*args):
        gate.wait(30)
        return original(*args)
    jobs._run_part_job = gated
    try:
        job_id = client.post(f'/api/scenes/{scene_id}/render').json()['job_id']
        check('a real render in progress blocks project deletion', client.delete('/api/projects/' + real['id']).status_code == 409)
        check('the blocked delete leaves the render job intact', client.get(f'/api/jobs/{job_id}').json()['status'] in ('queued', 'running'))
    finally:
        jobs._run_part_job = original
        gate.set()
    for _ in range(600):
        status = client.get(f'/api/jobs/{job_id}').json()['status']
        if status in ('succeeded', 'failed', 'cancelled'):
            break
        time.sleep(0.1)
    check('the real render finishes with FFmpeg and releases its live slot', status == 'succeeded' and job_id not in jobs.active_job_ids())
    check('the project can be deleted after its render finishes', client.delete('/api/projects/' + real['id']).status_code == 200)

print(f'{checks} stale-job checks passed')
