import React from 'react';
export const routeIconUrl=(kind:string)=>`/api/route-icons/${kind}`;
/** The source monitor shows the completed journey. Render draft previews its timing. */
export function RouteDestination({route,aspect,editing=false}:{route:any;aspect:number;editing?:boolean}){
 if(!route?.points||route.points.length<2)return null;
 const p=route.points.at(-1),before=route.points.at(-2),size=10;
 const icon=['plane','ship','car','pin'].includes(route.marker);
 let angle=Math.atan2(p[1]-before[1],(p[0]-before[0])*aspect)*180/Math.PI+(route.marker==='plane'?45:0);
 let flip=1;if(['car','ship'].includes(route.marker)){const right=p[0]>=before[0];flip=(route.marker==='car'?right:!right)?-1:1;if(angle>90)angle-=180;else if(angle< -90)angle+=180;}
 return <div className="route-completed-preview" aria-label="Completed route preview" style={{position:'absolute',inset:0,zIndex:4,pointerEvents:'none'}}>
  {!editing&&<svg className="route-destination" viewBox={`0 0 ${100*aspect} 100`} style={{width:'100%',height:'100%'}}>
   {route.pins&&route.points.map((point:number[],i:number)=><circle key={i} cx={point[0]*aspect} cy={point[1]} r={1.3} fill={route.color} stroke="white" strokeWidth={.4}/>)}
   {icon&&<image href={routeIconUrl(route.marker)} x={p[0]*aspect-size/2} y={route.marker==='pin'?p[1]-size:p[1]-size/2} width={size} height={size} transform={route.marker==='pin'?undefined:`translate(${p[0]*aspect} ${p[1]}) rotate(${angle}) scale(${flip} 1) translate(${-p[0]*aspect} ${-p[1]})`}/>}
  </svg>}
  {route.points.map((point:number[],i:number)=>route.labels?.[i]&&<span key={i} className="route-preview-label" data-route-stop={i+1} dir="auto" style={{left:`${Math.max(2,Math.min(98,point[0]))}%`,top:`${Math.max(8,Math.min(92,point[1]))}%`,transform:`translate(${point[0]<20?'0':point[0]>80?'-100%':'-50%'}, ${point[1]<15?'20%':'-150%'})`,fontSize:`clamp(9px,${3.4/aspect}cqw,36px)`}}>{route.labels[i]}</span>)}
 </div>;
}
