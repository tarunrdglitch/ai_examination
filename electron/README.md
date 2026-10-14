# DL Enterprise Proctored Exam Browser (Windows Lockdown Client)

High-security, locked Electron kiosk application designed for 500+ student examination halls connected via local LAN to the **NVIDIA DGX Spark** server.

---

## Security Features
1. **Full Kiosk Lock:**
   - Fullscreen borderless window (`kiosk: true`, `alwaysOnTop: true`).
   - Automatically reclaims window focus immediately if student attempts to minimize or blur.
2. **Keyboard & System Interception:**
   - Blocks `Alt + Tab`, `Alt + F4`, and the Windows / Super key.
   - Blocks Developer Tools (`F12`, `Ctrl + Shift + I`, `Ctrl + Shift + J`, `Ctrl + Shift + C`).
   - Blocks Browser Refresh / Navigations (`F5`, `Ctrl + R`, `Ctrl + Shift + R`, `Ctrl + U`).
   - Blocks Tab/Window Creation (`Ctrl + N`, `Ctrl + T`, `Ctrl + W`).
   - Blocks Screen Captures (`PrintScreen`).
3. **Anti-Capture Protection:**
   - `setContentProtection(true)` blocks third-party screen recorders (OBS, Discord, remote desktop mirrors) from capturing the exam screen.
4. **Teacher / Invigilator Exit:**
   - To safely exit the kiosk after exam submission, the invigilator presses **`Ctrl + Shift + Q`** and confirms the override.

---

## Building the Windows `.exe`

### Prerequisites
- Node.js (v18 or v20+)
- npm

### 1. Install Dependencies
```bash
cd electron
npm install
```

### 2. Test in Development Mode
```bash
# Connect to default DGX Spark LAN IP (http://192.168.10.252:8088)
npm start

# Or specify custom server IP
npm start -- --server=http://192.168.10.252:8088
```

### 3. Build Windows Executable (`.exe`)
From any Windows workstation (or Linux with wine):
```bash
npm run dist:win
```
The output directory `dist/` will contain:
- `DL Proctored Exam Browser 1.0.0.exe` (Portable self-contained executable - ideal for USB flash drive or shared network folder deployment).
- `DL Proctored Exam Browser Setup 1.0.0.exe` (NSIS installer for mass deployment across student labs).

---

## Deployment Across 500 Student PCs
1. Place `DL Proctored Exam Browser 1.0.0.exe` on a shared network drive (e.g. `\\192.168.10.252\exam\`).
2. Run a batch script on student computers at the start of the exam:
   ```cmd
   "\\192.168.10.252\exam\DL Proctored Exam Browser 1.0.0.exe" --server=http://192.168.10.252:8088
   ```
3. The exam launches in full kiosk mode, pointing directly to the DGX Spark offline examination instance.
