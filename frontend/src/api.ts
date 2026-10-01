export interface TextLayer { kind?:'text'|'text_box'|'text_plus';box_width?:number; family?:string;outline_width?:number;shadow?:number;align?:string;exit_ms?:number; animation?:string;animation_ms?:number;spacing?:number;highlight?:string;id:string;text:string;x:number;y:number;size:number;color:string;start_ms:number;end_ms:number;bold:boolean;}
export type CaptionSegment={id:string;text:string;start_ms:number;end_ms:number};
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
  creator?: string | null;
  license_note?: string | null;
};

export type VideoModel = {
  id:string; provider:string; provider_label:string; name:string; model:string; kind:'local'|'cloud';
  price_per_second:number|Record<string,number>; resolutions:string[]; ratios:string[];
  duration_min:number; duration_max:number; durations:number[]; native_audio:boolean|null;
  requirements:string; workflow_url:string; terms_url?:string; cost_note:string; workflow_imported?:boolean;
  min_vram_gb?:number|null; min_system_ram_gb?:number|null;
};
export type VideoGenerationRequest = {
  provider:string; model:string; prompt:string; negative_prompt?:string; aspect_ratio:string;
  width:number; height:number; duration_seconds:number; resolution:string; seed?:number|null; candidate_count?:1|2|3; confirm_paid?:boolean;
};
export type LocalVideoSystem = {detected:boolean;gpu_name:string|null;vram_gb:number|null;system_ram_gb:number|null;gpu_count:number;recommended_model_ids:string[];message:string};

export type Shot = {
  crop_json?: {x:number;y:number;width:number;height:number}|null;
  id: string;
  asset_id: string;
  order_index: number;
  fit: string;
  motion_json: { type: string; start?: any; end?: any };
  speed_json?: {speed?:number;freeze_at_ms?:number|null};
  source_in_ms: number;
  source_out_ms: number | null;
  duration_ms: number | null;
  is_selected: boolean;
  audio_json?: {volume?: number; mute?: boolean; duck?: boolean; fade_in_ms?: number; fade_out_ms?: number};
  asset?: Asset;
};

export type VoiceTake = {
  id: string;
  spoken_text_hash?: string;
  source: string;
  provider: string | null;
  model?: string | null;
  voice: string | null;
  settings_json?: Record<string, unknown> | null;
  audio_asset_id?: string | null;
  measured_duration_ms: number | null;
  natural_duration_ms?: number | null;
  accepted: boolean;
  stale: boolean;
  audio_asset?: Asset;
  edit_json?: AudioEdit;
  effective_duration_ms?: number | null;
};
export type AudioEdit = {in_ms?: number; out_ms?: number | null; volume?: number; fade_in_ms?: number; fade_out_ms?: number; voice_fx?: string};
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
  caption_segments?: CaptionSegment[];
  caption_direction?: 'auto'|'ltr'|'rtl';
  typewriter?: boolean;
  typewriter_sound?: boolean;
  typewriter_sound_asset_id?: string | null;
  typewriter_volume?: number;
  typewriter_delay_ms?: number;
  typewriter_duration_ms?: number;
};

/** Must match BUILD_ID in backend/app/main.py. */
export const BUILD_ID = "v0.7.0";

export type Adjust = Partial<Record<'exposure'|'contrast'|'highlights'|'shadows'|'temperature'|'tint'|'saturation'|'vibrance'|'sharpen'|'vignette'|'grain', number>>;
export type Look = {
  glitch?: {speed: number; block: 'small' | 'medium' | 'large'} | null;
  adjust?: Adjust | null;
  lut?: {asset_id: string; strength: number} | null;
  film?: FilmLook | null;
  /** rc6 pack parameters (see backend render/filters.py + scene_fx.py). */
  focus?: {size: number; blur: number; x: number; y: number} | null;
  mosaic?: {block: number} | null;
  rgbsplit?: {amount: number} | null;
  flare?: {x: number; y: number; color: string; blend: 'screen' | 'add'; amount: number; drift: number} | null;
  wiggle?: {amount: number; speed: number; size: number} | null;
  /** Effect stack (backend render/fx_stack.py): scene-FX render order and bypassed ids. */
  fx_order?: string[] | null;
  /** Per-effect settings, kept per preset: {<preset>: {<param>: value}} (backend render/effect_params.py). */
  fx_params?: Record<string, Record<string, number | string>> | null;
  fx_bypass?: string[] | null;
};
export type Overlay = {id: string; asset_id: string; kind?: 'media'|'sticker'; x: number; y: number; width: number; rotation: number; opacity: number;
  radius: number; border: number; border_color: string; shadow: number; start_ms: number; end_ms: number | null;
  anim_in: 'none' | 'fade' | 'slide_left' | 'slide_up' | 'zoom'; anim_out: 'none' | 'fade' | 'slide_left' | 'slide_up' | 'zoom'; anim_ms: number;
  x2?: number | null; y2?: number | null; chroma?: string | null; chroma_similarity?: number; feather?: number;
  loop?: 'none' | 'float' | 'pendulum' | 'bob'; loop_amount?: number; loop_period_ms?: number};
export type ProjectAudioClip = {id: string; asset_id: string; name: string; start_ms: number; source_in_ms: number; source_out_ms: number; source_duration_ms: number; volume: number; fade_in_ms: number; fade_out_ms: number; mute: boolean; track?: import('./timeline/timeline.types').AudioTrackId; /** volume envelope: [source time ms, dB] */ gain?: [number, number][]; /** clips sharing a group id select and move together */ group?: string};
export type Finishing = {music?: {asset_id: string; volume: number; duck: number; fade_in_ms: number; fade_out_ms: number} | null; audio_clips?: ProjectAudioClip[]; loudnorm?: boolean; leader?: boolean; timeline?: import('./timeline/timeline.types').TimelineSettings};
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
  natural_duration_ms?: number | null;
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
  result_asset_ids?: string[];
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
export type SubjectVideoEstimate = {ok: boolean; reason?: string; frames?: number; seconds_of_video?: number; ms_per_frame?: number; estimate_s?: number; measured?: boolean; running_job_id?: string | null; notes?: string[]};
export type SubjectVideoJob = {job_id: string; status: 'queued' | 'running' | 'cancelling' | 'succeeded' | 'failed' | 'cancelled'; frames_done: number; frames_total: number; ms_per_frame: number | null; stage: string; error: string | null; notes: string[]};
export type VoiceIsolationStatus = {folder: string; file: string; label: string; url: string; approx_mb: number; bytes: number; downloaded: boolean; download?: {done: number; total: number} | null; license: string; running: {job_id: string; asset_id: string; progress: number}[]};
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
  createProject: (title: string, aspect: string, fps = 30) =>
    req<Project>("/api/projects", { method: "POST", body: JSON.stringify({ title, aspect, fps }) }),
  deleteProject: (id:string) => req<{ok:boolean}>(`/api/projects/${id}`, {method:"DELETE"}),
  listProjects: () => req<Project[]>("/api/projects"),
  getProject: (id: string) => req<Project>(`/api/projects/${id}`),
  getScene: (id:string)=>req<Scene>(`/api/scenes/${id}`),
  /** Per-effect settings schema (backend render/effect_params.py; see EffectControls.tsx). */
  effectsSchema: () => req<any>('/api/effects/schema'),
  updateProject: (id: string, body: Partial<{ title: string; aspect: string; fps: number; finishing: Finishing }>) =>
    req<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  addScene: (projectId: string) =>
    req<Scene>(`/api/projects/${projectId}/scenes`, { method: "POST", body: JSON.stringify({}) }),
  insertCountdown: (projectId: string, body: {style: string; seconds: number; beep: string; tone: string; color?: string; after_scene_id?: string | null}) =>
    req<Scene>(`/api/projects/${projectId}/insert-countdown`, {method: 'POST', body: JSON.stringify(body)}),
  autoCaptions: (sceneId: string, body: {provider?: string; language?: string; source?: string; phrase_words?: number}) =>
    req<Scene>(`/api/scenes/${sceneId}/auto-captions`, {method: 'POST', body: JSON.stringify(body)}),
  applyToScenes: (sourceId: string, targets: string[], parts: string[]) =>
    req<{changed: number}>(`/api/scenes/${sourceId}/apply-to`, {method: 'POST', body: JSON.stringify({targets, parts})}),
  duplicateScene: (sceneId: string) => req<Scene>(`/api/scenes/${sceneId}/duplicate`, {method: 'POST'}),
  pasteAudio: (sceneId: string, takeId: string) => req<Scene>(`/api/scenes/${sceneId}/paste-audio`, {method: 'POST', body: JSON.stringify({take_id: takeId})}),
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
  restoreScene: (id:string,snapshot:Scene)=>req<Scene>(`/api/scenes/${id}/restore`,{method:"POST",body:JSON.stringify(snapshot)}),
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
  detachAudio: (sceneId: string, body: {source: 'narration' | 'shot'; shot_id?: string; duration_ms?: number}) =>
    req<{asset: Asset; offset_ms: number}>(`/api/scenes/${sceneId}/detach-audio`, {method: 'POST', body: JSON.stringify(body)}),
  clearNarration: (sceneId: string) => req(`/api/scenes/${sceneId}/voice-takes/clear-selection`, {method: "POST"}),
  editTake: (takeId: string, edit: AudioEdit) => req<VoiceTake>(`/api/voice-takes/${takeId}/edit`, {method: "PATCH", body: JSON.stringify(edit)}),
  waveform: (assetId: string, points = 600) => req<Waveform>(`/api/assets/${assetId}/waveform?points=${points}`),
  deleteTake: (takeId: string) => req(`/api/voice-takes/${takeId}`, {method:"DELETE"}),
  selectTake: (takeId: string) => req<VoiceTake>(`/api/voice-takes/${takeId}/select`, { method: "POST" }),

  renderPart: (sceneId: string) => req<{ job_id: string }>(`/api/scenes/${sceneId}/render`, { method: "POST" }),
  exportProject: (projectId: string, skipEmpty = false, settings?: Record<string, unknown>) =>
    req<{ job_id: string }>(`/api/projects/${projectId}/export?skip_empty=${skipEmpty}`, { method: "POST", body: JSON.stringify({settings: settings || {}}) }),
  captionsUrl: (projectId: string, format: 'srt' | 'vtt') => `/api/projects/${projectId}/captions?format=${format}`,
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
  restoreAsset: (assetId: string) => req<Asset>(`/api/assets/${assetId}/restore`, {method: 'POST'}),
  musicFit: (projectId: string, assetId: string, targetMs?: number) => req<Asset>(`/api/projects/${projectId}/music-fit`, {method: 'POST', body: JSON.stringify(targetMs ? {asset_id: assetId, target_ms: Math.round(targetMs)} : {asset_id: assetId})}),
  beatSync: (projectId: string) => req<{bpm: number; beats: number[]; scenes_changed: number; scenes_kept: number}>(`/api/projects/${projectId}/beat-sync`, {method: 'POST'}),
  /** Rendered scene with the timeline audio (A3–A8) and music under it; `v` refreshes the cached mix. */
  scenePreviewUrl: (sceneId: string, v: string) => `/api/scenes/${sceneId}/preview-media?v=${encodeURIComponent(v)}`,
  assetStreamUrl: (assetId: string) => `/api/assets/${assetId}/stream`,
  assetThumbUrl: (assetId: string, width = 320, timeMs = 0) => `/api/assets/${assetId}/thumbnail?w=${width}${timeMs > 0 ? `&time_ms=${Math.round(timeMs)}` : ''}`,
  gradedFrameUrl: (sceneId: string, key: string, width = 1280, shotId?: string) => `/api/scenes/${sceneId}/graded-frame?w=${width}&k=${key}${shotId ? `&shot_id=${shotId}` : ''}`,
  assetDownloadUrl: (assetId: string) => `/api/assets/${assetId}/stream?download=1`,

  health: () => req<{status:string;build?:string;credential_warning?:string}>("/api/health"),
  closeStatus:()=>req<{ready:boolean}>("/api/close-status"),
  cutoutStatus: () => req<{folder: string; models: {id: string; label: string; downloaded: boolean; approx_mb: number}[]}>(`/api/cutout/status`),
  cutoutAsset: (assetId: string, body: {model?: string; edge?: string; feather?: number; shift?: number}) => req<Asset>(`/api/assets/${assetId}/cutout`, {method: "POST", body: JSON.stringify(body)}),
  subjectVideoEstimate: (sceneId: string, model: string) => req<SubjectVideoEstimate>(`/api/scenes/${sceneId}/subject-video-layer?model=${encodeURIComponent(model)}`),
  subjectVideoLayer: (sceneId: string, body: {model?: string; edge?: string; shift?: number}) => req<{status: 'running' | 'done'; job_id?: string; cached?: boolean; frames?: number; estimate_s?: number; notes?: string[]}>(`/api/scenes/${sceneId}/subject-video-layer`, {method: "POST", body: JSON.stringify(body)}),
  subjectVideoJob: (jobId: string) => req<SubjectVideoJob>(`/api/cutout/video-jobs/${jobId}`),
  voiceIsolationStatus: () => req<VoiceIsolationStatus>(`/api/voice-isolation/status`),
  isolateVoice: (assetId: string, strength = 100) => req<{status: 'done' | 'running'; cached?: boolean; asset?: Asset; job_id?: string; progress?: number}>(`/api/assets/${assetId}/isolate-voice`, {method: "POST", body: JSON.stringify({strength})}),
  voiceIsolationJob: (jobId: string) => req<{status: 'running' | 'done' | 'error'; progress: number; stage: string; asset?: Asset; error?: string}>(`/api/voice-isolation/jobs/${jobId}`),
  subjectLayer: (sceneId: string, body: {model?: string; edge?: string; feather?: number; shift?: number}) => req<{scene: Scene; notes: string[]}>(`/api/scenes/${sceneId}/subject-layer`, {method: "POST", body: JSON.stringify(body)}),
  /** Copy a bundled library sticker into the project's Media Pool (re-used when already imported). */
  importSticker: (projectId: string, stickerId: string) => req<Asset>(`/api/projects/${projectId}/stickers/${encodeURIComponent(stickerId)}`, {method: "POST"}),
  stickerImageUrl: (stickerId: string) => `/api/stickers/${encodeURIComponent(stickerId)}/image`,
  texturedTitle: (sceneId: string, body: Record<string, unknown>) => req<{scene: Scene; asset: Asset}>(`/api/scenes/${sceneId}/textured-title`, {method: "POST", body: JSON.stringify(body)}),
  beatMarkers: (projectId: string, body: {clip_id?: string; every?: number}) => req<{bpm: number; markers: {time_ms: number; downbeat: boolean}[]; truncated: boolean}>(`/api/projects/${projectId}/beat-markers`, {method: "POST", body: JSON.stringify(body)}),
  whisperCheck: () => req<{ok: boolean; model_dir: string; checks: {name: string; ok: boolean; detail: string}[]}>(`/api/local-speech/whisper/check`),
  whisperReset: () => req<{removed: boolean; message: string}>(`/api/local-speech/whisper/reset`, {method: "POST"}),
  localEngineStatus: (engine: string) => req<{engine: string; reachable: boolean; state: string; docker: string; message: string; log: string; services_bundled: boolean}>(`/api/local-speech/${engine}/status`),
  startLocalEngine: (engine: string) => req<{state: string}>(`/api/local-speech/${engine}/start`, {method: "POST"}),
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
  videoGenerationCatalog: () => req<{models:VideoModel[];prices_checked:string}>("/api/video-generation/catalog"),
  localVideoStatus: () => req<{ready:boolean;message:string}>("/api/video-generation/local/status"),
  localVideoSystem: () => req<LocalVideoSystem>("/api/video-generation/local/system"),
  importLocalVideoWorkflow: (modelId:string,file:File) => {
    const form=new FormData();form.append('file',file);
    return req<{ok:boolean;model_id:string;node_count:number}>("/api/video-generation/local/workflows/"+encodeURIComponent(modelId),{method:'POST',body:form});
  },
  generateVideo: (projectId:string, body:VideoGenerationRequest) =>
    req<{job_id:string}>("/api/video-generation/projects/"+projectId+"/generate",{method:'POST',body:JSON.stringify(body)}),
};

/** Look preset packs (backend api/look_presets.py). */
export type LookPreset = {id?: string; name: string; description?: string; effect_preset: string; effect_intensity: number; look: Record<string, any>; builtin?: boolean};
export type LookPack = {format: 'sceneforge-look-pack'; version: 1; presets: LookPreset[]};
export const lookPresetApi = {
  list: () => req<{presets: LookPreset[]; builtin: LookPreset[]; look_keys: string[]}>('/api/look-presets'),
  validate: (pack: unknown) => req<{ok: boolean; presets: LookPreset[]}>('/api/look-presets/validate', {method: 'POST', body: JSON.stringify(pack)}),
  importPack: (pack: unknown) => req<{added: LookPreset[]; presets: LookPreset[]}>('/api/look-presets', {method: 'POST', body: JSON.stringify(pack)}),
  remove: (id: string) => req<{presets: LookPreset[]}>(`/api/look-presets/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  fromScene: (sceneId: string, name: string) => req<LookPack>(`/api/look-presets/scene/${sceneId}?name=${encodeURIComponent(name)}`),
  exportPack: () => req<LookPack>('/api/look-presets/export'),
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
