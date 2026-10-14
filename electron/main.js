const { app, BrowserWindow, globalShortcut, dialog, ipcMain, Menu } = require('electron');
const path = require('path');

let mainWindow = null;

// Parse server URL from arguments or environment, default to DGX Spark IP
const defaultServer = process.env.EXAM_SERVER_URL || 'http://192.168.10.252:8088';
let serverUrl = defaultServer;

for (const arg of process.argv) {
    if (arg.startsWith('--server=')) {
        serverUrl = arg.split('=')[1];
    }
}

// Master Invigilator override password to exit kiosk
const TEACHER_EXIT_PIN = process.env.EXAM_EXIT_PIN || 'DLADMIN2026';

function createWindow() {
    Menu.setApplicationMenu(null); // Strip all menu bars

    mainWindow = new BrowserWindow({
        width: 1920,
        height: 1080,
        fullscreen: true,
        kiosk: true,
        alwaysOnTop: true,
        frame: false,
        backgroundColor: '#0a0d14',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: true,
            devTools: false,
            webSecurity: true
        }
    });

    // Content protection prevents external screen capture / OBS / Remote desktop mirrors
    mainWindow.setContentProtection(true);

    // Disable opening any new browser windows / popups
    mainWindow.webContents.setWindowOpenHandler(() => {
        return { action: 'deny' };
    });

    // Trap DevTools opening
    mainWindow.webContents.on('devtools-opened', () => {
        mainWindow.webContents.closeDevTools();
    });

    // Keyboard lockdown: filter out all system escape hotkeys
    mainWindow.webContents.on('before-input-event', (event, input) => {
        const key = input.key.toLowerCase();

        // Invigilator Exit Key: Ctrl + Shift + Q
        if (input.control && input.shift && key === 'q') {
            event.preventDefault();
            promptTeacherExit();
            return;
        }

        // Block Developer Tools (F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C)
        if (key === 'f12' || (input.control && input.shift && ['i', 'j', 'c'].includes(key))) {
            event.preventDefault();
            return;
        }

        // Block Refresh / Source View (F5, Ctrl+R, Ctrl+Shift+R, Ctrl+U)
        if (key === 'f5' || (input.control && ['r', 'u'].includes(key))) {
            event.preventDefault();
            return;
        }

        // Block Window / Tab Creation & Closure (Ctrl+N, Ctrl+T, Ctrl+W, Ctrl+Q)
        if (input.control && ['n', 't', 'w', 'q', 'o', 's', 'p'].includes(key)) {
            event.preventDefault();
            return;
        }

        // Block Fullscreen Toggle (F11) and Alt+F4
        if (key === 'f11' || (input.alt && key === 'f4')) {
            event.preventDefault();
            return;
        }

        // Block Alt+Tab and Meta / Windows Key
        if (input.meta || (input.alt && key === 'tab')) {
            event.preventDefault();
            return;
        }

        // Block PrintScreen
        if (key === 'printscreen') {
            event.preventDefault();
            return;
        }
    });

    // Aggressively recapture focus if student tries to Alt+Tab or mouse out
    mainWindow.on('blur', () => {
        setTimeout(() => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.focus();
            }
        }, 100);
    });

    // Load Exam Platform
    loadExamUrl(serverUrl);
}

function loadExamUrl(url) {
    mainWindow.loadURL(url).catch((err) => {
        console.error('Failed to load server URL:', err);
        // Show fallback offline / server IP input screen
        const fallbackHTML = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>DL Exam Lockdown - Server Connection</title>
                <style>
                    body {
                        background: #0f172a;
                        color: #f8fafc;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: #1e293b;
                        padding: 40px;
                        border-radius: 16px;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                        width: 480px;
                        text-align: center;
                        border: 1px solid #334155;
                    }
                    h2 { margin-top: 0; color: #f43f5e; font-size: 1.5rem; }
                    p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
                    input {
                        width: 100%;
                        padding: 12px 16px;
                        border-radius: 8px;
                        border: 1px solid #475569;
                        background: #0f172a;
                        color: #fff;
                        font-size: 1rem;
                        box-sizing: border-box;
                        margin: 20px 0;
                    }
                    button {
                        background: #e11d48;
                        color: #fff;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 1rem;
                        font-weight: 600;
                        cursor: pointer;
                        width: 100%;
                    }
                    button:hover { background: #be123c; }
                    .tip { font-size: 0.8rem; color: #64748b; margin-top: 16px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>DGX Spark Server Unreachable</h2>
                    <p>Unable to connect to exam server at:<br><code>${url}</code></p>
                    <p>Verify that your workstation is connected to the exam LAN or enter the DGX Spark IP below:</p>
                    <input type="text" id="targetUrl" value="${url}" placeholder="http://192.168.10.252:8088">
                    <button onclick="reconnect()">Connect to Examination Server</button>
                    <div class="tip">Press Ctrl+Shift+Q for Invigilator Exit</div>
                </div>
                <script>
                    function reconnect() {
                        const target = document.getElementById('targetUrl').value.trim();
                        if (target) window.location.href = target;
                    }
                </script>
            </body>
            </html>
        `;
        mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(fallbackHTML)}`);
    });
}

function promptTeacherExit() {
    dialog.showMessageBox(mainWindow, {
        type: 'question',
        buttons: ['Cancel', 'Confirm Exit'],
        defaultId: 0,
        title: 'Invigilator Lockdown Override',
        message: 'Enter Teacher Invigilator Key to close the exam browser:',
        detail: 'Closing this application will terminate the proctored session.',
    }).then(res => {
        if (res.response === 1) {
            // Invigilator confirmed exit
            app.isQuitting = true;
            app.quit();
        }
    });
}

// IPC handler for web app to request exit
ipcMain.handle('request-exit-exam', (event, key) => {
    if (key === TEACHER_EXIT_PIN) {
        app.isQuitting = true;
        app.quit();
        return true;
    }
    return false;
});

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
