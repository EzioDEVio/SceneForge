import type {Scene,Shot} from '../api';
export type SelectionBox={x:number;y:number;width:number;height:number};
/** Intersections use content coordinates, so zoom and scrolling do not change selection. */
export function scenesInBox(box:SelectionBox,clips:{id:string;box:SelectionBox}[]){
 if(box.width<4&&box.height<4)return [];
 return [...new Set(clips.filter(({box:r})=>box.x<r.x+r.width&&box.x+box.width>r.x&&box.y<r.y+r.height&&box.y+box.height>r.y).map(c=>c.id))];
}
/** Move selected scenes as a block while preserving their project order. */
export function reorderSceneSelection(ids:string[],dragged:string,selected:string[],target:string,after=false){
 if(!ids.includes(dragged)||!ids.includes(target))return ids;
 const moving=ids.filter(id=>id===dragged||selected.includes(dragged)&&selected.includes(id));
 if(moving.includes(target))return ids;
 const rest=ids.filter(id=>!moving.includes(id)),at=rest.indexOf(target)+(after?1:0);
 return [...rest.slice(0,at),...moving,...rest.slice(at)];
}
/** Mirror sequential render durations; selected media determine the picture sequence. */
export function sceneShotSegments(scene:Scene,duration:number){
 const selected=scene.shots.filter(s=>s.is_selected),shots=selected.length?selected:scene.shots;
 const intro=Math.max(0,Number((scene.look_json as any)?.countdown?.seconds||0)*1000),total=Math.max(1,duration-intro);
 const natural=(s:Shot)=>s.asset?.type==='video'&&s.asset.duration_ms?Math.round(Math.max(100,Math.min(s.source_out_ms||s.asset.duration_ms,s.asset.duration_ms)-(s.source_in_ms||0))/Math.max(.1,Math.min(4,s.speed_json?.speed||1)))+(s.speed_json?.freeze_at_ms!=null?Number((s.speed_json as any).freeze_ms||0):0):null;
 const plan:(number|null)[]=shots.map(s=>s.duration_ms||null),lengths=shots.map(natural);
 let budget=total-plan.reduce<number>((n,ms)=>n+(ms||0),0);
 const want=lengths.reduce<number>((n,ms,i)=>n+(plan[i]===null?ms||0:0),0);
 if(want&&want<=budget){lengths.forEach((ms,i)=>{if(plan[i]===null&&ms)plan[i]=ms;});budget-=want;}
 const rest=plan.filter(ms=>ms===null).length;const per=rest?Math.floor(budget/rest):0;
 const spans=plan.map(ms=>Math.max(1,ms??per));if(spans.length)spans[spans.length-1]=Math.max(1,total-spans.slice(0,-1).reduce((n,ms)=>n+ms,0));
 let cursor=intro;return shots.map((shot,i)=>{const start=cursor;cursor+=spans[i];return {shot,start,duration:spans[i]};});
}

/** Split-screen panels share scene time; tile their thumbnails without implying cuts. */
export function scenePictureTiles(scene:Scene,duration:number){
 const sequence=sceneShotSegments(scene,duration),layout=(scene.look_json as any)?.layout;
 if(!layout)return sequence;
 const count=({split2:2,split2v:2,split3:3,grid4:4} as Record<string,number>)[layout.type]||2;
 const panels=sequence.slice(0,count),size=duration/Math.max(1,panels.length);
 return panels.map((row,i)=>({...row,start:i*size,duration:size}));
}
