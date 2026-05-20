from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from embeddings.generator import generate_embedding
from ingestion.bugsinpy import ingest_bugsinpy_dataset, ingest_mock_data
from llm.feedback_model import generate_developer_feedback
from parser.traceback_parser import build_embedding_document, extract_code_context, parse_traceback
from runtime.executor import execute_code, stop_execution
from rca.engine import analyze_error
from vector_db.chroma_store import add_bug_to_db, get_similar_bugs, traceback_collection

app = FastAPI(title="Semantic AI Debugger API")


@app.on_event("startup")
async def seed_curated_bug_patterns():
    ingest_mock_data()

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExecuteRequest(BaseModel):
    filename: str = "main.py"
    code: str

class SemanticSearchRequest(BaseModel):
    exception_type: str = ""
    traceback: str = ""
    code: str = ""
    top_k: int = 5

class EmbeddingRequest(BaseModel):
    text: str

class RCARequest(BaseModel):
    exception_type: str
    message: str = ""
    traceback: str = ""
    code: str = ""

class IngestRequest(BaseModel):
    dataset_path: str = "dataset/BugsInPy"
    limit: int | None = 150
    run_tests: bool = False

class FeedbackStreamRequest(BaseModel):
    error: dict
    rca: dict | None = None
    similar_bugs: list | None = None
    source_code: str = ""
    model: str | None = None


@app.post("/execute")
async def execute(request: ExecuteRequest):
    result = execute_code(request.code, request.filename)

    if not result.get("success", False):
        exception_type = result["error"].get("type")
        message = result["error"].get("message")
        traceback_str = result["error"].get("traceback")
        code_context = result["error"].get("code_context", {})

        semantic_document = build_embedding_document(result["error"], code_context, request.code)
        query_embedding = generate_embedding(semantic_document)
        similar_bugs = get_similar_bugs(exception_type, traceback_str, semantic_document, top_k=5)

        rca_summary = analyze_error(exception_type, message, traceback_str, similar_bugs)

        return {
            "success": False,
            "filename": request.filename,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "traceback": result.get("traceback", ""),
            "error": result["error"],
            "semantic_matches": similar_bugs,
            "query_embedding": query_embedding,
            "root_cause_analysis": rca_summary["summary"],
            "suggested_fix": rca_summary["suggested_fix"],
            "llm_feedback": None,
            "similarity_scores": [match["score"] for match in similar_bugs],
            "rca": rca_summary,
            "execution_time": result.get("execution_time", ""),
        }

    return {
        "success": True,
        "filename": request.filename,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "traceback": result.get("traceback", ""),
        "error": None,
        "execution_time": result.get("execution_time", ""),
    }


@app.post("/stream-feedback")
async def stream_feedback(request: FeedbackStreamRequest):
    from fastapi.responses import StreamingResponse
    from llm.feedback_model import stream_developer_feedback_generator

    similar_bugs = request.similar_bugs
    if similar_bugs is None:
        try:
            from services.search_service import get_similar_bugs
            from services.code_parser import parse_traceback
            tb = request.error.get("traceback", "")
            exc_type = request.error.get("type", "")
            exc_msg = request.error.get("message", "")
            parsed = parse_traceback(tb)
            line_number = parsed.get("line_number", -1)
            code_context = ""
            if line_number != -1 and request.source_code:
                code_lines = request.source_code.split("\n")
                if 0 < line_number <= len(code_lines):
                    code_context = code_lines[line_number - 1].strip()
            semantic_document = f"{exc_type} {exc_msg} {parsed.get('failing_function', '')} {code_context}"
            similar_bugs = get_similar_bugs(exc_type, tb, semantic_document)
        except Exception:
            similar_bugs = []

    return StreamingResponse(
        stream_developer_feedback_generator(
            error=request.error,
            rca=request.rca,
            similar_bugs=similar_bugs,
            source_code=request.source_code,
            model_name=request.model,
        ),
        media_type="text/event-stream",
    )

@app.post("/stop")
async def stop():
    stopped = stop_execution()
    return {"success": stopped, "message": "Execution was stopped." if stopped else "No running execution to stop."}

@app.get("/similar-bugs")
async def similar_bugs(exception_type: str = "", query: str = ""):
    bugs = get_similar_bugs(exception_type, query, "")
    return {"bugs": bugs}

@app.post("/semantic-search")
async def semantic_search(request: SemanticSearchRequest):
    bugs = get_similar_bugs(request.exception_type, request.traceback, request.code, request.top_k)
    return {"semantic_matches": bugs, "similarity_scores": [bug["score"] for bug in bugs]}

@app.post("/generate-embedding")
async def embedding(request: EmbeddingRequest):
    vector = generate_embedding(request.text)
    return {"dimension": len(vector), "embedding": vector}

@app.get("/embeddings")
async def embeddings():
    try:
        data = traceback_collection.get_all()
        return {
            "records": [
                {
                    "id": id_,
                    "embedding": embedding,
                    "metadata": metadata,
                }
                for id_, embedding, metadata in zip(data.get("ids", []), data.get("embeddings", []), data.get("metadatas", []))
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/rca")
async def rca(request: RCARequest):
    parsed = parse_traceback(request.traceback)
    line_number = parsed.get("line_number", -1)
    code_context = extract_code_context(request.code, line_number)
    semantic_document = build_embedding_document(
        {
            "type": request.exception_type,
            "message": request.message,
            "traceback": request.traceback,
            "failing_function": parsed.get("failing_function", ""),
        },
        code_context,
        request.code,
    )
    matches = get_similar_bugs(request.exception_type, request.traceback, semantic_document)
    rca_result = analyze_error(request.exception_type, request.message, request.traceback, matches)
    error_details = {
        "type": request.exception_type,
        "message": request.message,
        "traceback": request.traceback,
        "line_number": line_number,
        "failing_function": parsed.get("failing_function", ""),
        "code_context": code_context,
        "call_stack": parsed.get("call_stack", []),
    }
    return {
        "rca": rca_result,
        "llm_feedback": None,
        "semantic_matches": matches,
        "error_details": error_details,
    }


@app.post("/ingest-bugsinpy")
async def ingest_bugsinpy(request: IngestRequest):
    try:
        summary = ingest_bugsinpy_dataset(request.dataset_path, limit=request.limit, run_tests=request.run_tests)
        return summary
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
