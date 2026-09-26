'use strict';
// Updates and upgrade safety for SceneForge Studio (GPL-3.0-or-later).
//
// * Before a new app version first opens the workspace, the project database
//   is backed up (the backend may migrate it). The last 5 backups are kept.
// * The workspace of the old "SceneForge Desktop Alpha" name is copied over
//   once, so projects carry across the rename. The old folder is not touched.
// * Updates come from GitHub Releases (electron-updater). Windows and Linux
//   (AppImage) download in the background and ask to restart; macOS apps are
//   unsigned, so macOS only announces the update and opens the release page.
const fs = require('node:fs');
const path = require('node:path');

const KEEP_BACKUPS = 5;
const LEGACY_NAMES = ['SceneForge Desktop Alpha'];
const RELEASES_URL = 'https://github.com/EzioDEVio/SceneForge/releases/latest';

function readJSON(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}
function writeJSON(file, value) {
  fs.mkdirSync(path.dirname(file), {recursive: true});
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2));
  fs.renameSync(tmp, file);
}

/** Copy the workspace from an older app name, once, if the new one is empty. */
function migrateLegacyWorkspace(appDataDir, workspaceDir) {
  if (fs.existsSync(path.join(workspaceDir, 'sceneforge.db'))) return null;
  for (const name of LEGACY_NAMES) {
    const legacy = path.join(appDataDir, name, 'workspace');
    if (fs.existsSync(path.join(legacy, 'sceneforge.db'))) {
      fs.mkdirSync(path.dirname(workspaceDir), {recursive: true});
      fs.cpSync(legacy, workspaceDir, {recursive: true, errorOnExist: false, force: false});
      return legacy;
    }
  }
  return null;
}

/** Back up the database when the app version changed since the last run.
 *  Must run BEFORE the backend starts (it may upgrade the database). */
function backupOnVersionChange(workspaceDir, version, now = new Date()) {
  const stateFile = path.join(workspaceDir, 'app-state.json');
  const state = readJSON(stateFile, {});
  const db = path.join(workspaceDir, 'sceneforge.db');
  let backup = null;
  if (state.lastVersion && state.lastVersion !== version && fs.existsSync(db)) {
    backup = backupDatabase(workspaceDir, `before-${version}`, now);
  }
  writeJSON(stateFile, {...state, lastVersion: version});
  return backup;
}

function backupDatabase(workspaceDir, label, now = new Date()) {
  const db = path.join(workspaceDir, 'sceneforge.db');
  if (!fs.existsSync(db)) return null;
  const dir = path.join(workspaceDir, 'backups');
  fs.mkdirSync(dir, {recursive: true});
  const stamp = now.toISOString().replace(/[:.]/g, '-');
  const target = path.join(dir, `sceneforge-${label.replace(/[^\w.-]/g, '_')}-${stamp}.db`);
  fs.copyFileSync(db, target);
  const all = fs.readdirSync(dir).filter(f => f.startsWith('sceneforge-') && f.endsWith('.db')).sort();
  for (const old of all.slice(0, Math.max(0, all.length - KEEP_BACKUPS))) fs.rmSync(path.join(dir, old), {force: true});
  return target;
}

/** Once per workspace: switch off Stable Diffusion's automatic start (a heavy engine that
 *  can make the whole computer slow while it starts). Returns true when it was switched off,
 *  so the app can explain how to turn it back on. */
function reviewSdAutostart(workspaceDir) {
  const stateFile = path.join(workspaceDir, 'app-state.json');
  const state = readJSON(stateFile, {});
  if (state.sdAutostartReviewed) return false;
  const sdFile = path.join(workspaceDir, 'local-images.json');
  const sd = readJSON(sdFile, null);
  let changed = false;
  if (sd && sd.autostart) {
    writeJSON(sdFile, {...sd, autostart: false});
    changed = true;
  }
  writeJSON(stateFile, {...state, sdAutostartReviewed: true});
  return changed;
}

/** Plain-language reason for an update-check failure. */
function explainUpdateError(err) {
  const m = String((err && (err.message || err)) || '');
  if (/404|Cannot find latest|No published versions|latest\.yml|HttpError: 404/i.test(m))
    return {kind: 'no-release', message: 'No published release was found yet. (Draft releases are not visible to the app.) Try again once a release is published.'};
  if (/ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNREFUSED|ECONNRESET|net::ERR_|getaddrinfo|socket hang up|network/i.test(m))
    return {kind: 'offline', message: 'Could not reach GitHub. Check your internet connection and try again.'};
  if (/rate limit|403/i.test(m))
    return {kind: 'rate-limit', message: 'GitHub is limiting requests right now. Try again in a little while.'};
  return {kind: 'error', message: 'The update check failed: ' + m.slice(0, 300)};
}

function loadSettings(userDataDir) { return readJSON(path.join(userDataDir, 'update-settings.json'), {beta: false}); }
function saveSettings(userDataDir, settings) { writeJSON(path.join(userDataDir, 'update-settings.json'), settings); }

/** Wire electron-updater. Returns {check(manual)} for the Help menu. */
function setupUpdates({app, dialog, shell, getWindow, workspaceDir, userDataDir, log = () => {}}) {
  let autoUpdater;
  try { ({autoUpdater} = require('electron-updater')); } catch (e) { log('updater unavailable: ' + e.message); return {check: async () => {}}; }
  const mac = process.platform === 'darwin';
  const settings = loadSettings(userDataDir);
  autoUpdater.autoDownload = !mac;
  autoUpdater.autoInstallOnAppQuit = !mac;
  autoUpdater.allowPrerelease = !!settings.beta;
  autoUpdater.logger = {info: log, warn: log, error: log, debug: () => {}};
  let manual = false, prompted = false;

  autoUpdater.on('update-available', async info => {
    if (!mac) return;                      // Windows/Linux download silently
    const r = await dialog.showMessageBox(getWindow(), {type: 'info', title: 'Update available',
      message: `SceneForge ${info.version} is available`, detail: 'Download it from the releases page and replace the app in Applications. Your projects are kept.',
      buttons: ['Open download page', 'Later'], defaultId: 0, cancelId: 1});
    if (r.response === 0) shell.openExternal(RELEASES_URL);
  });
  autoUpdater.on('update-not-available', () => {
    if (manual) dialog.showMessageBox(getWindow(), {type: 'info', message: 'SceneForge is up to date', detail: `You have version ${app.getVersion()}.`});
    manual = false;
  });
  autoUpdater.on('error', err => {
    log('update error: ' + (err && err.message));
    manual = false;   // manual checks report through check() instead
  });
  autoUpdater.on('update-downloaded', async info => {
    if (prompted) return;
    prompted = true;
    try { backupDatabase(workspaceDir, `before-${info.version}`); } catch (e) { log('backup failed: ' + e.message); }
    const r = await dialog.showMessageBox(getWindow(), {type: 'info', title: 'Update ready',
      message: `SceneForge ${info.version} is ready to install`,
      detail: 'Restart now to update, or it installs automatically the next time you close SceneForge. Your projects are backed up first.',
      buttons: ['Restart and update', 'Later'], defaultId: 0, cancelId: 1});
    if (r.response === 0) setImmediate(() => autoUpdater.quitAndInstall());
  });

  /** Check for updates. With `isManual`, the result is shown to the user.
   *  Returns {status: 'up-to-date'|'available'|'error', version?, message}. */
  async function check(isManual = false) {
    let result;
    try {
      const r = await autoUpdater.checkForUpdates();
      const latest = r && r.updateInfo && r.updateInfo.version;
      const available = r && (r.isUpdateAvailable ?? (latest && latest !== app.getVersion()));
      result = available
        ? {status: 'available', version: latest, message: mac ? `SceneForge ${latest} is available to download.` : `SceneForge ${latest} is downloading; you will be asked to restart when it is ready.`}
        : {status: 'up-to-date', version: app.getVersion(), message: `You have the latest version (${app.getVersion()}).`};
    } catch (e) {
      log('check failed: ' + (e && e.message));
      result = {status: 'error', ...explainUpdateError(e)};
    }
    if (isManual && result.status !== 'available') {   // 'available' shows its own prompts
      await dialog.showMessageBox(getWindow(), {type: result.status === 'error' ? 'warning' : 'info',
        message: result.status === 'error' ? 'Could not check for updates' : 'SceneForge is up to date', detail: result.message});
    }
    return result;
  }
  function setBeta(on) {
    saveSettings(userDataDir, {...loadSettings(userDataDir), beta: !!on});
    autoUpdater.allowPrerelease = !!on;
    return {beta: !!on, message: on ? 'Beta updates are on. You will be offered test versions before they are released to everyone.' : 'Beta updates are off. You will only receive regular releases.'};
  }
  return {check, setBeta, beta: () => !!loadSettings(userDataDir).beta};
}

module.exports = {explainUpdateError, migrateLegacyWorkspace, backupOnVersionChange, reviewSdAutostart, backupDatabase, loadSettings, saveSettings, setupUpdates, KEEP_BACKUPS, RELEASES_URL};
