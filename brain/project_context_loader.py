import os

class ProjectContextLoader:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.file_summaries = {}

    def load(self):
        for root, _, files in os.walk(self.project_root):
            for file in files:
                if file.endswith((".html", ".js", ".css", ".py")):
                    path = os.path.join(root, file)
                    self.file_summaries[file] = self._summarize_file(path)

    def _summarize_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return "Could not read file."

        summary = []

        if "<html" in content.lower():
            summary.append("HTML document")

        if "three" in content.lower():
            summary.append("Uses Three.js")

        if "particle" in content.lower():
            summary.append("Contains particle system")

        if "shapes" in content:
            summary.append("Defines shapes object for layouts")

        if "settarget" in content.lower():
            summary.append("Uses setTarget() for particle positioning")

        return ", ".join(summary) or "General code file"

    def get_summary(self) -> str:
        output = ["PROJECT SUMMARY:"]
        for file, desc in self.file_summaries.items():
            output.append(f"- {file}: {desc}")
        return "\n".join(output)
