from typing import Dict

class IntentEngine:
    """
    Classifies user inputs into high-level intents.
    This engine MUST be conservative.
    """

    def classify(self, query: str) -> Dict[str, str]:
        q = query.strip().lower()

        # 1️⃣ Pure chat / greetings (hard exit)
        if q in {"hi", "hii", "hello", "hey", "yo", "greetings"}:
            return {"task_type": "chat"}

        # 2️⃣ Project inspection (no LLM modification)
        if any(k in q for k in [
            "list files",
            "show files",
            "what files",
            "project structure",
            "folder structure",
            "tree",
            "directories",
        ]):
            return {"task_type": "project_info"}

        # 3️⃣ Explanation / reasoning (read-only)
        if any(k in q for k in [
            "explain",
            "why",
            "how does",
            "what is",
            "difference",
            "reason",
            "summary",
            "summarize",
        ]):
            return {"task_type": "info"}

        # 4️⃣ Debugging (code-aware but not destructive by default)
        if any(k in q for k in [
            "bug",
            "error",
            "issue",
            "crash",
            "exception",
            "debug",
        ]):
            return {"task_type": "debug"}

        # 5️⃣ Explicit code changes ONLY
        if any(k in q for k in [
            "add",
            "create",
            "implement",
            "modify",
            "update",
            "refactor",
            "remove",
            "delete",
        ]):
            return {"task_type": "code"}

        # 6️⃣ Safe default
        return {"task_type": "info"}
