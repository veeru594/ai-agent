from pathlib import Path
import tempfile
import subprocess


class MCPWriteError(Exception):
    pass


class MCPWrite:
    def __init__(self, context_engine):
        self.context_engine = context_engine

    def apply_diff(self, diff_text: str) -> str:
        """
        Applies a unified diff to the currently active file.
        Implicit apply. Fails hard on any mismatch.
        """

        if not self.context_engine.has_loaded_file():
            raise MCPWriteError("No active file to apply diff")

        if not self.context_engine.project_root:
            raise MCPWriteError("No project root set")

        target = self.context_engine.focus_file
        project_root = Path(self.context_engine.project_root).resolve()
        file_path = (project_root / target).resolve()

        # Sandbox enforcement
        if not str(file_path).startswith(str(project_root)):
            raise MCPWriteError("Access denied: outside project")

        if not file_path.exists():
            raise MCPWriteError(f"Target file does not exist: {target}")

        # Basic sanity check: unified diff markers
        if not diff_text.strip().startswith("---"):
            raise MCPWriteError("Invalid diff: missing '---' header")
        if "@@" not in diff_text:
            raise MCPWriteError("Invalid diff: no hunks found")

        # Write diff to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".diff",
            delete=False,
            encoding="utf-8"
        ) as tmp:
            tmp.write(diff_text)
            diff_path = Path(tmp.name)

        # Apply diff using git
        try:
            result = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(diff_path)],
                cwd=project_root,
                capture_output=True,
                text=True
            )
        finally:
            diff_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise MCPWriteError(
                "Failed to apply diff.\n"
                f"STDERR:\n{result.stderr.strip()}"
            )

        return f"Applied diff to {target}"
