"""Source-checkpoint AI setup. Same implementation as the native installer."""
from pathlib import Path
import argparse
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('SCENEFORGE_RESOURCE_DIR',str(ROOT))
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Install local AI after reviewing its component terms.')
    p.add_argument('--components',default='whisper,stable_diffusion,chatterbox')
    p.add_argument('--accept-terms',action='store_true')
    p.add_argument('--gpu',action='store_true')
    a=p.parse_args()
    if not a.accept_terms:p.error('Review docs/LOCAL_AI_INSTALLER.md, then pass --accept-terms.')
    from app.db.database import init_db
    from app.managed_ai import install
    init_db()
    sys.exit(0 if install(a.components.split(','),a.gpu) else 1)
