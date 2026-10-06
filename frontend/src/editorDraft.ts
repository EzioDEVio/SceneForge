import type {Scene} from './api';
export type EditorEdits = {scene:Record<string,any>; shots:{id:string;patch:Record<string,any>}[];revision?:number;replace?:boolean};
export const emptyEdits = ():EditorEdits=>({scene:{},shots:[]});
export function mergeEdits(a:EditorEdits,b:Partial<EditorEdits>):EditorEdits {
 const scene={...a.scene,...b.scene};
 for(const key of ['look','font']) if(b.scene?.[key])scene[key]={...a.scene[key],...b.scene[key]};
 const shots=a.shots.map(s=>({...s,patch:{...s.patch}}));
 for(const row of b.shots||[]){const old=shots.find(s=>s.id===row.id);if(old)old.patch={...old.patch,...row.patch};else shots.push(row);}
 return {scene,shots,revision:a.revision??b.revision};
}
export function draftScene(saved:Scene,e:EditorEdits):Scene {
 const out={...saved,...e.scene,...('overlays'in e.scene?{overlays_json:e.scene.overlays}:{}),...('transition_in'in e.scene?{transition_in_json:e.scene.transition_in}:{}),font_json:{...saved.font_json,...e.scene.font},look_json:{...saved.look_json,...e.scene.look}};
 for(const key of Object.keys(out.look_json))if((out.look_json as any)[key]===null)delete (out.look_json as any)[key];
 out.shots=saved.shots.map(s=>{const p=e.shots.find(x=>x.id===s.id)?.patch||{};return {...s,...p,...('motion'in p?{motion_json:p.motion}:{}),...('crop'in p?{crop_json:p.crop}:{}),...('speed'in p?{speed_json:p.speed}:{})};});
 return out;
}
export function previousEdits(s:Scene,e:EditorEdits):EditorEdits {
 const scene:Record<string,any>={};
 for(const k of Object.keys(e.scene))scene[k]=(s as any)[({font:'font_json',look:'look_json',overlays:'overlays_json',transition_in:'transition_in_json'} as any)[k]||k];
 return {scene,replace:true,shots:e.shots.map(row=>{const shot=s.shots.find(x=>x.id===row.id)!;return {id:row.id,patch:Object.fromEntries(Object.keys(row.patch).map(k=>[k,(shot as any)[({crop:'crop_json',motion:'motion_json',speed:'speed_json'} as any)[k]||k]??null]))};})};
}
