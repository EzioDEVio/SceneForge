'use strict';
const {spawn}=require('node:child_process');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
function isOwnURL(value,origin){try{return new URL(value).origin===origin}catch{return false}}
function startBackend({executable,args=[],resources,dataDir,ffmpegDir,timeoutMs=45000,onExit=()=>{}}){
 fs.mkdirSync(path.join(dataDir,'logs'),{recursive:true});
 const log=fs.createWriteStream(path.join(dataDir,'logs','desktop-backend.log'),{flags:'a'});
 const token=crypto.randomBytes(32).toString('hex');
 const ext=process.platform==='win32'?'.exe':'';
 const child=spawn(executable,args,{windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...process.env,SCENEFORGE_DESKTOP_TOKEN:token,SCENEFORGE_DATA_DIR:dataDir,SCENEFORGE_RESOURCE_DIR:resources,SCENEFORGE_FFMPEG:path.join(ffmpegDir,'ffmpeg'+ext),SCENEFORGE_FFPROBE:path.join(ffmpegDir,'ffprobe'+ext),SCENEFORGE_SD_AUTOSTART:process.env.SCENEFORGE_SD_AUTOSTART||'1',PYTHONUNBUFFERED:'1'}});
 let stopping=false,buffer='',ready=false,timer;
 const launched=new Promise((resolve,reject)=>{
  timer=setTimeout(()=>reject(Error('The local editor did not become ready within 45 seconds. See desktop-backend.log.')),timeoutMs);
  child.once('error',reject);
  child.once('exit',(code)=>{if(!ready)reject(Error(`Backend exited before startup (code ${code}). See desktop-backend.log.`));});
  child.stdout.on('data',chunk=>{
   buffer+=chunk.toString();let end;
   while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);
    if(line.startsWith('SCENEFORGE_READY ')){
     try{const msg=JSON.parse(line.slice(17));if(!Number.isInteger(msg.port)||msg.port<1||msg.port>65535)throw Error('Invalid backend port');ready=true;clearTimeout(timer);resolve({origin:`http://127.0.0.1:${msg.port}`,token});}catch(e){reject(e);}
    }else log.write(line+'\n');
   }
   if(buffer.length>65536){log.write(buffer);buffer='';}
  });
 });
 child.stderr.pipe(log,{end:false});
 child.once('exit',(code)=>{clearTimeout(timer);log.end();if(ready&&!stopping)onExit(code)});
 async function stop(){
  stopping=true;clearTimeout(timer);
  if(child.exitCode!==null)return;
  child.stdin.end();
  await new Promise(resolve=>{
   const kill=setTimeout(()=>{
    if(child.exitCode===null){
     if(process.platform==='win32')spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
     else child.kill('SIGKILL');
    }resolve();
   },5000);
   child.once('exit',()=>{clearTimeout(kill);resolve()});
  });
 }
 return {launched,stop,child};
}
module.exports={startBackend,isOwnURL};
