export const PROVIDER_NOTES:Record<string,string> = {
  openai:"Paid image API. Uses your OpenAI account.",
  gemini:"Image API billing depends on your Google account and model; not advertised as free.",
  cloudflare:"Free daily Workers AI allowance; limits apply. Paid accounts may incur usage charges. FLUX Schnell uses the model’s default composition.",
  huggingface:"Small monthly inference credit, not unlimited free images. Extra usage follows your HF account billing. Model availability varies.",
  together:"Together AI image models, including a limited free FLUX Schnell model. Usage and quota follow your account.",
  local_sd:"Runs on your computer. Install AUTOMATIC1111 and an image checkpoint, then start it with --api. No API key or Docker required. GPU memory limits apply; model downloads are separate. Use current to keep the loaded model.",
  elevenlabs:"Hosted multilingual voice generation. Usage and quota follow your ElevenLabs account.",
  local_comfy:"Runs open-weight video models on your computer through ComfyUI. Model files and trusted API workflows are downloaded/imported separately; no API key or per-video provider fee. GPU, RAM and disk requirements vary by model.",
  google_veo:"Paid cloud video generation through Google Gemini API. Add a Google AI Studio key. SceneForge displays an estimate before submission; Google controls final billing.",
  runway:"Paid cloud video generation through Runway API. Add a Runway developer key and credits. SceneForge displays an estimate before submission; Runway controls final billing.",
};
export const PROVIDER_OPTIONS = [
  {name:"cloudflare", label:"Cloudflare · Free allowance", capability:"image", model:"@cf/black-forest-labs/flux-1-schnell", url:""},
  {name:"huggingface", label:"Hugging Face · Limited credits", capability:"image", model:"black-forest-labs/FLUX.1-schnell", url:""},
  {name:"together", label:"Together AI · FLUX images", capability:"image", model:"black-forest-labs/FLUX.1-schnell-Free", url:""},
  {name:"local_sd", label:"Local · Stable Diffusion", capability:"image", model:"current", url:"http://127.0.0.1:7860"},
  {name:"openai", label:"OpenAI · Images", capability:"image", model:"gpt-image-1", url:""},
  {name:"gemini", label:"Google Gemini · Images", capability:"image", model:"gemini-3.1-flash-image", url:""},
  {name:"elevenlabs", label:"ElevenLabs · Voice", capability:"speech", model:"eleven_multilingual_v2", url:"https://api.elevenlabs.io/v1"},
  {name:"local_comfy", label:"Local · ComfyUI video", capability:"video", model:"ComfyUI local video engine", url:"http://127.0.0.1:8188"},
  {name:"google_veo", label:"Google Veo · Video", capability:"video", model:"veo-3.1-generate-preview", url:""},
  {name:"runway", label:"Runway · Video", capability:"video", model:"gen4.5", url:""},
];
