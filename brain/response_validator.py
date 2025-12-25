from typing import Dict, Optional

class ResponseValidator:
    def validate(
        self,
        task_mode: str,
        original: Optional[str],
        proposed: str
    ) -> Dict[str, str]:
        """
        Returns:
        {
            "status": "PASS" | "REJECT" | "CONFIRM",
            "reason": str
        }
        """
        task_mode = task_mode.upper()

        if task_mode == "INFO":
            if original and proposed.strip() and proposed.strip() != original.strip():
                return {
                    "status": "REJECT",
                    "reason": "INFO mode is read-only. No modifications allowed."
                }

        if task_mode == "ADD":
            # If it's a unified diff, we trust the DiffValidator (already ran in main.py)
            if proposed.strip().startswith("---"):
                pass
            elif original and original.strip() not in proposed:
                return {
                    "status": "REJECT",
                    "reason": "ADD mode must preserve existing code. Detected rewrite."
                }

        if task_mode == "MODIFY":
            if original:
                original_lines = original.splitlines()
                proposed_lines = proposed.splitlines()
                # Avoid division by zero
                max_len = max(len(original_lines), 1)
                changed_ratio = abs(len(proposed_lines) - len(original_lines)) / max_len

                if changed_ratio > 0.5:
                    return {
                        "status": "CONFIRM",
                        "reason": "Large modification detected (>50% of file). Confirm?"
                    }

        return {
            "status": "PASS",
            "reason": "Validation passed."
        }
