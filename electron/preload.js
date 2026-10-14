const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronLockdown', {
    isLockdown: true,
    version: '1.0.0',
    notifyFocusLost: () => ipcRenderer.send('exam-focus-lost'),
    requestExitExam: (teacherKey) => ipcRenderer.invoke('request-exit-exam', teacherKey)
});

// Inform the window on load
window.addEventListener('DOMContentLoaded', () => {
    window.isEnterpriseLockdownBrowser = true;
});
