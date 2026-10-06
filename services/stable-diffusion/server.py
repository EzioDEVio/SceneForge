"""Owned SD 1.5 service. Keep the existing AUTOMATIC1111 adapter compatible.

No third-party extensions, arbitrary checkpoint paths or cloud fallback.
The model's safety checker is retained. CUDA is used only when available.
"""
import base64
import io
import threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL = 'stable-diffusion-v1-5/stable-diffusion-v1-5'
REVISION = '451f4fe16113bff5a5d2269ed5ad43b0592e9a14'
app = FastAPI(title='SceneForge Stable Diffusion')
pipeline = None
lock = threading.Lock()
loading = False
last_error = None

def load():
    global pipeline, loading, last_error
    if pipeline is not None:
        return pipeline
    loading = True
    try:
        import torch
        from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        pipeline = StableDiffusionPipeline.from_pretrained(
            MODEL, revision=REVISION, use_safetensors=True,
            torch_dtype=torch.float16 if device == 'cuda' else torch.float32)
        pipeline.scheduler = DPMSolverMultistepScheduler.from_config(pipeline.scheduler.config)
        pipeline.to(device)
        pipeline.enable_attention_slicing()
        last_error = None
        return pipeline
    except Exception as exc:
        pipeline = None
        last_error = type(exc).__name__ + ': ' + str(exc)[:500]
        raise HTTPException(503, 'Stable Diffusion model setup failed. Retry installation; inspect the engine log.') from exc
    finally:
        loading = False

@app.get('/health')
def health():
    return {'service':'stable_diffusion','model_ready':pipeline is not None,'loading':loading,'last_error':last_error,'device':str(pipeline.device) if pipeline is not None else None}

@app.post('/warmup')
def warmup():
    with lock:
        load()
    return health()

@app.get('/sdapi/v1/options')
def options():
    if pipeline is None:
        raise HTTPException(503, 'Image model has not finished installation.')
    return {'sd_model_checkpoint':'SceneForge SD 1.5','device':str(pipeline.device)}

class ImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(default='', max_length=4000)
    width: int = Field(default=512, ge=256, le=1024, multiple_of=8)
    height: int = Field(default=512, ge=256, le=1024, multiple_of=8)
    steps: int = Field(default=30, ge=1, le=60)
    cfg_scale: float = Field(default=7, ge=1, le=20)
    seed: int = Field(default=-1, ge=-1, le=2147483647)
    enable_hr: bool = False

@app.post('/sdapi/v1/txt2img')
def image(body: ImageRequest):
    if body.enable_hr:
        raise HTTPException(400, 'Managed SD 1.5 does not support a hires pass. Turn it off, or connect your WebUI engine.')
    import torch
    with lock:
        p = load()
        seed = body.seed if body.seed >= 0 else int(torch.randint(0, 2147483647, (1,)).item())
        result = p(body.prompt, negative_prompt=body.negative_prompt, width=body.width,
                   height=body.height, num_inference_steps=body.steps,
                   guidance_scale=body.cfg_scale, generator=torch.Generator(device=p.device).manual_seed(seed))
        out = io.BytesIO()
        result.images[0].save(out, format='PNG')
        return {'images':[base64.b64encode(out.getvalue()).decode()], 'seed':seed}
