import {JSDOM} from 'jsdom';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';

const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost:8000'});
for(const key of ['window','document','navigator','HTMLElement','HTMLInputElement','HTMLTextAreaElement','Event','MouseEvent','CustomEvent','File','FormData'])Object.defineProperty(globalThis,key,{value:dom.window[key],configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
await build({entryPoints:['src/VideoGenerationPanel.tsx'],outfile:'node_modules/.cache/video-generation-test.cjs',bundle:true,platform:'node',format:'cjs',external:['react','react-dom'],logLevel:'silent'});
const require=createRequire(import.meta.url),React=require('react');
const {default:VideoGenerationPanel}=require('../node_modules/.cache/video-generation-test.cjs');
const {render,screen,waitFor,cleanup}=await import('@testing-library/react');
const {default:userEvent}=await import('@testing-library/user-event');

const models=[
  {id:'ltx-2.5-fast',provider:'local_comfy',provider_label:'Local · ComfyUI',name:'LTX-2.5 Fast',model:'LTX-2.5',kind:'local',price_per_second:0,resolutions:['480p','720p'],ratios:['16:9','9:16','1:1','custom'],duration_min:1,duration_max:20,durations:[],native_audio:true,requirements:'Local test model',workflow_url:'https://docs.ltx.io',workflow_imported:true,cost_note:'No API fee.'},
  {id:'custom-comfy-workflow',provider:'local_comfy',provider_label:'Local · ComfyUI',name:'Custom ComfyUI workflow',model:'user-supplied',kind:'local',price_per_second:0,resolutions:['480p','720p'],ratios:['16:9','9:16','1:1','custom'],duration_min:1,duration_max:30,durations:[],native_audio:null,requirements:'Trusted workflow',workflow_url:'https://docs.comfy.org',workflow_imported:false,cost_note:'No API fee.'},
  {id:'veo-3.1-lite',provider:'google_veo',provider_label:'Google Gemini API',name:'Veo 3.1 Lite',model:'veo-3.1-lite-generate-preview',kind:'cloud',price_per_second:{'720p':0.05,'1080p':0.08},resolutions:['720p','1080p'],ratios:['16:9','9:16'],duration_min:4,duration_max:8,durations:[4,6,8],native_audio:true,requirements:'Cloud test model',workflow_url:'https://ai.google.dev',cost_note:'Google list price per second.'},
];
let profiles=[{id:'local-profile',capability:'video',name:'local_comfy',configured:true,base_url:'http://127.0.0.1:8188',model:'ComfyUI'}];
let generationRequest=null,added=null,captionsFor=null,closed=0;
const asset={id:'generated-1',type:'video',original_filename:'generated.mp4',width:720,height:1280,duration_ms:5000,origin:'generated'};
globalThis.fetch=async(path,init={})=>{
  const method=init.method||'GET';
  let result;
  if(path==='/api/video-generation/catalog')result={models,prices_checked:'2026-09-28'};
  else if(path==='/api/video-generation/local/status')result={ready:true,message:'ComfyUI is connected.'};
  else if(path==='/api/providers')result=profiles;
  else if(path==='/api/video-generation/projects/project-1/generate'){generationRequest=JSON.parse(init.body);result={job_id:'job-1'};}
  else if(path==='/api/jobs/job-1')result={id:'job-1',project_id:'project-1',scene_id:null,scope:'video_generation',status:'succeeded',stage:'video ready in Media Pool',progress:100,error:null,artifact_asset_id:'generated-1'};
  else if(path==='/api/assets/generated-1')result=asset;
  else if(path==='/api/jobs/job-1/cancel'&&method==='POST')result={ok:true};
  else throw new Error(`Unhandled API request: ${method} ${path}`);
  return {ok:true,status:200,json:async()=>structuredClone(result)};
};
const project={id:'project-1',title:'Video test',aspect:'9:16',fps:30,width:720,height:1280,scenes:[]};
const props={project,selectedSceneId:'scene-1',onClose:()=>{closed++;},onOpenSettings:()=>{},onAdd:async(id,placement)=>{added={id,placement};return 'scene-1';},onCaptions:async(id)=>{captionsFor=id;}};
const user=userEvent.setup();

try{
  const view=render(React.createElement(VideoGenerationPanel,props));
  await screen.findByRole('dialog',{name:'Generate video from text'});
  await screen.findByText('ComfyUI is connected.');
  await user.type(screen.getByLabelText('Prompt'), 'A moonlit desert with a slow camera push');
  await user.selectOptions(screen.getByLabelText('Aspect ratio'),'custom');
  const width=screen.getByLabelText('Width'),height=screen.getByLabelText('Height');
  await user.clear(width);await user.type(width,'768');
  await user.clear(height);await user.type(height,'1344');
  const generate=screen.getByRole('button',{name:'Generate video'});
  assert.equal(generate.disabled,false,'valid local dimensions should enable generation');
  await user.click(generate);
  await waitFor(()=>assert.ok(generationRequest));
  assert.deepEqual([generationRequest.aspect_ratio,generationRequest.width,generationRequest.height],['custom',768,1344]);
  assert.equal(generationRequest.confirm_paid,false,'local generation does not require paid confirmation');
  await screen.findByText('Generated video is ready');
  await user.click(screen.getByRole('button',{name:'Add to timeline'}));
  await screen.findByRole('button',{name:/Generate captions & open Text/});
  assert.deepEqual(added,{id:'generated-1',placement:'after'});
  await user.click(screen.getByRole('button',{name:/Generate captions & open Text/}));
  await waitFor(()=>assert.equal(captionsFor,'scene-1'));
  assert.equal(closed,1,'caption handoff closes the generator so Text can be edited');
  console.log('PASS local custom-ratio generation, asset insertion, and caption-to-Text handoff');
  view.unmount();cleanup();

  profiles=[{id:'google-profile',capability:'video',name:'google_veo',configured:true,base_url:null,model:'veo-3.1'}];
  generationRequest=null;closed=0;
  render(React.createElement(VideoGenerationPanel,props));
  await screen.findByRole('dialog',{name:'Generate video from text'});
  await user.click(screen.getByRole('tab',{name:'Google Veo'}));
  await screen.findByText(/Published rates: 720p \$0\.05\/sec/);
  await user.type(screen.getByLabelText('Prompt'),'A red kite above the sea');
  await user.click(screen.getByRole('checkbox'));
  await user.click(screen.getByRole('button',{name:/Generate and confirm charge/}));
  await waitFor(()=>assert.ok(generationRequest));
  assert.equal(generationRequest.confirm_paid,true,'cloud generation sends paid-cost consent to the backend');
  assert.equal(generationRequest.duration_seconds,4,'Veo uses a supported duration');
  assert.equal(generationRequest.resolution,'720p');
  console.log('PASS cloud model list price and explicit paid-generation consent');
}finally{cleanup();dom.window.close();}
