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
  return <span className="narration-wave-wrap" style={{position:'relative',display:'block',height:30}}><WavePath peaks={wave.peaks} from={from} to={to} height={30} className="narration-wave"/>{(e.censor||[]).map((r,i)=>{const start=Math.max(r.start_ms/src,from),end=Math.min(r.end_ms/src,to);return end>start?<span key={i} className="audio-censor-band" aria-label={`${r.mode} narration range`} style={{position:'absolute',top:0,bottom:0,left:(start-from)/(to-from)*100+'%',width:(end-start)/(to-from)*100+'%',background:'#aa77dd55',pointerEvents:'none'}}/>:null;})}</span>;
}

/**
 * The used part of any audio or video asset's waveform (A2 clip sound, A3–A8 timeline clips),
 * like the waveform under a linked clip in other editors. Silently draws nothing for files
 * without audio.
 */
export function AssetWave({assetId, fromMs, toMs, height = 24, className = 'asset-wave'}: {assetId?: string | null; fromMs: number; toMs?: number | null; height?: number; className?: string}) {
  const [wave, setWave] = useState<Waveform | null>(null);
  useEffect(() => {let live = true; setWave(null); if (assetId) loadWaveform(assetId).then(w => live && setWave(w)).catch(() => {}); return () => {live = false;};}, [assetId]);
  const src = wave?.duration_ms || 0;
  if (!wave || !src) return null;
  const from = Math.max(0, Math.min(1, fromMs / src)), to = Math.max(from, Math.min(1, (toMs ?? src) / src));
  if (to - from <= 0) return null;
  return <WavePath peaks={wave.peaks} from={from} to={to} height={height} className={className}/>;
}
