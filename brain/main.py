import threading
import uvicorn
import os
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from .model_router import ModelRouter
from .context_engine import ContextEngine
from .project_context_loader import ProjectContextLoader

load_dotenv()

# ======================================================
# App
# ======================================================
app = FastAPI(title="JARVIS Brain")

UI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui"
)
if os.path.exists(UI_DIR):
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")

# ======================================================
# Core Components
# ======================================================
context_engine = ContextEngine()
router = ModelRouter(context_engine)

# ======================================================
# Modes
# ======================================================
UNDERSTAND_KEYWORDS = [
    "understand", "explain", "summarize",
    "overview", "what is in", "how does",
    "walk me through"
]

CODE_KEYWORDS = [
    "add", "create", "implement", "write",
    "give me code", "new", "function",
    "object", "component", "feature"
]

def decide_mode(text: str) -> str:
    text = text.lower()
    if any(k in text for k in UNDERSTAND_KEYWORDS):
        return "UNDERSTAND"
    return "CODE"

# ======================================================
# INTENT EXTRACTION (SYSTEM-SIDE)
# ======================================================
def extract_intent(message: str) -> str:
    text = message.lower()

    if "square" in text and "shape" in text:
        return "square_grid_layout"

    if "cone" in text and "shape" in text:
        return "cone_layout"

    if "new project" in text:
        return "new_project"

    return "generic_code"

# ======================================================
# SEMANTIC VALIDATOR (CRITICAL FIX)
# ======================================================
def semantic_validate(intent: str, code: str) -> bool:
    """
    Rejects outputs that are syntactically valid
    but semantically wrong for the user's intent.
    """

    if intent == "square_grid_layout":
        required = ["Math.sqrt", "row", "col", "setTarget"]
        return all(r in code for r in required)

    if intent == "cone_layout":
        required = ["radius", "(1 -", "setTarget"]
        return all(r in code for r in required)

    if intent == "new_project":
        # Code should NOT be generated yet
        return False

    return True

# ======================================================
# SYSTEM PROMPT (LOCKED)
# ======================================================
from .system_prompt import JARVIS_SYSTEM_PROMPT

# ======================================================
# API Models
# ======================================================
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    provider: str | None = None
    model: str | None = None
    task_type: str | None = None

# ======================================================
# Brain
# ======================================================
def handle_request(message: str) -> dict:
    message = message.strip()

    # --------------------------------------------------
    # Hard exits
    # --------------------------------------------------
    if message.lower() in ("hi", "hii", "hello", "hey"):
        return {
            "response": "Hey 👋",
            "provider": "system",
            "model": "internal",
            "task_type": "chat"
        }

    if message.lower().startswith(("set project ", "set path ")):
        path = message.split(" ", 2)[2]
        response = context_engine.set_project(path)

        loader = ProjectContextLoader(context_engine.project_root)
        loader.load()
        context_engine.project_summary = loader.get_summary()

        response += f"\n\nContext Loaded:\n{context_engine.project_summary}"

        return {
            "response": response,
            "provider": "system",
            "model": "internal",
            "task_type": "command"
        }

    # --------------------------------------------------
    # Mode + Intent
    # --------------------------------------------------
    mode = decide_mode(message)
    intent = extract_intent(message)

    if intent == "new_project":
        return {
            "response": "What is the new project about? Please describe the goal and stack.",
            "provider": "system",
            "model": "internal",
            "task_type": "clarify"
        }

    # --------------------------------------------------
    # Prompt construction
    # --------------------------------------------------
    prompt = f"""
{JARVIS_SYSTEM_PROMPT}

PROJECT SUMMARY:
{context_engine.project_summary}

CURRENT MODE: {mode}

User Request:
{message}
"""

    # --------------------------------------------------
    # Call model
    # --------------------------------------------------
    task_type = "reason" if mode == "UNDERSTAND" else "code"
    result = router.call(task_type, prompt)
    output = result.get("response", "").strip()

    # --------------------------------------------------
    # UNDERSTAND MODE → no validation
    # --------------------------------------------------
    if mode == "UNDERSTAND":
        return {
            "response": output,
            "provider": result.get("provider"),
            "model": result.get("model"),
            "task_type": "understand"
        }

    # --------------------------------------------------
    # CODE MODE → semantic enforcement
    # --------------------------------------------------
    if not semantic_validate(intent, output):
        return {
            "response": (
                "The generated code does not correctly satisfy your request.\n"
                "I am re-evaluating the implementation. Please re-run the command."
            ),
            "provider": "system",
            "model": "semantic_validator",
            "task_type": "retry"
        }

    return {
        "response": output,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "task_type": "code"
    }

# ======================================================
# FastAPI
# ======================================================
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    result = handle_request(req.message)
    return ChatResponse(
        reply=result["response"],
        provider=result["provider"],
        model=result.get("model"),
        task_type=result["task_type"]
    )

# ======================================================
# CLI + Server
# ======================================================
def start_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="error")
    uvicorn.Server(config).run()

def start_cli():
    time.sleep(1)
    print("\n[SYSTEM] JARVIS Brain Online.")
    while True:
        try:
            q = input("\nJARVIS> ").strip()
            if q.lower() in ("exit", "quit"):
                break
            if not q:
                continue

            result = handle_request(q)
            print("\n== RESPONSE ==")
            print(result["response"])
            print("================")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    start_cli()
