"""Warmup protocol failure classification; no network, Docker or model downloads."""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
root=Path(__file__).resolve().parents[2]
temp=tempfile.TemporaryDirectory()
os.environ['SCENEFORGE_DATA_DIR']=temp.name
sys.path.insert(0,str(root/'backend'))
from app import managed_ai as m
# Owner diagnostic: an old/incompatible service returns HTTP 404 at /warmup.
# This must not be presented as a failed model download or retried automatically.
import requests
for status in (404,405):
    response=requests.Response();response.status_code=status
    failure=requests.HTTPError('Endpoint unavailable',response=response)
    fake_session=MagicMock();fake_session.__enter__.return_value=fake_session
    fake_session.post.return_value.raise_for_status.side_effect=failure
    with patch.object(m,'session',return_value=fake_session),patch.object(m,'health') as health,patch.object(m.time,'sleep') as sleep:
        try:m.warmup_with_retry('chatterbox',['docker','compose'])
        except RuntimeError as exc:
            assert 'POST /warmup' in str(exc) and str(status) in str(exc)
            assert 'Cached models are retained' in str(exc)
            assert 'model loading failed' not in str(exc)
        else:raise AssertionError('Missing setup endpoint must fail clearly')
        assert fake_session.post.call_count==1
        health.assert_not_called();sleep.assert_not_called()
print('PASS missing warmup endpoint is explained as a service mismatch, without automatic retries or model-download blame')
# Genuine model failures still retain the engine's cause.
response=requests.Response();response.status_code=503
failure=requests.HTTPError('Unavailable',response=response)
fake_session=MagicMock();fake_session.__enter__.return_value=fake_session
fake_session.post.return_value.raise_for_status.side_effect=failure
with patch.object(m,'session',return_value=fake_session),patch.object(m,'health',return_value={'last_error':'CUDA out of memory'}),patch.object(m.time,'sleep') as sleep:
    try:m.warmup_with_retry('chatterbox',['docker','compose'])
    except RuntimeError as exc:assert 'CUDA out of memory' in str(exc)
    else:raise AssertionError('Model failure must remain visible')
    assert fake_session.post.call_count==1
    sleep.assert_not_called()
print('PASS actual model failure retains its cause; memory errors are not retried')
