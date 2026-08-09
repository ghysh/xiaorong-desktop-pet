# Windows packaging

Run the full guarded build from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\build_release.ps1
```

The wrapper locates Conda and delegates every Python, test, lint, and PyInstaller command to environment `dp`. The primary artifact is the onedir portable ZIP. No upload, Git operation, environment installation, signing, UPX compression, or system-level change is performed.
