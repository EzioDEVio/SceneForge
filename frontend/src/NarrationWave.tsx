import React, {useEffect, useState} from 'react';
import {VoiceTake, Waveform} from './api';
import {loadWaveform, WavePath} from './AudioClipEditor';

/** The used (trimmed) part of a take's waveform, drawn inside its timeline clip. */
export function NarrationWave({take}: {take: VoiceTake}) {
  const [wave, setWave] = useState<Waveform | null>(null);
  const id = take.audio_asset?.id;
  useEffect(() => {let live = true; if (id) loadWaveform(id).then(w => live && setWave(w)).catch(() => {}); return () => {live = false;};}, [id]);
  const src = take.measured_duration_ms || wave?.duration_ms || 0;
  if (!wave || !src) return null;
  const e = take.edit_json || {};
  const from = (e.in_ms || 0) / src, to = (e.out_ms ?? src) / src;
  return <WavePath peaks={wave.peaks} from={from} to={to} height={30} className="narration-wave"/>;
}
