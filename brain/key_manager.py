import os
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class KeyManager:
    """
    Manages API keys for a specific provider.
    Rotates keys on 429 (Rate Limit), 403 (Permission), or Network Failure (0).
    """

    def __init__(self, provider_prefix: str):
        self.provider_prefix = provider_prefix.upper()
        self.keys = self._load_keys()
        if not self.keys:
            raise RuntimeError(f"No keys found for {self.provider_prefix} (checked {self.provider_prefix}_KEY_*)")
        
        self.current_index = 0
        # Timestamp until which a key is blacklisted
        self.blacklist_until: Dict[str, float] = {}

    def _load_keys(self) -> List[str]:
        """
        Loads keys from env vars like GEMINI_KEY_1, GEMINI_KEY_2...
        Sorts them to ensure deterministic usage order.
        """
        prefix = f"{self.provider_prefix}_KEY_"
        candidates = []
        for k, v in os.environ.items():
            if k.startswith(prefix) and v.strip():
                candidates.append((k, v.strip()))
        
        # Sort by variable name (e.g. KEY_1 before KEY_2)
        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]

    def get_key(self) -> str:
        """Returns the current valid key, skipping blacklisted ones."""
        attempts = 0
        while attempts < len(self.keys):
            key = self.keys[self.current_index]
            if self._is_blacklisted(key):
                self._rotate()
                attempts += 1
                continue
            return key
        
        # If all are blacklisted, just return the current one to try anyway
        return self.keys[self.current_index]

    def report_failure(self, key: str, status: int = 0):
        """
        Reports a failure.
        status=429 -> Rate limit (blacklist 60s)
        status=403 -> Forbidden (blacklist 5m)
        status=0   -> Network/Unknown (rotate, short backoff)
        """
        should_rotate = False
        cooldown = 0
        
        if status == 429:
            should_rotate = True
            cooldown = 60
        elif status == 403:
            should_rotate = True
            cooldown = 300
        elif status == 0 or status >= 500:
            # Network error or server error
            should_rotate = True
            cooldown = 10 
        
        if should_rotate:
            logger.warning(f"Key failure for {self.provider_prefix} (status={status}). Rotating.")
            if cooldown > 0:
                self.blacklist_until[key] = time.time() + cooldown
            self._rotate()

    def _rotate(self):
        self.current_index = (self.current_index + 1) % len(self.keys)

    def _is_blacklisted(self, key: str) -> bool:
        until = self.blacklist_until.get(key, 0)
        return time.time() < until