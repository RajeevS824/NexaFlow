# Running this project locally (Windows)

This project used to run as 3 services inside one Kaggle notebook,
tunneled to the internet via ngrok, with the frontend running locally and
talking to that tunnel. It now runs entirely on your machine — no
Kaggle, no ngrok, no notebook.

The backend is still 3 separate FastAPI services (this didn't change,
it's the same architecture the app was already built around):

| Service      | Port | What it does                                   |
|--------------|------|-------------------------------------------------|
| audio_service| 8020 | Whisper transcription                          |
| video_service| 8021 | Qwen3-VL frame analysis                        |
| orchestrator | 8022 | Coordinates both + LLM report — **frontend talks to this one** |

`run_backend.py` starts all three for you with one command.

---

## 0. Software you need to install first

1. **Python 3.10 or 3.11** (64-bit) — https://www.python.org/downloads/
   During install, check **"Add python.exe to PATH"**.
   Verify: `python --version`

2. **Node.js 20 LTS** (for the React frontend) — https://nodejs.org/
   Verify: `node --version` and `npm --version`

3. **Git** (only needed if you're cloning from GitHub rather than
   unzipping) — https://git-scm.com/download/win

4. **FFmpeg** (audio/video extraction, silence detection):
   ```powershell
   winget install Gyan.FFmpeg
   ```
   Close and reopen your terminal afterward so PATH updates take effect.
   Verify: `ffmpeg -version` and `ffprobe -version`

5. **Redis** (job queue used by the video service). Windows doesn't
   ship Redis natively, so pick one:
   - **Easiest — Docker Desktop**: https://www.docker.com/products/docker-desktop/
     then: `docker run -d --name redis -p 6379:6379 redis`
   - **WSL2**: `wsl --install`, then inside the WSL Ubuntu shell:
     `sudo apt-get update && sudo apt-get install -y redis-server && sudo service redis-server start`
   - **Native Windows build**: https://github.com/tporadowski/redis/releases
     (download, run `redis-server.exe`)

   `run_backend.py` checks for Redis on startup and tells you exactly
   which of the above it's missing if none are found.

6. **GPU (optional but recommended)**: if you have an NVIDIA GPU, install
   the matching CUDA-enabled PyTorch build (see step 3 below) so the
   video service (Qwen3-VL) runs on GPU instead of CPU. Not required —
   everything also works on CPU, just slower.

7. **ODBC Driver 17 for SQL Server** — **only if** you plan to turn on
   the optional database persistence layer (`database.enabled: true` in
   `config.yaml`). Skip this if you're fine with the default in-memory
   job store.
   Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

---

## 1. Get the code

If you already unzipped the project, `cd` into the folder that contains
`AudioVideoPipeline/`, `Frontend/`, and `run_backend.py` (this is
`REPO_ROOT` below) and skip to step 2.

If cloning from GitHub instead:
```powershell
git clone <your-repo-url> suppi
cd suppi
```

---

## 2. Create a virtual environment

From the repo root (PowerShell):
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```
(If PowerShell blocks script execution: run PowerShell as Administrator
once and execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`,
then retry. Or use `venv\Scripts\activate.bat` from `cmd.exe` instead.)

You should now see `(venv)` at the start of your prompt.

---

## 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs everything for all 3 services (audio, video, orchestrator)
in one go — it references the three per-service requirement files under
`AudioVideoPipeline/*/requirements_*.txt`.

**If you have an NVIDIA GPU** and want CUDA acceleration, reinstall torch
with the CUDA build that matches your driver *after* the step above
(pick your CUDA version at https://pytorch.org/get-started/locally/), e.g.:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 4. Configure environment variables

```powershell
copy .env.example .env
notepad .env
```
At minimum, set:
```
OPENROUTER_API_KEY=sk-or-...your key from https://openrouter.ai/keys...
```
Everything else in `.env.example` is optional — read the comments in the
file. Leave `EMAIL_SENDER_PASSWORD` and the `DB_*` variables blank unless
you're using those features.

`.env` is already gitignored — it will never be committed.

---

## 5. Start the backend

Still inside the activated virtual environment, from the repo root:
```powershell
python run_backend.py
```

First run downloads several GB of ML models (Whisper large-v3, a
sentence-embedding model, Silero VAD, Qwen3-VL) — this can take 10-20+
minutes depending on your connection. Subsequent runs reuse the local
`models/` folder and start in seconds.

When it's ready you'll see:
```
BACKEND IS LIVE AT: http://localhost:8020
```
Leave this terminal window open — closing it stops all 3 services.
Logs for each service are written next to `run_backend.py`
(`audio_service.log`, `video_service.log`, `orchestrator.log`).

---

## 6. Start the frontend

In a **new** terminal window (leave the backend running in the first
one):
```powershell
cd Frontend\project_final
copy .env.example .env
npm install
npm run dev
```
Vite will print a local URL, typically `http://localhost:5173`. Open
that in your browser — the app is now fully local, talking to your
backend at `http://localhost:8020` through Vite's dev proxy.

---

## 7. Stopping everything

- Frontend terminal: `Ctrl+C`
- Backend terminal: `Ctrl+C` (this stops the audio, video, and
  orchestrator processes together)
- If you started Redis via Docker: `docker stop redis`

---

## Troubleshooting

- **`ffmpeg`/`ffprobe not found`** — you installed it but didn't reopen
  your terminal, or it's not on PATH. Open a new terminal and re-check
  `ffmpeg -version`.
- **Redis connection errors** — confirm something is actually listening
  on port 6379: `Test-NetConnection localhost -Port 6379` (PowerShell).
- **`/health` never turns healthy for audio/video service** — check
  `audio_service.log` / `video_service.log` next to `run_backend.py` for
  the actual stack trace.
- **OpenRouter calls fail with 401** — `OPENROUTER_API_KEY` isn't set in
  `.env`, or the key is invalid/revoked.
- **Frontend can't reach the backend** — confirm `run_backend.py` printed
  `BACKEND IS LIVE AT: http://localhost:8000`, and that
  `Frontend/project_final/.env` has `VITE_BACKEND_URL=http://localhost:8000`
  (this is already the default even without a `.env` file). Restart
  `npm run dev` after changing `.env` — Vite only reads it at startup.
- **GPU not being used** — verify `python -c "import torch; print(torch.cuda.is_available())"`
  prints `True` inside the activated venv; if `False`, reinstall torch
  with the correct CUDA index URL (step 3).
- **Slow on CPU-only machines** — this is expected; Whisper large-v3 and
  Qwen3-VL are both large models. Consider a smaller Whisper size if
  needed by editing `models.whisper.name` in
  `AudioVideoPipeline/Configuration/config.yaml`.
