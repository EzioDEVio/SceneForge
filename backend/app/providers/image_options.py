"""Hosted allowance-based images and an explicitly local AUTOMATIC1111 adapter."""
import base64
import io
from urllib.parse import urlsplit

import requests
from app.providers.openai_image import ImageProviderError


def local_url(value):
    url = urlsplit(value or 'http://127.0.0.1:7860')
    if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1')
            or url.username or url.password or url.query or url.fragment or url.path not in ('', '/')):
        raise ValueError('Local image service must be an HTTP localhost URL, such as http://127.0.0.1:7860.')
    try: url.port
    except ValueError: raise ValueError('Invalid local service port.')
    return (value or 'http://127.0.0.1:7860').rstrip('/')


def _decode(value):
    try:
        if value.startswith('data:'): value = value.split(',', 1)[1]
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError, AttributeError):
        raise ImageProviderError('The image service returned an invalid image payload.')


def generate(profile, key, prompt, size, options=None):
    width, height = map(int, size.split('x'))
    try:
        if profile.name == 'together':
            response = requests.post('https://api.together.xyz/v1/images/generations',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={'model': profile.model or 'black-forest-labs/FLUX.1-schnell-Free', 'prompt': prompt,
                      'width': width, 'height': height, 'n': 1, 'response_format': 'b64_json'}, timeout=(10, 180))
        elif profile.name == 'huggingface':
            from huggingface_hub import InferenceClient
            # A HF token routes billing through HF, including any available credits.
            client = InferenceClient(provider='auto', api_key=key, timeout=180)
            image = client.text_to_image(prompt, model=profile.model or 'black-forest-labs/FLUX.1-schnell', width=width, height=height)
            buffer = io.BytesIO(); image.save(buffer, format='PNG')
            return buffer.getvalue()
        elif profile.name == 'cloudflare':
            if len(prompt) > 2048:
                raise ImageProviderError('Cloudflare prompts must contain at most 2,048 characters.')
            endpoint = f'https://api.cloudflare.com/client/v4/accounts/{profile.base_url}/ai/run/@cf/black-forest-labs/flux-1-schnell'
            response = requests.post(endpoint, headers={'Authorization': f'Bearer {key}'}, json={'prompt': prompt, 'steps': 4}, timeout=(10,180))
        else:
            endpoint = local_url(profile.base_url) + '/sdapi/v1/txt2img'
            opts = options or {}
            base = 1024 if opts.get('family') == 'sdxl' else 512
            width, height = ((base, base) if width == height else ((base * 3 // 2, base) if width > height else (base, base * 3 // 2)))
            payload = {'prompt': prompt, 'width': width, 'height': height, 'steps': opts.get('steps', 30),
                       'cfg_scale': opts.get('cfg_scale', 7), 'seed': opts.get('seed', -1),
                       'negative_prompt': opts.get('negative_prompt', ''), 'sampler_name': 'DPM++ 2M',
                       'batch_size': 1, 'n_iter': 1}
            if opts.get('hires'):
                payload.update(enable_hr=True, hr_scale=1.5, hr_upscaler='Latent', denoising_strength=0.35, hr_second_pass_steps=15)
            if profile.model and profile.model != 'current':
                payload.update(override_settings={'sd_model_checkpoint': profile.model}, override_settings_restore_afterwards=True)
            session = requests.Session(); session.trust_env = False
            response = session.post(endpoint, json=payload, timeout=(10,600), allow_redirects=False)
        if not response.ok or response.is_redirect:
            code = response.status_code
            hints = {401:'Check your API token.',403:'Check token permissions and model access.',402:'Free credits may be exhausted. Check your provider account.',429:'Provider limit reached. Wait or check your allowance.'}
            raise ImageProviderError(f'Image service returned HTTP {code}. '+hints.get(code,'Check that the engine/model is available.'))
        data = response.json()
        if profile.name == 'cloudflare':
            return _decode(data['result']['image'])
        if profile.name == 'together':
            item = data.get('data', [{}])[0]
            return _decode(item['b64_json'])
        return _decode(data['images'][0])
    except ImageProviderError: raise
    except requests.Timeout: raise ImageProviderError('Image generation timed out. The local model may still be loading; check its window before retrying.')
    except requests.ConnectionError: raise ImageProviderError('Cannot connect to the image service. For local generation, start AUTOMATIC1111 with --api and a downloaded image model.')
    except ImportError: raise ImageProviderError('Hugging Face support needs the updated dependencies. Stop SceneForge and run scripts/setup.bat, then restart.')
    except Exception:
        # Never expose exception URLs/headers/tokens in a browser error.
        raise ImageProviderError('Image generation failed. Check model availability, token permissions and remaining provider credits. No alternative provider was charged.')
