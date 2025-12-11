# Nemotron Nano 8B (Local)

NVIDIA's Llama-3.1-Nemotron-Nano-8B-v1 running locally via Ollama.

## About

A reasoning model fine-tuned by NVIDIA for:
- **Tool calling / function calling**
- **RAG (Retrieval Augmented Generation)**
- **Math & code reasoning**
- **General chat**

Based on Llama 3.1 8B Instruct. Supports 128K context length.

## Install Ollama (macOS / Linux / Windows)

### macOS (Apple Silicon or Intel)

```bash
# Option A (recommended): Homebrew
brew install ollama

# Option B: Official installer
curl -fsSL https://ollama.com/install.sh | sh

# Verify and quick test
ollama --version
ollama run llama3.2:3b "hi"
```

Notes:
- Homebrew is for macOS/Linux only. For Windows, see the Windows section below.
- Apple Silicon (M‑series) accelerates with Metal automatically.
- If you prefer a foreground server: `ollama serve` (Ctrl+C to stop).

### Linux (Ubuntu/Debian/Fedora/Arch)

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Start/enable service (systemd distros)
sudo systemctl enable --now ollama

# Verify
ollama --version
ollama list
```

GPU (optional):
- NVIDIA: install recent NVIDIA driver + CUDA; verify with `nvidia-smi`.
- If GPU isn’t available, Ollama falls back to CPU.

### Windows 11/10

```powershell
# PowerShell (run as Administrator; requires winget)
winget install Ollama.Ollama
# If winget is unavailable, download the installer from: https://ollama.com

# New terminal:
ollama --version
ollama run llama3.2:3b "hi"
```

Notes:
- Allow Ollama (port 11434) through Windows Firewall on first run.
- Alternative: WSL2 → install Ubuntu, then follow Linux steps inside WSL.

## Add Models to Ollama

You can either pull from the Ollama library or use local GGUF files.

### Option A — Pull from library (1‑line)

```bash
ollama pull llama3.2:3b
ollama run llama3.2:3b "hello"
```

### Option B — Use local GGUF (Nemotron examples below)

See “Download” and “Additional Models (Optional)” sections for GGUF URLs and `Modelfile` examples to register:

```bash
# Example flow
curl -L -o model.gguf "https://huggingface.co/.../model-Q4_K_M.gguf"
cat > Modelfile << 'EOF'
FROM ./model.gguf
PARAMETER temperature 0.6
PARAMETER top_p 0.95
EOF
ollama create mymodel -f Modelfile
ollama run mymodel "hi"
```

## Usage

ollama run nemotron

If you’ve registered additional models:

- nemotron9b: `ollama run nemotron9b`
- nemotron12b: `ollama run nemotron12b`

### Reasoning Mode

Toggle reasoning with the system prompt "detailed thinking on" or "detailed thinking off".

### Recommended Settings

- **Reasoning ON**: temperature 0.6, top_p 0.95
- **Reasoning OFF**: greedy decoding (temperature 0)

## Download

Download the GGUF weights locally:
(Already downloaded)
```bash
curl -L -o nemotron-nano.gguf "https://huggingface.co/bartowski/nvidia_Llama-3.1-Nemotron-Nano-8B-v1-GGUF/resolve/main/nvidia_Llama-3.1-Nemotron-Nano-8B-v1-Q4_K_M.gguf"
```

## Files

- Modelfile - Ollama model config
- nemotron-nano.gguf - Model weights (Q4_K_M quantization, ~4.7GB)
- nemotron-9b-v2.gguf - Optional upgrade (Q4_K_M, ~6.1GB)
- nemotron-12b-v2.gguf - Optional upgrade (Q4_K_M, ~7.1GB)

## Use with LLM Council (Local)

Run Karpathy’s LLM Council fully offline using your local Ollama models.

1) Verify Ollama and models

```bash
ollama list
```

2) Install Council deps

```bash
cd Council/llm-council
uv sync
cd frontend && npm install && cd ..
```

3) Configure local mode (.env in Council/llm-council)

```bash
cat > .env <<'EOF'
COUNCIL_PROVIDER=local
LOCAL_MODELS=nemotron,nemotron9b,nemotron12b
CHAIRMAN_LOCAL_MODEL=nemotron12b
COUNCIL_MAX_PARALLEL_LOCAL=2
COUNCIL_MEM_RESERVE_GB=6
# OLLAMA_BASE_URL=http://127.0.0.1:11434
EOF
```

4) Start servers

- Option A:

```bash
./start.sh
```

- Option B:

```bash
uv run python -m backend.main
# in a new terminal:
cd frontend && npm run dev
```

Open http://localhost:5173.

5) Smoke test via CLI (optional)

```bash
bash scripts/council.sh -m "Say hi in five words"
bash scripts/council.sh --stream -m "One fun fact about space."
```

Notes
- Ensure `LOCAL_MODELS` names match `ollama list` (omit tags like `:latest`).
- If the machine is tight on RAM, lower `LOCAL_MODELS` count or set `COUNCIL_MAX_PARALLEL_LOCAL=1–2`.
- `COUNCIL_MEM_RESERVE_GB` keeps headroom for the OS/apps; increase if needed.

### RAM Sizing & Safeguards (Council Local Mode)
- Effective model budget ≈ `max(60% of RAM, RAM − COUNCIL_MEM_RESERVE_GB)`.
- Recommended on 48 GiB Macs:
  - Light multitasking: `COUNCIL_MEM_RESERVE_GB=8`
  - Heavy multitasking: `COUNCIL_MEM_RESERVE_GB=10–12`
- To reduce pressure: lower `COUNCIL_MAX_PARALLEL_LOCAL` or remove a model from `LOCAL_MODELS`.

## Additional Models (Optional)

### NVIDIA Nemotron Nano 9B v2

Download:

```bash
curl -L -o nemotron-9b-v2.gguf "https://huggingface.co/bartowski/nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF/resolve/main/nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M.gguf"
```

Register with Ollama:

```bash
cat > Modelfile-9b << 'EOF'
FROM ./nemotron-9b-v2.gguf
TEMPLATE """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>
{{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
PARAMETER temperature 0.6
PARAMETER top_p 0.95
EOF

ollama create nemotron9b -f Modelfile-9b
```

Run:

```bash
ollama run nemotron9b "What are you?"
```

---

### NVIDIA Nemotron Nano 12B v2

Download:

```bash
curl -L -o nemotron-12b-v2.gguf "https://huggingface.co/bartowski/nvidia_NVIDIA-Nemotron-Nano-12B-v2-GGUF/resolve/main/nvidia_NVIDIA-Nemotron-Nano-12B-v2-Q4_K_M.gguf"
```

Register with Ollama:

```bash
cat > Modelfile-12b << 'EOF'
FROM ./nemotron-12b-v2.gguf
TEMPLATE """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>
{{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
PARAMETER temperature 0.6
PARAMETER top_p 0.95
EOF

ollama create nemotron12b -f Modelfile-12b
```

Run:

```bash
ollama run nemotron12b "What are you?"
```

## Manage Models & Disk Space

```bash
# See installed models and sizes
ollama list

# Remove a model to free space
ollama rm nemotron9b
```

Notes:
- GGUF files are several GB each; keep an eye on free disk space before downloads.
- If using Council in local mode, ensure `LOCAL_MODELS` only includes models you actually need.

## Troubleshooting

- Error: supplied file was not in GGUF format  
  This usually means the downloaded file was an HTML page, not a .gguf. Make sure you:
  - Use the Hugging Face “resolve/main/... .gguf” URL.
  - Pass -L to curl to follow redirects.
  - Verify file size is several GB (ls -lh). Re-download if it’s only KB/MB.
- zsh: command not found: llama  
  Use `ollama run ...` instead of `llama run`.
- Connection refused to http://127.0.0.1:11434  
  Start Ollama:  
  - macOS/Windows: launch the app or run `ollama serve`  
  - Linux: `sudo systemctl enable --now ollama`
- Port 11434 already in use  
  Stop whatever is bound to 11434, or change Ollama port/host (e.g., `OLLAMA_HOST=127.0.0.1:11435 ollama serve`) and update `OLLAMA_BASE_URL` in `.env`.

## Source

- Official: https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1
- GGUF: https://huggingface.co/bartowski/nvidia_Llama-3.1-Nemotron-Nano-8B-v1-GGUF
- 9B v2: https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-9B-v2
- 12B v2: https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-12B-v2

## License

NVIDIA Open Model License + Llama 3.1 Community License
