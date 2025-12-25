import os
from typing import List, Set, Optional

class ContextEngine:
    """
    Manages project context.
    STRICT MODE:
    - No implicit file loading
    - Files become active only via explicit request
    """

    def __init__(self):
        self.project_root: Optional[str] = None
        self.file_index: List[str] = []
        self.active_files: Set[str] = set()
        self.focus_file: Optional[str] = None
        self.project_summary: str = ""

        self.ignore_patterns = {
            ".git", "__pycache__", "venv", "node_modules",
            ".env", "dist", "build", ".idea", ".vscode",
            "package-lock.json"
        }

    def set_project(self, path: str) -> str:
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            return f"Error: Invalid project path '{path}'."

        self.project_root = abs_path
        self._build_index()
        self.active_files.clear()
        self.focus_file = None

        return f"Project set to: {self.project_root}\nIndexed {len(self.file_index)} files."

    def _build_index(self):
        self.file_index = []
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in self.ignore_patterns]

            for file in files:
                if file in self.ignore_patterns:
                    continue
                if file.endswith(('.pyc', '.exe', '.dll', '.png', '.jpg', '.zip')):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.project_root)
                self.file_index.append(rel_path)

    # 🔒 Explicit file activation only
    def activate_file(self, rel_path: str) -> bool:
        if not self.project_root:
            return False

        full_path = os.path.join(self.project_root, rel_path)
        if not os.path.isfile(full_path):
            return False

        self.active_files = {rel_path}
        self.focus_file = rel_path
        return True

    def read_active_context(self) -> str:
        if not self.focus_file:
            return ""

        content = self._read_file_safe(self.focus_file)
        if not content:
            return ""

        return (
            "## ACTIVE FILE CONTEXT ##\n"
            f"filename: {self.focus_file}\n"
            "```\n"
            f"{content}\n"
            "```"
        )

    def _read_file_safe(self, rel_path: str) -> Optional[str]:
        full_path = os.path.abspath(os.path.join(self.project_root, rel_path))
        if not full_path.startswith(self.project_root):
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
                return data[:10000] + "\n...[TRUNCATED]" if len(data) > 10000 else data
        except Exception:
            return None

    def has_loaded_file(self) -> bool:
        return self.focus_file is not None

    def get_original_file(self) -> str:
        if not self.focus_file:
            return ""
        return self._read_file_safe(self.focus_file) or ""
