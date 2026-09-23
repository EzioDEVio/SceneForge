"""Kokoro and the bundled Chatterbox bridge share an OpenAI-shaped audio API."""
import requests
from app.security.secrets import reveal


def connection(profile):
    base = (profile.base_url or '').rstrip('/')
    if not base.endswith('/v1'): base += '/v1'
    key = reveal(profile.secret_ref or '')
    if profile.name == 'elevenlabs':
        return 'https://api.elevenlabs.io/v1', ({'xi-api-key': key} if key else {})
    return base, ({'Authorization': f'Bearer {key}'} if key else {})


def list_voice_details(profile):
    if profile.name == 'elevenlabs':
        base, headers = connection(profile)
        try:
            res = requests.get(base + '/voices', headers=headers, timeout=(5, 20), allow_redirects=False)
            if not res.ok:
                detail = ''
                try:
                    value = res.json().get('detail', {})
                    detail = value.get('message', '') if isinstance(value, dict) else str(value)
                except ValueError:
                    pass
                raise ValueError(f'ElevenLabs returned HTTP {res.status_code}' + (f': {detail}' if detail else '. Check the API key and Voices read permission.'))
            details = []
            for voice in res.json().get('voices', []):
                if not isinstance(voice, dict) or not voice.get('voice_id'):
                    continue
                labels = voice.get('labels') if isinstance(voice.get('labels'), dict) else {}
                details.append({'id': str(voice['voice_id']), 'name': str(voice.get('name') or voice['voice_id']),
                    'language': str(labels.get('language') or voice.get('language') or ''),
                    'accent': str(labels.get('accent') or voice.get('accent') or ''),
                    'gender': str(labels.get('gender') or voice.get('gender') or ''),
                    'age': str(labels.get('age') or voice.get('age') or ''),
                    'description': str(voice.get('description') or ''),
                    'preview_url': str(voice.get('preview_url') or '')})
            return details
        except (requests.RequestException, KeyError, TypeError):
            raise ValueError('ElevenLabs voice list unavailable. Check the API key.')
    base, headers = connection(profile)
    try:
        res = requests.get(base + '/audio/voices', headers=headers, timeout=(5, 15), allow_redirects=False)
        if not res.ok: raise ValueError(f'Voice service returned HTTP {res.status_code}. Check the service URL.')
        values = res.json().get('voices', [])
        return [{'id': v if isinstance(v, str) else str(v['id']), 'name': v if isinstance(v, str) else str(v['id'])} for v in values]
    except (requests.RequestException, KeyError, TypeError):
        raise ValueError('Voice service unavailable. Start it and check its address in Settings.')


def list_voices(profile):
    return [voice['id'] for voice in list_voice_details(profile)]


def synthesize(profile, text, voice, language, speed):
    if profile.name == 'elevenlabs':
        base, headers = connection(profile)
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+', voice or ''):
            raise ValueError('Select an ElevenLabs voice first.')
        if not .7 <= speed <= 1.2:
            raise ValueError('ElevenLabs speaking speed must be between 0.70 and 1.20.')
        try:
            res = requests.post(base + '/text-to-speech/' + voice,
                params={'output_format': 'mp3_44100_128'},
                json={'text': text, 'model_id': profile.model or 'eleven_multilingual_v2',
                      'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'speed': speed}},
                headers={**headers, 'Accept': 'audio/mpeg', 'Content-Type': 'application/json'},
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
