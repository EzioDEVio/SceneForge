import type {Scene} from './api';

/** Scene length as the timeline and renderer see it (trimmed audio included). */
export function sceneDuration(scene:Scene) {
  // A countdown intro effect plays before the scene and adds its length.
  const cd=((scene.look_json as any)?.countdown?.seconds||0)*1000;
  return baseDuration(scene)+cd;
}
function baseDuration(scene:Scene) {
  if(scene.timing_mode==='fixed'&&scene.requested_duration_ms)return scene.requested_duration_ms;
  const take=scene.voice_takes.find(t=>t.accepted);
  const audioMs=take?.effective_duration_ms??take?.measured_duration_ms;
  if(audioMs)return audioMs+(scene.lead_ms??250)+(scene.trail_ms??400);
  // No narration and no fixed length: as long as the scene's videos (renderer does the same).
  return scene.natural_duration_ms||scene.measured_duration_ms||scene.requested_duration_ms||4000;
}
