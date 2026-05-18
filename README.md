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
- The Ollama model used by the backend: `qwen2.5-coder:1.5b`

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

Install/pull the local Ollama model:

```bash
ollama pull qwen2.5-coder:1.5b
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

## Backend Endpoints

- `POST /execute` - run Python code and return execution output, RCA, semantic matches, and LLM feedback
- `POST /rca` - generate RCA and LLM feedback from a supplied traceback/code payload
- `GET /embeddings` - inspect stored vector records
- `POST /ingest-bugsinpy` - ingest BugsInPy records into the vector store
- `POST /generate-embedding` - generate an embedding for custom text

## Ollama Notes

The LLM feedback module is configured in:

```text
backend/llm/feedback_model.py
```

Current model:

```text
qwen2.5-coder:1.5b
```

To use a different local Ollama model, update `OLLAMA_MODEL` in `backend/llm/feedback_model.py`, then pull that model:

```bash
ollama pull <model-name>
```

Examples:

```bash
ollama pull qwen2.5-coder:7b
ollama pull deepseek-coder:6.7b
ollama pull codellama:7b
```

Larger models usually give better feedback, but need more RAM and take longer to respond.

## Troubleshooting

If the RCA panel says the backend is unavailable:

- Make sure Terminal 2 is running `python main.py` inside the `backend` folder.
- Confirm the backend is reachable at `http://localhost:8000`.
- Check that the frontend is using the same backend URL.

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
│   └── traceback_parser.py      # Traceback and code-context extraction
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
