'use strict';
// The only bridge between the editor page and the desktop shell: a few named actions.
// No Node.js APIs are exposed; main.cjs checks that every call comes from the app's own page.
const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('sceneforgeDesktop', {
  info: () => ipcRenderer.invoke('sf:info'),
  checkForUpdates: () => ipcRenderer.invoke('sf:check-updates'),
  setBeta: on => ipcRenderer.invoke('sf:set-beta', !!on),
  chooseSdFolder: () => ipcRenderer.invoke('sf:choose-sd-folder'),
  openExternal: url => ipcRenderer.invoke('sf:open-external', String(url)),
  openLogs: () => ipcRenderer.invoke('sf:open-logs'),
  collectDiagnostics: () => ipcRenderer.invoke('sf:diagnostics'),
});
