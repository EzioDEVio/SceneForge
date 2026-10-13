import os
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from app import managed_ai
router=APIRouter(tags=['local-ai'])

class Install(BaseModel):
    components:list[Literal['whisper','kokoro','stable_diffusion','chatterbox']]=Field(min_length=1,max_length=4)
    accept_terms:bool=False
    gpu:bool=False

@router.get('/api/local-ai/setup')
def state():return {**managed_ai.state(),'running':managed_ai.running()}

@router.post('/api/local-ai/setup')
def install(body:Install):
    if not managed_ai.state()['supported']:raise HTTPException(400,'Automatic setup is not available on this computer yet.')
    if not body.accept_terms:raise HTTPException(400,'Review and accept the component terms before installing.')
    if not body.components:raise HTTPException(400,'Select at least one local AI component.')
    with managed_ai._lock:
        if managed_ai.state()['status']=='running':raise HTTPException(409,'Installation is already running.')
        managed_ai._state.update(status='running',error='')
        threading.Thread(target=managed_ai.install,args=(body.components,body.gpu),daemon=True).start()
    return {'started':True}

class Startup(BaseModel):
    autostart:bool|None=None
    gpu:bool|None=None

@router.put('/api/local-ai/startup')
def startup(body:Startup):
    """Save the AI Engines options (start with SceneForge, use the NVIDIA graphics card)."""
    with managed_ai._lock:
        value=managed_ai.preferences()
        if body.autostart is not None:value['autostart']=body.autostart
        if body.gpu is not None:value['gpu']=body.gpu
        managed_ai.save_preferences(value)
    return value


class Start(BaseModel):
    components:list[Literal['stable_diffusion','chatterbox']]=Field(min_length=1,max_length=2)

@router.post('/api/local-ai/start')
def start(body:Start):
    """Start engines that were installed earlier (no downloads, no installs)."""
    installed=managed_ai.preferences().get('components',[])
    missing=[c for c in body.components if c not in installed]
    if missing:raise HTTPException(400,'Install '+', '.join(missing)+' first.')
    threading.Thread(target=managed_ai.autostart,kwargs={'force':True,'services':list(body.components)},daemon=True).start()
    return {'started':True}
