# WebIDE with Semantic Log Debugger & Root Cause Analysis

A web-based Python IDE with runtime execution, semantic traceback debugging, root cause analysis, vector-based historical bug matching, and local LLM feedback for developers.

The project has three moving parts:

- Frontend IDE: React/Vite app served on `http://localhost:3000`
- Backend API: FastAPI server on `http://localhost:8000`
- Local LLM: Ollama server on `http://localhost:11434`

## Prerequisites

Install these before running the project:

- Node.js 18+ and npm
- Python 3.10+ recommended
- Ollama
- The Ollama models used by the project: `qwen2.5-coder:1.5b`, `llama3.2:1b`, `phi4-mini:latest`
- Sarvam API key for translating RCA output into Indian languages

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

Install/pull the local Ollama models:

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull llama3.2:1b
ollama pull phi4-mini:latest
```

## Running the Project

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

1. Open the IDE at `http://localhost:3000`.
2. Select or write Python code in the editor.
3. Click `EXECUTE RUNTIME`.
4. If the code fails, the RCA panel appears.
5. The backend parses the traceback, retrieves similar historical bugs, runs root cause analysis, and asks the local Ollama model for developer feedback.
6. The panel shows the symptom, root cause, recommended fix, evidence, developer fix plan, prevention checks, and debugging questions.
7. After the LLM output finishes, use `Translate Generated RCA`, select an Indian language, and click `CONVERT`.
8. You can change the AI model used for explanations at any time via the **Settings** panel in the IDE.

## Log Debugger

The IDE also supports log-based debugging.

1. Select the local Ollama model from the model dropdown.
2. Click `LOG DEBUGGER` in the left sidebar.
3. Upload a `.log`, `.txt`, `.out`, `.err`, `.trace`, `.csv`, or `.xslx` file.
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

The LLM feedback module supports dynamically switching models via the IDE **Settings** panel.

The pre-configured models are optimized for low-end machines:

- `qwen2.5-coder:1.5b` (Extremely lightweight, default)
- `llama3.2:1b` (Ultra-fast general reasoning)
- `phi4-mini:latest` (Advanced instructions and code reasoning)

To use these models, you must pull them to your local Ollama instance:

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull llama3.2:1b
ollama pull phi4-mini:latest
```

If you wish to add different local Ollama models (e.g., `qwen2.5-coder:7b` or `deepseek-coder:6.7b`), you can update the `LOCAL_MODELS` array in `src/App.jsx` and pull the model in Ollama.

Larger models usually give better feedback, but need more RAM and take longer to respond.

## Sarvam Translation

The RCA panel can translate the generated English explanation into Indian languages through Sarvam Translate.

Add your Sarvam API key in one of these ways:

```text
backend/sarvam_translate.py
```

Set:

```python
SARVAM_API_KEY = "your_key_here"
```

Or set an environment variable before starting the backend:

```bash
SARVAM_API_KEY=your_key_here
```

Important: restart the backend after adding or changing the key. The running FastAPI process only reads the key when it starts.

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

If translation says the Sarvam API key is missing:

- Confirm the key is set in `backend/sarvam_translate.py` or in the `SARVAM_API_KEY` environment variable.
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

```
backend/
├── main.py                      # FastAPI app and API routes
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

src/
├── App.jsx                      # React IDE shell
├── components/
│   └── RCAPanel.jsx             # RCA/feedback UI panel
└── services/
    └── api.ts                   # Frontend API client/types

index.html                       # Inline IDE demo served by Vite
package.json                     # Frontend dependencies/scripts
vite.config.js                   # Vite server config
```

## Technologies Used

- React
- Vite
- Monaco Editor
- FastAPI
- Python subprocess execution
- Sentence Transformers / deterministic embedding fallback
- Local vector search
- Ollama local LLM feedback
- BugsInPy-style historical bug retrieval
