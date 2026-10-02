// Keyframe interpolation for overlays and text layers. Mirrors backend/app/render/keyframes.py
// (value_at) so the editor canvas previews the same motion the render produces.
//
// A keyframe's t_ms is relative to the layer's start. Missing values fall back to the
// layer's own value. `ease` shapes the segment that leaves the keyframe.
export type Ease='linear'|'ease_in'|'ease_out'|'ease_in_out';
export const EASES:[Ease,string][]=[['linear','Linear'],['ease_in','Ease in'],['ease_out','Ease out'],['ease_in_out','Ease in-out']];
export type Keyframe={t_ms:number;x?:number;y?:number;width?:number;size?:number;rotation?:number;opacity?:number;ease?:Ease};
export const MAX_KEYFRAMES=32;
/** Properties keyframes animate, per layer kind. */
export const OVERLAY_KEYS=['x','y','width','rotation','opacity'] as const;
export const TEXT_KEYS=['x','y','size','rotation','opacity'] as const;
type Prop=typeof OVERLAY_KEYS[number]|typeof TEXT_KEYS[number];

export function ease(name:Ease|undefined,p:number){
  p=Math.max(0,Math.min(1,p));
  if(name==='ease_in')return p*p;
  if(name==='ease_out')return 1-(1-p)*(1-p);
  if(name==='ease_in_out')return 0.5-0.5*Math.cos(Math.PI*p);
  return p;
}
export function sortKeyframes(kfs:Keyframe[]){return [...kfs].sort((a,b)=>a.t_ms-b.t_ms);}
/** Value of `prop` at `tMs` (relative to the layer start). */
export function valueAt(kfs:Keyframe[]|undefined|null,prop:Prop,base:number,tMs:number){
  if(!kfs?.length)return base;
  const ks=sortKeyframes(kfs),vals=ks.map(k=>k[prop]??base);
  let v=vals[0];
  for(let i=0;i<ks.length-1;i++){const t0=ks[i].t_ms,t1=ks[i+1].t_ms;v+=(vals[i+1]-vals[i])*ease(ks[i].ease,(tMs-t0)/Math.max(1e-9,t1-t0));}
  return v;
}
type OverlayLike={x:number;y:number;width:number;rotation:number;opacity:number;start_ms:number;keyframes?:Keyframe[]|null};
type TextLike={x:number;y:number;size:number;start_ms:number;keyframes?:Keyframe[]|null;rotation?:number;opacity?:number};
const round2=(v:number)=>Math.round(v*100)/100;
/** The overlay as it looks at scene time `sceneMs` (unchanged without keyframes). */
export function overlayAt<T extends OverlayLike>(o:T,sceneMs:number):T{
  if(!o.keyframes?.length)return o;
  const t=sceneMs-(o.start_ms||0),out:any={...o};
  for(const k of OVERLAY_KEYS)out[k]=round2(valueAt(o.keyframes,k,o[k],t));
  return out;
}
/** A text layer at `sceneMs`; adds rotation/opacity (0 / 100 when not keyframed). */
export function textLayerAt<T extends TextLike>(l:T,sceneMs:number):T&{rotation:number;opacity:number}{
  if(!l.keyframes?.length)return l as any;
  const t=sceneMs-(l.start_ms||0);
  return {...l,x:round2(valueAt(l.keyframes,'x',l.x,t)),y:round2(valueAt(l.keyframes,'y',l.y,t)),size:round2(valueAt(l.keyframes,'size',l.size,t)),rotation:round2(valueAt(l.keyframes,'rotation',0,t)),opacity:round2(valueAt(l.keyframes,'opacity',100,t))};
}
/** Insert or replace (within `toleranceMs`) a keyframe; result stays sorted and capped. */
export function upsertKeyframe(kfs:Keyframe[]|undefined|null,k:Keyframe,toleranceMs=40):Keyframe[]{
  const list=kfs||[],hit=list.findIndex(x=>Math.abs(x.t_ms-k.t_ms)<=toleranceMs);
  if(hit>=0)return sortKeyframes(list.map((x,i)=>i===hit?{...x,...k,t_ms:x.t_ms}:x));
  if(list.length>=MAX_KEYFRAMES)return list;
  return sortKeyframes([...list,{ease:'linear',...k}]);
}
export function removeKeyframe(kfs:Keyframe[]|undefined|null,tMs:number):Keyframe[]{return (kfs||[]).filter(k=>k.t_ms!==tMs);}
/** Capture the current (interpolated) values of a layer as a keyframe at layer time `t`. */
export function captureKeyframe(values:Record<string,number>,keys:readonly string[],t:number,easeName:Ease='linear'):Keyframe{
  const k:any={t_ms:Math.max(0,Math.round(t)),ease:easeName};
  for(const key of keys)if(Number.isFinite(values[key]))k[key]=round2(values[key]);
  return k;
}
/** Route an edit of animated properties to the keyframe at the playhead (creating one) when
 *  the layer is keyframed; other properties (and un-keyframed layers) change directly. */
export function keyframedPatch<T extends {start_ms:number;keyframes?:Keyframe[]|null}>(layer:T,patch:Partial<T>,keys:readonly string[],current:Record<string,number>,sceneMs:number):Partial<T>{
  if(!layer.keyframes?.length)return patch;
  const animated=Object.keys(patch).filter(k=>keys.includes(k));
  if(!animated.length)return patch;
  const rest:any={...patch};for(const k of animated)delete rest[k];
  const t=Math.max(0,Math.round(sceneMs-(layer.start_ms||0)));
  const at=layer.keyframes.find(k=>Math.abs(k.t_ms-t)<=40);
  const values:any={...current};for(const k of animated)values[k]=Number((patch as any)[k]);
  const k=captureKeyframe(values,keys,at?at.t_ms:t,at?.ease||'linear');
  return {...rest,keyframes:upsertKeyframe(layer.keyframes,k)};
}
