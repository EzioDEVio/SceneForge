const {test}=require('node:test');const assert=require('node:assert/strict');
const {isOwnURL,startBackend}=require('../backend-process.cjs');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
test('backend credentials only attach to its exact origin',()=>{
 assert(isOwnURL('http://127.0.0.1:4321/api/projects','http://127.0.0.1:4321'));
 for(const url of ['http://127.0.0.1:4322','https://example.com','http://127.0.0.1:4321.evil.example','file:///tmp/x'])assert(!isOwnURL(url,'http://127.0.0.1:4321'));
});
test('child startup protocol, private token and cooperative shutdown',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sf-child-'));
 const source=path.join(dir,'fake.cjs');fs.writeFileSync(source,"console.log('SCENEFORGE_READY '+JSON.stringify({port:4321}));process.stdin.resume();process.stdin.on('end',()=>process.exit(0));");
 const b=startBackend({executable:process.execPath,args:[source],resources:dir,dataDir:dir,ffmpegDir:dir});
 const ready=await b.launched;assert.equal(ready.origin,'http://127.0.0.1:4321');assert.equal(ready.token.length,64);await b.stop();assert.equal(b.child.exitCode,0);
});
test('startup failure is reported instead of waiting forever',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sf-child-'));
 const b=startBackend({executable:process.execPath,args:['-e','process.exit(7)'],resources:dir,dataDir:dir,ffmpegDir:dir});
 await assert.rejects(b.launched,/code 7/);await b.stop();
});
