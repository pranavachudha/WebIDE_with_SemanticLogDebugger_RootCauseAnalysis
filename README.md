# PyGlide — Python Web IDE with Semantic Log Debugging & Root Cause Analysis

**PyGlide** is a web-based Python IDE with code execution, an interactive console, semantic log debugging, root cause analysis (RCA), historical bug matching, and local AI feedback through Ollama.

It includes a multi-file workspace, resizable panels, traceback visualization, and optional Indian-language RCA translation through Sarvam. Code execution and structured debugging currently support **Python**.

PyGlide uses three local services:

- Frontend IDE: React/Vite app served on `http://localhost:3000`
- Backend API: FastAPI server on `http://localhost:8000`
- Local LLM: Ollama server on `http://localhost:11434`

## Prerequisites

Install these before running the project:

- Node.js 18+ and npm
- Python 3.10+ recommended (3.11 or newer works)
- Ollama
- The Ollama models used by the project: `qwen2.5-coder:1.5b`, `llama3.2:1b`, `phi4-mini:latest`
- Sarvam API key (optional, required only for translating RCA output into Indian languages)

Internet access is needed for CDN assets and optional Sarvam translation; Ollama feedback runs locally.

## First-Time Setup

Clone the repo and enter the project folder:

```bash
git clone git@github.com:pranavachudha/WebIDE_with_SemanticLogDebugger_RootCauseAnalysis.git
cd WebIDE_with_SemanticLogDebugger_RootCauseAnalysis
```

Install frontend dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
cd ..
```

For Excel logs, also run `pip install pandas openpyxl` in the same environment; `.xls` files additionally require `xlrd`.

### Windows setup (recommended if pip fails with long path or build errors)

Long project folder paths can break the PyTorch install on Windows, and pinned older versions may try to compile from source. To avoid both, create the virtual environment at a short path:

```powershell
python -m venv E:\venvs\logdbg
E:\venvs\logdbg\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
E:\venvs\logdbg\Scripts\python.exe -m pip install fastapi uvicorn pydantic sentence-transformers requests python-multipart scikit-learn httpx --only-binary=:all:
```

Notes:

- Replace `E:\venvs\logdbg` with any short folder you like, for example `C:\venvs\logdbg`.
- The first command installs the CPU build of PyTorch, which is smaller and works without an NVIDIA GPU.
- `--only-binary=:all:` prevents pip from compiling packages, so Microsoft C++ Build Tools are not needed.
- Do not install into a shared conda environment, since the pinned versions can downgrade packages used by other projects.

Install/pull the local Ollama models:

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull llama3.2:1b
ollama pull phi4-mini:latest
```

## Running PyGlide

Start the app using three terminals.

### Terminal 1: Start Ollama

```bash
ollama serve
```

If Ollama is already running in the background, this may say the port is already in use. That is fine as long as `http://localhost:11434` is active.

### Terminal 2: Start the Backend

From the project root:

```bash
cd backend
python main.py
```

If you used the Windows setup above, start the backend with the venv Python instead:

```powershell
cd backend
E:\venvs\logdbg\Scripts\python.exe main.py
```

The backend should start on:

```text
http://localhost:8000
```

### Terminal 3: Start the Frontend

From the project root:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

## How to Use

1. Open PyGlide at `http://localhost:3000`.
2. Select or write Python code in the editor.
3. Click `EXECUTE RUNTIME`.
4. If the code fails, the RCA panel appears.
5. The backend parses the traceback, retrieves similar historical bugs, runs root cause analysis, and asks the local Ollama model for developer feedback.
6. The panel shows the symptom, root cause, recommended fix, evidence, developer fix plan, prevention checks, and debugging questions.
7. After the LLM output finishes, use `Translate Generated RCA`, select an Indian language, and click `CONVERT`.
8. Change the local AI model using the model dropdown in the top toolbar. Pull the selected model in Ollama before using it.

### Workspace panels

- Toggle **Explorer**, **Console**, and **Analysis** from the toolbar. Hiding panels preserves their contents; **×** clears Analysis, while closing Console keeps its session.
- RCA survives file switches and edits until Analysis is closed or a file runs again.
- Drag panel edges to resize, use the console chevron to maximize/restore, or select **Reset panel layout**. Sizes and visibility are saved locally.
- Shortcuts: `Ctrl+B` Explorer, `Ctrl+J` Console, `Ctrl+Alt+A` Analysis. Use Command instead of Ctrl on macOS.

## Log Debugger

PyGlide also supports log-based debugging without running the original source file.

1. Select the local Ollama model from the model dropdown.
2. Click `LOG DEBUGGER` in the left sidebar.
3. Upload a `.log`, `.txt`, `.out`, `.err`, `.trace`, `.csv`, `.xlsx`, or `.xls` file. Excel uploads require the optional readers described in setup.
4. The backend extracts the strongest traceback/error signal, runs semantic retrieval and RCA, then streams feedback from the selected Ollama model.
5. The same RCA panel shows the log excerpt, root cause, fix plan, evidence, prevention checks, debugging questions, and translation controls.

## Backend Endpoints

- `POST /execute` - run Python code and return execution output, RCA, semantic matches, and LLM feedback
- `POST /rca` - generate RCA and LLM feedback from a supplied traceback/code payload
- `POST /log-debug` - extract error context from uploaded logs and return RCA-ready details
- `POST /stream-feedback` - stream local Ollama feedback for code errors or log errors
- `GET /embeddings` - inspect stored vector records
- `POST /ingest-bugsinpy` - ingest BugsInPy records into the vector store
- `POST /generate-embedding` - generate an embedding for custom text
- `POST /translate-feedback` - translate generated RCA feedback with Sarvam Translate

## Ollama Notes

The LLM feedback module supports switching models through PyGlide's top toolbar dropdown.

The configured local model options are:

- `qwen2.5-coder:1.5b` (default coding model)
- `llama3.2:1b` (general reasoning option)
- `phi4-mini:latest` (additional reasoning option)

Pull the selected model with `ollama pull <model-name>` as shown in setup.

To add a model to the active IDE, update `LOCAL_MODELS` in `index.html` and pull it in Ollama.

Response time and feedback quality depend on the selected model, available memory, hardware, and error context.

## Sarvam Translation

PyGlide's RCA panel can translate the generated English explanation into Indian languages through Sarvam Translate.

Set `SARVAM_API_KEY` in the terminal used to start the backend. For PowerShell:

```powershell
$env:SARVAM_API_KEY = "your_key_here"
python main.py
```

Run from `backend/` with your environment's Python. In Bash, use `export SARVAM_API_KEY="your_key_here"`. The variable overrides the fallback in `backend/sarvam_translate.py`; restart the backend after changing it. Keep real keys out of committed files.

The translation feature uses:

- Backend endpoint: `POST /translate-feedback`
- Frontend control: `Translate Generated RCA` in the RCA panel
- Default source language: `en-IN`
- Target languages include Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu, Urdu, and more.

## Troubleshooting

If the RCA panel says the backend is unavailable:

- Make sure Terminal 2 is running `python main.py` inside the `backend` folder.
- Confirm the backend is reachable at `http://localhost:8000`.
- Check that the frontend is using the same backend URL.

If you see `ModuleNotFoundError: No module named 'xyz'`:

- Install the missing package with the same Python you use to run the backend, for example:

```powershell
E:\venvs\logdbg\Scripts\python.exe -m pip install xyz
```

If pip fails with a long path error or asks for Microsoft Visual C++ Build Tools:

- Follow the **Windows setup** section above. It uses a short venv path and prebuilt packages only.

If translation says the Sarvam API key is missing or returns `invalid_api_key_error`:

- Set a valid Sarvam key in the backend terminal's `SARVAM_API_KEY` environment variable. A stale environment variable overrides the source fallback.
- Stop and restart the backend after setting the key.
- Refresh the frontend with `Ctrl + F5`.

If LLM feedback is weak or falls back:

- Make sure Ollama is running.
- Make sure the model is pulled:

```bash
ollama list
```

- Test Ollama directly:

```bash
ollama run qwen2.5-coder:1.5b
```

If frontend does not open on the expected port:

- This project's Vite config uses port `3000`.
- If the port is occupied, stop the other process or update `vite.config.js`.

## Project Structure

```text
backend/
├── main.py                      # FastAPI app and API routes
├── sarvam_translate.py          # Sarvam translation requests and key lookup
├── llm/
│   └── feedback_model.py        # Ollama-powered developer feedback module
├── rca/
│   └── engine.py                # Root cause analysis synthesis
├── parser/
│   ├── traceback_parser.py      # Traceback and code-context extraction
│   └── log_parser.py            # Uploaded log error extraction
├── runtime/
│   └── executor.py              # Python subprocess execution
├── vector_db/
│   └── chroma_store.py          # Local vector store and semantic search
└── ingestion/
    └── bugsinpy.py              # BugsInPy ingestion utilities

index.html                       # Active PyGlide interface and inline React application
pyworker.js                      # Browser Python execution and REPL through Pyodide
sw.js                            # Service worker for interactive Python input

src/
├── workspace.css                # Active PyGlide panel layout and responsive styles
├── App.jsx                      # Separate React source implementation
├── components/
│   └── RCAPanel.jsx             # RCA/feedback UI panel
└── services/
    └── api.ts                   # Frontend API client/types

package.json                     # Frontend dependencies/scripts
vite.config.js                   # Vite server config
```

## Technologies Used

- React
- Vite
- Monaco Editor for Python editing
- Pyodide and Web Workers for browser-based Python execution
- Xterm.js for the console and REPL
- FastAPI
- Python subprocess execution through the backend API
- Trace graphs and PageRank for candidate root-cause frame selection
- Sentence Transformers / deterministic embedding fallback
- Local vector search
- Ollama local LLM feedback
- BugsInPy-style historical bug retrieval
- Sarvam Translate for optional Indian-language RCA translation
- Browser local storage for workspace files and panel preferences
