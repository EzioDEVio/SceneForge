"""Native OS credentials. SQLite stores opaque references; no plaintext fallback."""
from __future__ import annotations

import base64
import sys
import uuid

SERVICE = "SceneForge"


def vault():
    # Explicit native backends prevent plaintext keyring plugins overriding us.
    try:
        if sys.platform == 'win32':
            from keyring.backends.Windows import WinVaultKeyring
            return WinVaultKeyring()
        if sys.platform == 'darwin':
            from keyring.backends.macOS import Keyring
            return Keyring()
        from keyring.backends.SecretService import Keyring
        return Keyring()
    except Exception:
        raise ValueError('Secure credential storage is unavailable. Unlock your OS credential store and retry.') from None


def obscure(secret: str) -> str:
    """Store credentials in the OS credential vault, never SQLite."""
    if not secret:
        return ""
    ref = uuid.uuid4().hex
    try:
        vault().set_password(SERVICE, ref, secret)
    except Exception:
        raise ValueError('Could not save the key securely. Unlock your OS credential store and retry.') from None
    return "keyring:" + ref


def reveal(stored: str) -> str:
    if not stored:
        return ''
    if not stored.startswith('keyring:'):
        raise ValueError('Credential migration is incomplete. Re-save the provider key in Settings.')
    try:
        value = vault().get_password(SERVICE, stored[8:])
    except Exception:
        raise ValueError('Secure credential storage is locked or unavailable. Unlock it and retry.') from None
    if value is None:
        raise ValueError('Provider credential is missing. Re-enter the key in Settings.')
    return value


def forget(stored: str):
    if stored and stored.startswith('keyring:'):
        try:
            backend = vault()
            if backend.get_password(SERVICE, stored[8:]) is not None:
                backend.delete_password(SERVICE, stored[8:])
        except Exception:
            raise ValueError('Could not remove the saved credential. Unlock the OS credential store and retry.') from None


def migrate_credentials():
    from app.db.database import SessionLocal, engine
    from app.db.models import ProviderProfile
    failed = 0
    changed = False
    with SessionLocal() as db:
        for profile in db.query(ProviderProfile).all():
            if not profile.secret_ref or profile.secret_ref.startswith('keyring:'):
                continue
            try:
                plain = base64.b64decode(profile.secret_ref, validate=True).decode('utf-8')
                protected = obscure(plain)
            except Exception:
                failed += 1
                continue
            profile.secret_ref = protected
            changed = True
        db.commit()
    if changed:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            conn.exec_driver_sql('PRAGMA wal_checkpoint(TRUNCATE)')
            conn.exec_driver_sql('VACUUM')
            conn.exec_driver_sql('PRAGMA wal_checkpoint(TRUNCATE)')
    return failed


def mask_for_display(secret: str) -> str:
    """Never send the real key to the frontend — only a masked hint like
    'sk-...ab12' so the user can confirm which key is configured."""
    if len(secret) <= 8:
        return "•" * len(secret)
    return f"{secret[:3]}...{secret[-4:]}"
