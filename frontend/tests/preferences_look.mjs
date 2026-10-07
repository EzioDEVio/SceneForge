// Director's Desk look (RC3): default theme, one-time move from the old default, explicit choices kept.
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
await build({stdin:{contents:"export * from './src/preferences';",resolveDir:process.cwd(),loader:'ts'},bundle:true,format:'cjs',platform:'node',outfile:'node_modules/.cache/prefs.cjs',logLevel:'silent'});
const require=createRequire(import.meta.url);
const {readPreferences,writePreferences,DEFAULT_PREFERENCES}=require('../node_modules/.cache/prefs.cjs');
let passed=0;const check=(n,c)=>{assert.ok(c,n);console.log('PASS '+n);passed++;};
const store=v=>({getItem:()=>v===undefined?null:JSON.stringify(v)});
check("new installs start on Director's Desk with the cyan accent",DEFAULT_PREFERENCES.theme==='desk'&&readPreferences(store()).theme==='desk'&&readPreferences(store()).accent==='cyan');
check('people on the old default theme and accent move to the new look once',(p=>p.theme==='desk'&&p.accent==='cyan')(readPreferences(store({theme:'graphite',accent:'violet',density:'comfortable'}))));
check('their other preferences are kept during the move',readPreferences(store({theme:'graphite',density:'comfortable',reduceMotion:true})).density==='comfortable');
check('a theme chosen on purpose (Daylight) is never replaced',readPreferences(store({theme:'light',accent:'blue'})).theme==='light'&&readPreferences(store({theme:'light',accent:'blue'})).accent==='blue');
check('after the move, choosing Graphite Night again is respected',readPreferences(store({theme:'graphite',accent:'violet',look:2})).theme==='graphite');
let saved;writePreferences({...DEFAULT_PREFERENCES,theme:'graphite'},{setItem:(k,v)=>saved=JSON.parse(v)});
check('saved preferences record the new look version',saved.look===2&&saved.theme==='graphite');
check('unknown stored values fall back to the default look',readPreferences(store({theme:'neon',accent:'pink',look:2})).theme==='desk');
console.log(passed+' preference look checks passed');
