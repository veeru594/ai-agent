import re

class DiffValidationError(Exception):
    pass

class DiffValidator:
    def validate(self, diff: str) -> None:
        if not diff.strip().startswith("---"):
            raise DiffValidationError("Not a unified diff")

        if "+++" not in diff or "@@" not in diff:
            raise DiffValidationError("Malformed diff")

        lines = diff.splitlines()
        
        # stricter counting avoiding headers
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

        if added > 0 and removed > added * 5: # Allow some leeway but block massive deletions
            raise DiffValidationError("Diff removes too much code")

        # hard block full rewrites (heuristic)
        # If > 200 lines, it's risky.
        if added + removed > 300: # Bumped slightly for safety
            raise DiffValidationError("Diff too large — likely rewrite")
