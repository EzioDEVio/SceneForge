export interface TextLayer { family?:string;outline_width?:number;shadow?:number;align?:string;exit_ms?:number; animation?:string;animation_ms?:number;id:string;text:string;x:number;y:number;size:number;color:string;start_ms:number;end_ms:number;bold:boolean;}
// Thin fetch wrapper + types matching backend/app/domain/schemas.py.
// Uses relative /api paths so it works both under the Vite dev proxy and
// the production build served from the same FastAPI origin.

export type Asset = {
  id: string;
  type: "image" | "video" | "audio";
  mime: string;
  original_filename: string;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  origin: string;
};

export type Shot = {
  crop_json?: {x:number;y:number;width:number;height:number}|null;
  id: string;
  asset_id: string;
  order_index: number;
  fit: string;
  motion_json: { type: string; start?: any; end?: any };
  source_in_ms: number;
  source_out_ms: number | null;
  duration_ms: number | null;
  is_selected: boolean;
  asset?: Asset;
};

export type VoiceTake = {
  id: string;
  source: string;
  provider: string | null;
  voice: string | null;
  measured_duration_ms: number | null;
  accepted: boolean;
  stale: boolean;
  audio_asset?: Asset;
  edit_json?: AudioEdit;
  effective_duration_ms?: number | null;
};
export type AudioEdit = {in_ms?: number; out_ms?: number | null; volume?: number; fade_in_ms?: number; fade_out_ms?: number};
export type Waveform = {duration_ms: number; peaks: number[]; peak: number};

export type FontSettings = {
  family: string;
  size: number;
  color: string;
  outline_color: string;
  outline_width: number;
  background: string;
  position: string;
  captions_enabled: boolean;
  layers?: TextLayer[];
  typewriter?: boolean;
  typewriter_sound?: boolean;
  typewriter_sound_asset_id?: string | null;
  typewriter_volume?: number;
  typewriter_delay_ms?: number;
  typewriter_duration_ms?: number;
};

/** Must match BUILD_ID in backend/app/main.py. */
export const BUILD_ID = "rc5-effects-6";

export type Adjust = Partial<Record<'exposure'|'contrast'|'highlights'|'shadows'|'temperature'|'tint'|'saturation'|'vibrance'|'sharpen'|'vignette'|'grain', number>>;
export type Look = {
  glitch?: {speed: number; block: 'small' | 'medium' | 'large'} | null;
  adjust?: Adjust | null;
  lut?: {asset_id: string; strength: number} | null;
  film?: FilmLook | null;
};
export type Overlay = {id: string; asset_id: string; x: number; y: number; width: number; rotation: number; opacity: number;
  radius: number; border: number; border_color: string; shadow: number; start_ms: number; end_ms: number | null;
  anim_in: 'none' | 'fade' | 'slide_left' | 'slide_up' | 'zoom'; anim_out: 'none' | 'fade' | 'slide_left' | 'slide_up' | 'zoom'; anim_ms: number};
export type Finishing = {music?: {asset_id: string; volume: number; duck: number; fade_in_ms: number; fade_out_ms: number} | null; loudnorm?: boolean; leader?: boolean};
export type FilmLook = {scratches: number; dust: number; flicker: number; weave: number; sound: number; fps: 0 | 16 | 18 | 24; tone: 'color' | 'faded' | 'sepia' | 'bw'};

export type Scene = {
  id: string;
  project_id: string;
  order_index: number;
  title: string;
  original_text: string;
  spoken_text: string;
  subtitle_text: string;
  timing_mode: string;
  requested_duration_ms: number | null;
  lead_ms: number;
  trail_ms: number;
  effect_preset: string;
  effect_intensity: number;
  transition_in_json: { type: string; duration_ms: number };
  font_json: FontSettings;
  look_json?: Look;
  overlays_json?: Overlay[];
  revision: number;
  rendered_plan_hash: string | null;
  rendered_asset_id: string | null;
  measured_duration_ms: number | null;
  shots: Shot[];
  voice_takes: VoiceTake[];
  is_stale: boolean;
};

export type Project = {
  id: string;
  title: string;
  language: string;
  aspect: string;
  fps: number;
  width: number;
  height: number;
  revision: number;
  default_font_json: FontSettings;
  finishing_json?: Finishing;
  scenes: Scene[];
};

export type Job = {
  id: string;
  project_id: string;
  scene_id: string | null;
  scope: string;
  status: "queued" | "running" | "cancelling" | "cancelled" | "failed" | "succeeded";
  stage: string;
  progress: number;
  error: string | null;
  artifact_asset_id: string | null;
};

export type ProviderProfile = {
  id: string;
  capability: string;
  name: string;
  model: string | null;
  base_url: string | null;
  masked_key: string;
  configured: boolean;
};
export type VoiceOption = { id: string; name: string; language?: string; accent?: string; gender?: string; age?: string; description?: string; preview_url?: string };

const BASE = "";

let activeWrites=0;
export const hasActiveWrites=()=>activeWrites>0;
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const write=!!init?.method&&init.method!=="GET";
  if(write)activeWrites++;
  try {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  return await res.json();
  } finally {if(write)activeWrites--;}
}

export const api = {
  createProject: (title: string, aspect: string) =>
    req<Project>("/api/projects", { method: "POST", body: JSON.stringify({ title, aspect }) }),
  deleteProject: (id:string) => req<{ok:boolean}>(`/api/projects/${id}`, {method:"DELETE"}),
  listProjects: () => req<Project[]>("/api/projects"),
  getProject: (id: string) => req<Project>(`/api/projects/${id}`),
  updateProject: (id: string, body: Partial<{ title: string; aspect: string; finishing: Finishing }>) =>
    req<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  addScene: (projectId: string) =>
    req<Scene>(`/api/projects/${projectId}/scenes`, { method: "POST", body: JSON.stringify({}) }),
  reorderScenes: (projectId: string, sceneIds: string[]) =>
    req(`/api/projects/${projectId}/scene-order`, { method: "PUT", body: JSON.stringify({ scene_ids: sceneIds }) }),
  updateScene: (sceneId: string, body: Record<string, any>) =>
    req<Scene>(`/api/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteScene: (sceneId: string) => req(`/api/scenes/${sceneId}`, { method: "DELETE" }),

  uploadAsset: (projectId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Asset>(`/api/assets/upload?project_id=${projectId}`, { method: "POST", body: fd });
  },
  addShot: (sceneId: string, assetId: string, motion: any = { type: "static" }, fit = "cover") =>
    req<Shot>(`/api/scenes/${sceneId}/shots`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId, motion, fit }),
    }),
  listAssets:(id:string)=>req<Asset[]>(`/api/assets?project_id=${id}`),
  listLuts:(projectId:string)=>req<Asset[]>(`/api/assets/luts?project_id=${projectId}`),
  importLut:(projectId:string,file:File)=>{const form=new FormData();form.append('file',file);return req<Asset>(`/api/assets/lut?project_id=${projectId}`,{method:'POST',body:form});},
  hideAsset:(id:string)=>req(`/api/assets/${id}/hide-from-pool`,{method:'POST'}),
  useAudioAsset:(sceneId:string,assetId:string)=>req(`/api/scenes/${sceneId}/voice-takes/from-asset`,{method:'POST',body:JSON.stringify({asset_id:assetId})}),
  splitScene: (id:string,at:number,baked=false)=>req<Scene>(`/api/scenes/${id}/split`,{method:"POST",body:JSON.stringify({at_ms:at,baked})}),
  updateShot: (shotId: string, body: Record<string, any>) =>
    req<Shot>(`/api/scenes/shots/${shotId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteShot: (shotId: string) => req(`/api/scenes/shots/${shotId}`, { method: "DELETE" }),

  localTtsTake: (sceneId: string, voice: string) =>
    req<VoiceTake>(`/api/scenes/${sceneId}/voice-takes/local-tts`, {
      method: "POST",
      body: JSON.stringify({ source: "local_offline_tts", voice }),
    }),
  uploadVoiceTake: (sceneId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<VoiceTake>(`/api/scenes/${sceneId}/voice-takes/upload`, { method: "POST", body: fd });
  },
  voicePreview: (sceneId: string, text: string, voice: string) =>
    req<{ asset: Asset; stream_url: string }>(`/api/scenes/${sceneId}/voice-preview`, {
      method: "POST",
      body: JSON.stringify({ text, voice }),
    }),
  clearNarration: (sceneId: string) => req(`/api/scenes/${sceneId}/voice-takes/clear-selection`, {method: "POST"}),
  editTake: (takeId: string, edit: AudioEdit) => req<VoiceTake>(`/api/voice-takes/${takeId}/edit`, {method: "PATCH", body: JSON.stringify(edit)}),
  waveform: (assetId: string, points = 600) => req<Waveform>(`/api/assets/${assetId}/waveform?points=${points}`),
  deleteTake: (takeId: string) => req(`/api/voice-takes/${takeId}`, {method:"DELETE"}),
  selectTake: (takeId: string) => req<VoiceTake>(`/api/voice-takes/${takeId}/select`, { method: "POST" }),

  renderPart: (sceneId: string) => req<{ job_id: string }>(`/api/scenes/${sceneId}/render`, { method: "POST" }),
  exportProject: (projectId: string, skipEmpty = false) =>
    req<{ job_id: string }>(`/api/projects/${projectId}/export?skip_empty=${skipEmpty}`, { method: "POST" }),
  getJob: (jobId: string) => req<Job>(`/api/jobs/${jobId}`),
  cancelJob: (jobId: string) => req(`/api/jobs/${jobId}/cancel`, { method: "POST" }),

  importPreview: (projectId: string, text: string) =>
    req<any>(`/api/projects/${projectId}/import`, { method: "POST", body: JSON.stringify({ text }) }),
  importApply: (projectId: string, scenes: any[], replaceExisting: boolean) =>
    req<Scene[]>(`/api/projects/${projectId}/import/apply`, {
      method: "POST",
      body: JSON.stringify({ scenes, replace_existing: replaceExisting }),
    }),

  getAsset: (assetId: string) => req<Asset>(`/api/assets/${assetId}`),
  assetStreamUrl: (assetId: string) => `/api/assets/${assetId}/stream`,
  assetThumbUrl: (assetId: string, width = 320) => `/api/assets/${assetId}/thumbnail?w=${width}`,
  gradedFrameUrl: (sceneId: string, key: string, width = 1280, shotId?: string) => `/api/scenes/${sceneId}/graded-frame?w=${width}&k=${key}${shotId ? `&shot_id=${shotId}` : ''}`,
  assetDownloadUrl: (assetId: string) => `/api/assets/${assetId}/stream?download=1`,

  health: () => req<{status:string;build?:string;credential_warning?:string}>("/api/health"),
  closeStatus:()=>req<{ready:boolean}>("/api/close-status"),
  connectLocalSpeech: (engine:string) => req<{profile:ProviderProfile;voices:string[];message:string}>(`/api/local-speech/${engine}/connect`, {method:"POST"}),
  imageHistory: (sceneId:string) => req<{id:string;prompt:string;provider:string}[]>(`/api/scenes/${sceneId}/image-history`),
  providerVoices: (id:string) => req<{voices:VoiceOption[]}>(`/api/providers/profile/${id}/voices`),
  deleteProviderProfile: (id:string) => req(`/api/providers/profile/${id}`, {method:"DELETE"}),
  serviceTts: (sceneId:string, providerId:string, voice:string, language:string, speed:number, audition=false) => req<any>(`/api/scenes/${sceneId}/voice-takes/service`, {method:"POST",body:JSON.stringify({provider_id:providerId,voice,language,speed,audition})}),
  listProviders: () => req<ProviderProfile[]>("/api/providers"),
  upsertProvider: (capability: string, name: string, apiKey: string, model?: string, baseUrl?: string) =>
    req<ProviderProfile>("/api/providers", {
      method: "POST",
      body: JSON.stringify({ capability, name, api_key: apiKey, model, base_url: baseUrl }),
    }),
  deleteProvider: (capability: string) => req(`/api/providers/${capability}`, { method: "DELETE" }),
  localImageStatus: (id:string) => req<{ready:boolean;model?:string;state?:string;message?:string}>(`/api/local-images/${id}/status`),
  generateImage: (sceneId: string, prompt: string, size = "1024x1024", providerId?: string, localOptions?: any) =>
    req<Asset>(`/api/scenes/${sceneId}/generate-image`, {
      method: "POST",
      body: JSON.stringify({ prompt, size, provider_id: providerId, local_options: localOptions }),
    }),
};

export function subscribeJob(jobId: string, onEvent: (e: any) => void): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.addEventListener("progress", (ev) => {
    try {
      onEvent(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore */
    }
  });
  return () => es.close();
}
