'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const u = require('../updates.cjs');
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'sf-upd-'));

test('first run records the version without a backup', () => {
  const ws = tmp(); fs.writeFileSync(path.join(ws, 'sceneforge.db'), 'v1');
  assert.equal(u.backupOnVersionChange(ws, '0.3.0'), null);
  assert.equal(JSON.parse(fs.readFileSync(path.join(ws, 'app-state.json'))).lastVersion, '0.3.0');
});
test('a new version backs up the database before it is opened', () => {
  const ws = tmp(); fs.writeFileSync(path.join(ws, 'sceneforge.db'), 'projects-v030');
  u.backupOnVersionChange(ws, '0.3.0');
  const b = u.backupOnVersionChange(ws, '0.3.1');
  assert.ok(b && fs.readFileSync(b, 'utf8') === 'projects-v030' && path.basename(b).includes('before-0.3.1'));
  assert.equal(u.backupOnVersionChange(ws, '0.3.1'), null, 'same version again: no extra backup');
});
test('only the last 5 backups are kept', () => {
  const ws = tmp(); fs.writeFileSync(path.join(ws, 'sceneforge.db'), 'x');
  for (let i = 0; i < 8; i++) u.backupDatabase(ws, 'v' + i, new Date(Date.UTC(2026, 0, 1, 0, 0, i)));
  const left = fs.readdirSync(path.join(ws, 'backups'));
  assert.equal(left.length, u.KEEP_BACKUPS);
  assert.ok(left.some(f => f.includes('v7')) && !left.some(f => f.includes('v0')));
});
test('projects carry over from the old "Desktop Alpha" name, once, without touching the old folder', () => {
  const appData = tmp();
  const legacy = path.join(appData, 'SceneForge Desktop Alpha', 'workspace');
  fs.mkdirSync(path.join(legacy, 'media'), {recursive: true});
  fs.writeFileSync(path.join(legacy, 'sceneforge.db'), 'old-projects'); fs.writeFileSync(path.join(legacy, 'media', 'a.png'), 'img');
  const ws = path.join(appData, 'SceneForge Studio', 'workspace');
  assert.equal(u.migrateLegacyWorkspace(appData, ws), legacy);
  assert.equal(fs.readFileSync(path.join(ws, 'sceneforge.db'), 'utf8'), 'old-projects');
  assert.ok(fs.existsSync(path.join(ws, 'media', 'a.png')) && fs.existsSync(path.join(legacy, 'sceneforge.db')));
  fs.writeFileSync(path.join(ws, 'sceneforge.db'), 'new-work');
  assert.equal(u.migrateLegacyWorkspace(appData, ws), null, 'never overwrites an existing workspace');
  assert.equal(fs.readFileSync(path.join(ws, 'sceneforge.db'), 'utf8'), 'new-work');
});
test('beta channel setting persists', () => {
  const ud = tmp();
  assert.equal(u.loadSettings(ud).beta, false);
  u.saveSettings(ud, {beta: true});
  assert.equal(u.loadSettings(ud).beta, true);
});

test('Stable Diffusion automatic start is switched off once, keeping the folder', () => {
  const ws = tmp();
  fs.writeFileSync(path.join(ws, 'local-images.json'), JSON.stringify({folder: 'C:/sd', autostart: true}));
  assert.equal(u.reviewSdAutostart(ws), true);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(ws, 'local-images.json'))), {folder: 'C:/sd', autostart: false});
  fs.writeFileSync(path.join(ws, 'local-images.json'), JSON.stringify({folder: 'C:/sd', autostart: true}));
  assert.equal(u.reviewSdAutostart(ws), false, 'if the user turns it back on, it stays on');
});
