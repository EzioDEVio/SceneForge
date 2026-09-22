"""Validate request limits and AUTOMATIC1111 payloads without a GPU."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.domain.schemas import GenerateImageRequest
from app.providers.image_options import generate
from pydantic import ValidationError
profile=SimpleNamespace(name='local_sd',base_url='http://127.0.0.1:7860',model='current')
with patch('app.providers.image_options.requests.Session') as session:
    response=MagicMock(ok=True,is_redirect=False)
    response.json.return_value={'images':['aW1hZ2U=']}
    session.return_value.post.return_value=response
    for family,base in [('sd15',512),('sdxl',1024)]:
        body=GenerateImageRequest(prompt='A lab',local_options={'family':family,'hires':True,'seed':42})
        assert generate(profile,'','A lab','1536x1024',body.local_options.model_dump())==b'image'
        payload=session.return_value.post.call_args.kwargs['json']
        assert (payload['width'],payload['height'])==(base*3//2,base)
        assert payload['enable_hr'] and payload['seed']==42 and payload['steps']==30
        assert payload['denoising_strength']==.35
    assert session.return_value.trust_env is False
for options in [{'steps':1000},{'cfg_scale':100},{'family':'invalid'},{'seed':-5}]:
    try: GenerateImageRequest(prompt='test',local_options=options)
    except ValidationError: pass
    else: raise AssertionError(options)
print('PASS SD15/SDXL dimensions, refinement, seed, sampler settings and validation')
