# Windows packaging

Run the full guarded build from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\build_xiaorong_1_2_0.ps1
```

The wrapper delegates every Python, test, lint, audit, and PyInstaller command to environment `dp`. It first verifies an isolated onedir build, then produces and smoke-tests the single-file `release/小融-1.2.0-win64.exe`. No upload, Git commit, environment installation, signing, UPX compression, or system-level change is performed.
