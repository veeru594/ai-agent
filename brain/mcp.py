from pathlib import Path

class MCPError(Exception):
    pass

class MCPRead:
    def __init__(self, context_engine, max_chars=12000):
        self.context_engine = context_engine
        self.max_chars = max_chars

    def read_file(self, path: str) -> str:
        if not self.context_engine.project_root:
            raise MCPError("No project set")

        project_root = Path(self.context_engine.project_root).resolve()
        file_path = (project_root / path).resolve()

        if not str(file_path).startswith(str(project_root)):
            raise MCPError("Access denied: outside project")

        if not file_path.exists() or not file_path.is_file():
            raise MCPError(f"File not found: {path}")

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if len(content) > self.max_chars:
            content = content[:self.max_chars] + "\n\n[TRUNCATED]"

        return content
