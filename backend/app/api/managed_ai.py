import os
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from app import managed_ai
router=APIRouter(tags=['local-ai'])

class Install(BaseModel):
    components:list[Literal['whisper','stable_diffusion','chatterbox']]=Field(min_length=1,max_length=3)
    accept_terms:bool=False
    gpu:bool=False

@router.get('/api/local-ai/setup')
def state():return managed_ai.state()

@router.post('/api/local-ai/setup')
def install(body:Install):
    if os.name!='nt':raise HTTPException(400,'Automatic setup is available on Windows.')
    if not body.accept_terms:raise HTTPException(400,'Review and accept the component terms before installing.')
    if not body.components:raise HTTPException(400,'Select at least one local AI component.')
    with managed_ai._lock:
        if managed_ai.state()['status']=='running':raise HTTPException(409,'Installation is already running.')
        managed_ai._state.update(status='running',error='')
        threading.Thread(target=managed_ai.install,args=(body.components,body.gpu),daemon=True).start()
    return {'started':True}

class Startup(BaseModel):
    autostart:bool

@router.put('/api/local-ai/startup')
def startup(body:Startup):
    with managed_ai._lock:
        value={**managed_ai.preferences(),'autostart':body.autostart};managed_ai.save_preferences(value)
    return value
