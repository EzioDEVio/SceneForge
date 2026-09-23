"""Kokoro and the bundled Chatterbox bridge share an OpenAI-shaped audio API."""
import requests
from app.security.secrets import reveal


def connection(profile):
    base = (profile.base_url or '').rstrip('/')
    if not base.endswith('/v1'): base += '/v1'
    key = reveal(profile.secret_ref or '')
    if profile.name == 'elevenlabs':
        return base, ({'xi-api-key': key} if key else {})
    return base, ({'Authorization': f'Bearer {key}'} if key else {})


def list_voices(profile):
    if profile.name == 'elevenlabs':
        base, headers = connection(profile)
        try:
            res = requests.get(base + '/voices', headers=headers, timeout=(5, 20), allow_redirects=False)
            if not res.ok: raise ValueError(f'ElevenLabs returned HTTP {res.status_code}. Check the API key.')
            return [str(v['voice_id']) for v in res.json().get('voices', []) if v.get('voice_id')]
        except (requests.RequestException, KeyError, TypeError):
            raise ValueError('ElevenLabs voice list unavailable. Check the API key.')
    base, headers = connection(profile)
    try:
        res = requests.get(base + '/audio/voices', headers=headers, timeout=(5, 15), allow_redirects=False)
        if not res.ok: raise ValueError(f'Voice service returned HTTP {res.status_code}. Check the service URL.')
        values = res.json().get('voices', [])
        return [v if isinstance(v, str) else str(v['id']) for v in values]
    except (requests.RequestException, KeyError, TypeError):
        raise ValueError('Voice service unavailable. Start it and check its address in Settings.')


def synthesize(profile, text, voice, language, speed):
    if profile.name == 'elevenlabs':
        base, headers = connection(profile)
        try:
            res = requests.post(base + '/text-to-speech/' + voice,
                json={'text': text, 'model_id': profile.model or 'eleven_multilingual_v2',
                      'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'speed': speed}},
                headers={**headers, 'Accept': 'audio/wav', 'Content-Type': 'application/json'},
                timeout=(10, 600), allow_redirects=False)
            if not res.ok: raise ValueError(f'ElevenLabs returned HTTP {res.status_code}. Check key, voice and quota.')
            return res.content
        except requests.RequestException:
            raise ValueError('ElevenLabs is unavailable or timed out.')
    if profile.name == 'kokoro' and (language == 'ar' or any('\u0600' <= c <= '\u06ff' for c in text)):
        raise ValueError('Kokoro does not support Arabic. Select Chatterbox Multilingual for Arabic narration.')
    if any('\u0600' <= c <= '\u06ff' for c in text) and language != 'ar':
        raise ValueError('This script contains Arabic. Select Arabic for narration; the app will not silently use an English voice.')
    base, headers = connection(profile)
    payload = {'model': profile.model or profile.name, 'input': text, 'voice': voice,
               'speed': speed, 'response_format': 'wav'}
    if profile.name == 'chatterbox': payload['language'] = language
    if profile.name == 'kokoro':
        codes = {'en':'ab','fr':'f','es':'e','hi':'h','it':'i','ja':'j','pt':'p','zh':'z'}
        if language not in codes or not voice or voice[0] not in codes[language]:
            raise ValueError('Select a Kokoro voice matching a supported language.')
        payload['lang_code'] = voice[0]
    try:
        res = requests.post(base + '/audio/speech', json=payload, headers=headers, timeout=(10, 600), allow_redirects=False)
        if not res.ok:
            detail = ''
            if profile.name == 'chatterbox':
                try: detail = str(res.json().get('detail', ''))[:800]
                except ValueError: pass
            raise ValueError(detail or f'Voice generation returned HTTP {res.status_code}. Run DIAGNOSE_VOICE.bat and check model installation.')
        if len(res.content) > 100 * 1024 * 1024: raise ValueError('Voice response is too large. Split the script into shorter scenes.')
        return res.content
    except requests.RequestException:
        raise ValueError('Voice service unavailable or timed out. Check the service log before retrying.')
