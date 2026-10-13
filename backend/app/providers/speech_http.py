"""Kokoro and the bundled Chatterbox bridge share an OpenAI-shaped audio API."""
import requests
from urllib.parse import urlparse
from app.security.secrets import reveal

_LOOPBACK = {'127.0.0.1', 'localhost', '::1'}


def _local(url):
    """Requests for this computer's own engines must not go through a system proxy.
    On Windows, requests picks up the Internet Options proxy (VPNs, antivirus web
    shields, company proxies) and then cannot reach 127.0.0.1, so a running
    Chatterbox container looked "unavailable". A None entry removes the
    environment proxy for that scheme."""
    if (urlparse(url).hostname or '').lower() in _LOOPBACK:
        return {'proxies': {'http': None, 'https': None}}
    return {}


def _unreachable(profile, base, exc):
    name = (profile.name or 'Voice service').title()
    root = base[:-3] if base.endswith('/v1') else base
    if isinstance(exc, requests.Timeout):
        return ValueError(f'{name} at {root} did not answer in time. It may still be starting or downloading its voice model; '
                          'wait a minute and try again.')
    if isinstance(exc, requests.ConnectionError):
        return ValueError(f'Nothing is answering at {root}. Start {name} (Audio → Voice & narration → Start {name}), '
                          'or check its address in Settings.')
    return ValueError(f'{name} at {root} sent an unexpected reply. Check its address in Settings.')


def connection(profile):
    base = (profile.base_url or '').rstrip('/')
    if not base.endswith('/v1'): base += '/v1'
    key = reveal(profile.secret_ref or '')
    if profile.name == 'elevenlabs':
        return 'https://api.elevenlabs.io/v1', ({'xi-api-key': key} if key else {})
    return base, ({'Authorization': f'Bearer {key}'} if key else {})


def list_voice_details(profile):
    if profile.name == 'kokoro_builtin':
        from app.providers import kokoro_builtin
        return kokoro_builtin.voice_details()
    if profile.name == 'gemini_tts':
        from app.providers import gemini_tts
        return gemini_tts.voice_details()
    if profile.name == 'voicebox':
        from app.providers import voicebox
        return voicebox.voice_details(profile.base_url)
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
        res = requests.get(base + '/audio/voices', headers=headers, timeout=(5, 15), allow_redirects=False, **_local(base))
        if not res.ok: raise ValueError(f'Voice service returned HTTP {res.status_code}. Check the service URL.')
        values = res.json().get('voices', [])
        return [{'id': v if isinstance(v, str) else str(v['id']), 'name': v if isinstance(v, str) else str(v['id'])} for v in values]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith('Voice service returned'):
            raise
        raise _unreachable(profile, base, exc) from exc


def list_voices(profile):
    return [voice['id'] for voice in list_voice_details(profile)]


def synthesize(profile, text, voice, language, speed):
    return synthesize_with_alignment(profile, text, voice, language, speed)[0]


def _alignment_from(payload) -> dict | None:
    """ElevenLabs /with-timestamps: per-character start/end seconds."""
    al = payload.get('alignment') if isinstance(payload, dict) else None
    if not isinstance(al, dict):
        return None
    chars, starts, ends = al.get('characters'), al.get('character_start_times_seconds'), al.get('character_end_times_seconds')
    if not (isinstance(chars, list) and isinstance(starts, list) and isinstance(ends, list) and len(chars) == len(starts) == len(ends) and chars):
        return None
    return {'chars': [str(c)[:4] for c in chars], 'starts': [float(x) for x in starts], 'ends': [float(x) for x in ends]}


def synthesize_with_alignment(profile, text, voice, language, speed):
    """Return (audio bytes, alignment or None). ElevenLabs is asked for
    character timestamps so word-by-word captions can follow the voice exactly."""
    if profile.name == 'kokoro_builtin':
        from app.providers import kokoro_builtin
        return kokoro_builtin.synthesize(text, voice, language, speed), None
    if profile.name == 'gemini_tts':
        from app.providers import gemini_tts
        return gemini_tts.synthesize(reveal(profile.secret_ref or ''), profile.model, text, voice, language, speed), None
    if profile.name == 'voicebox':
        from app.providers import voicebox
        return voicebox.synthesize(profile.base_url, text, voice, language), None
    if profile.name == 'elevenlabs':
        base, headers = connection(profile)
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+', voice or ''):
            raise ValueError('Select an ElevenLabs voice first.')
        if not .7 <= speed <= 1.2:
            raise ValueError('ElevenLabs speaking speed must be between 0.70 and 1.20.')
        try:
            res = requests.post(base + '/text-to-speech/' + voice + '/with-timestamps',
                params={'output_format': 'mp3_44100_128'},
                json={'text': text, 'model_id': profile.model or 'eleven_multilingual_v2',
                      'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'speed': speed}},
                headers={**headers, 'Accept': 'application/json', 'Content-Type': 'application/json'},
                timeout=(10, 600), allow_redirects=False)
            if not res.ok: raise ValueError(f'ElevenLabs returned HTTP {res.status_code}. Check key, voice and quota.')
            try:
                payload = res.json()
            except (ValueError, AttributeError):   # not JSON: plain audio from an older endpoint
                payload = None
            if isinstance(payload, dict) and isinstance(payload.get('audio_base64'), str):
                import base64
                return base64.b64decode(payload['audio_base64']), _alignment_from(payload)
            return res.content, None
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
        res = requests.post(base + '/audio/speech', json=payload, headers=headers, timeout=(10, 600), allow_redirects=False, **_local(base))
        if not res.ok:
            detail = ''
            if profile.name == 'chatterbox':
                try: detail = str(res.json().get('detail', ''))[:800]
                except ValueError: pass
            raise ValueError(detail or f'Voice generation returned HTTP {res.status_code}. Run DIAGNOSE_VOICE.bat and check model installation.')
        if len(res.content) > 100 * 1024 * 1024: raise ValueError('Voice response is too large. Split the script into shorter scenes.')
        return res.content, None
    except requests.RequestException as exc:
        raise _unreachable(profile, base, exc) from exc
