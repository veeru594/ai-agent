import os
import requests
import json
import logging
import re
from typing import Dict, Any, List, Optional

from .key_manager import KeyManager
from .mcp import MCPRead

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ModelRouter:
    """
    Routes tasks with strict priority:
    - Code -> Groq (llama-3.3-70b-versatile)
    - Reason/Plan -> DeepSeek Reasoner -> OpenRouter (Llama 3.1 70B) -> OpenRouter (Qwen 2.5 32B)
    """

    def __init__(self, context_engine=None):
        self.km_groq = KeyManager("GROQ")
        self.km_openrouter = KeyManager("OPENROUTER")
        try:
            self.km_deepseek = KeyManager("DEEPSEEK")
        except RuntimeError:
            self.km_deepseek = None
            
        # Initialize MCP
        self.mcp = MCPRead(context_engine) if context_engine else None

    def call(self, task_type: str, prompt: str) -> Dict[str, Any]:
        """Strict routing logic with fallback chains and MCP-READ interception."""
        
        # Inject MCP-READ system prompt rules
        prompt = self._apply_mcp_rules(prompt)

        # Initial Call
        if task_type in ("reason", "plan"):
            if task_type == "reason":
                prompt = self._apply_reasoning_grounding(prompt)
            result = self._call_reasoning_chain(prompt)
        elif task_type == "code":
            try:
                response = self._call_groq(prompt)
                result = {
                    "provider": "groq", 
                    "response": response, 
                    "model": "llama-3.3-70b-versatile"
                }
            except Exception as e:
                logger.error(f"Groq failed: {e}")
                logger.info("Falling back to reasoning chain for code task...")
                result = self._call_reasoning_chain(prompt)
        else:
            result = self._call_reasoning_chain(prompt)

        # Check for Tool Calls (MCP-READ)
        # We allow a max depth of 2 recursions to prevent loops
        return self._process_tool_calls(result, task_type, prompt, depth=0)

    def _process_tool_calls(self, result: Dict[str, Any], task_type: str, original_prompt: str, depth: int) -> Dict[str, Any]:
        """Intercepts 'read_file' requests and feeds content back to the model."""
        if depth >= 2:
            return result
            
        response_text = result["response"]
        tool_call = self._extract_tool_call(response_text)
        
        if not tool_call:
            return result
            
        if tool_call.get("tool") == "read_file":
            path = tool_call.get("path")
            logger.info(f"MCP-READ Interception: Reading {path}")
            
            try:
                if not self.mcp:
                    raise RuntimeError("MCP not initialized")
                    
                file_content = self.mcp.read_file(path)
                
                # Construct follow-up prompt
                followup_prompt = (
                    f"{original_prompt}\n\n"
                    f"You requested the following file:\n\n"
                    f"FILE: {path}\n"
                    f"------------------\n"
                    f"{file_content}\n"
                    f"------------------\n\n"
                    f"Continue your task using this as source of truth."
                )
                
                # Recursive call with new prompt
                # (We bypass initial grounding injection to avoid duplicating it too many times, 
                # but for simplicity calling internal methods or recursing 'call' is fine.
                # Let's call the specific provider chain again to keep it simple.)
                
                if task_type == "code" and result["provider"] == "groq":
                     # Retry Groq
                     new_resp = self._call_groq(followup_prompt)
                     new_result = {"provider": "groq", "response": new_resp, "model": "llama-3.3-70b-versatile"}
                else:
                     new_result = self._call_reasoning_chain(followup_prompt)
                     
                return self._process_tool_calls(new_result, task_type, followup_prompt, depth + 1)
                
            except Exception as e:
                logger.error(f"MCP-READ Failed: {e}")
                # Feed error back to model? Or just fail? 
                # For safety, let's append error and retry once.
                error_prompt = (
                     f"{original_prompt}\n\n"
                     f"TOOL ERROR: Failed to read file '{path}'. Reason: {str(e)}\n"
                     "Proceed without this file or request a different one."
                )
                if task_type == "code" and result["provider"] == "groq":
                     new_resp = self._call_groq(error_prompt)
                     new_result = {"provider": "groq", "response": new_resp, "model": "llama-3.3-70b-versatile"}
                else:
                     new_result = self._call_reasoning_chain(error_prompt)
                     
                return self._process_tool_calls(new_result, task_type, error_prompt, depth + 1)

        return result

    def _extract_tool_call(self, text: str) -> Optional[Dict]:
        """
        Parses { "tool": "read_file", ... } from text.
        Returns dict if found, None otherwise.
        """
        # Look for JSON-like block
        # Simple regex for the specific pattern requested
        # We look for the exact JSON structure provided in instructions
        try:
            # fast check
            if '"tool": "read_file"' not in text:
                return None
                
            # Attempt to find json block
            # This is a bit heuristic, assuming the model outputs valid JSON in a block or standalone
            match = re.search(r'\{.*"tool":\s*"read_file".*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return None

    def _apply_mcp_rules(self, prompt: str) -> str:
        rules = (
            "🔒 SYSTEM ROLE\n"
            "You are a coding assistant operating in READ-ONLY + SNIPPET MODE.\n"
            "You DO NOT:\n"
            "- write to files\n"
            "- apply patches\n"
            "- output unified diffs\n"
            "- rewrite full files\n"
            "- refactor existing logic\n"
            "- optimize or “clean up” code\n"
            "You ONLY:\n"
            "- read files when provided\n"
            "- reason over existing code\n"
            "- output minimal, additive code snippets\n"
            "The user applies changes manually.\n\n"
            "📂 FILE CONTEXT RULES (CRITICAL)\n"
            "You may only reason about code you can see.\n"
            "If a request depends on existing code and the file content is not provided:\n"
            "- Ask for the file explicitly.\n"
            "- Do NOT guess.\n"
            "- Never assume project structure, variable names, or logic.\n"
            "Example allowed response:\n"
            "“I need to see the file where the shapes object is defined to add a new shape safely.”\n\n"
            "🧠 CHANGE SCOPE RULES (NON-NEGOTIABLE)\n"
            "Unless the user explicitly says rewrite / refactor, you must assume:\n"
            "- Existing code is correct\n"
            "- Existing logic must remain untouched\n"
            "- Existing behavior must not change\n"
            "You are in ADDITIVE-ONLY MODE by default.\n"
            "This means:\n"
            "- Add new functions\n"
            "- Add new objects\n"
            "- Add new cases / handlers\n"
            "- Add new shape definitions\n"
            "❌ You must NOT:\n"
            "- remove existing code\n"
            "- rename variables\n"
            "- reorder logic\n"
            "- simplify loops\n"
            "- merge functions\n"
            "- change behavior “for clarity”\n\n"
            "✂️ OUTPUT FORMAT RULES (VERY IMPORTANT)\n"
            "When asked to add or modify functionality:\n"
            "- Output ONLY the exact code snippet to add\n"
            "- No explanations before or after\n"
            "- No markdown fences unless the user asks\n"
            "- No full files\n"
            "- No diffs\n"
            "- No commentary\n"
            "If placement matters, add one short comment like:\n"
            "// ADD INSIDE `shapes` OBJECT\n\n"
            "🛑 FAILURE CONDITION\n"
            "If you violate any rule above, your response is considered invalid and will be discarded.\n"
            "Proceed accordingly.\n\n"
        )
        return rules + prompt

    def _apply_reasoning_grounding(self, prompt: str) -> str:
        """Prepends grounding instructions to prevent hallucinated ignorance."""
        grounding = (
            "You are continuing an ongoing technical discussion.\n"
            "Assume that:\n"
            "- A refactor or code change MAY have been suggested earlier in this session.\n"
            "- The question refers to that earlier suggestion, even if it was made by another model.\n"
            "- Answer strictly based on the provided project files and inferred prior changes.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Do NOT invent or name classes, functions, variables, or files that are not present in the provided context.\n"
            "- If exact identifiers are unknown, describe changes behaviorally instead of naming code entities.\n"
            "- If an answer cannot be grounded in the provided files, say so explicitly.\n\n"
        )
        return grounding + prompt

    def _call_reasoning_chain(self, prompt: str) -> Dict[str, Any]:
        """Tries providers in strict priority order for reasoning."""
        
        # 1. DeepSeek Reasoner
        if self.km_deepseek:
            try:
                resp = self._call_deepseek_direct(prompt)
                return {"provider": "deepseek", "response": resp, "model": "deepseek-reasoner"}
            except Exception as e:
                logger.warning(f"DeepSeek Reasoner failed: {e}")
        
        # 2. OpenRouter: Llama 3.1 70B
        try:
            resp = self._call_openrouter(prompt, "meta-llama/llama-3.1-70b-instruct")
            return {"provider": "openrouter", "response": resp, "model": "meta-llama/llama-3.1-70b-instruct"}
        except Exception as e:
            logger.warning(f"OpenRouter Llama 70B failed: {e}")

        # 3. OpenRouter: Qwen 2.5 32B
        try:
            resp = self._call_openrouter(prompt, "qwen/qwen2.5-32b-instruct")
            return {"provider": "openrouter", "response": resp, "model": "qwen/qwen2.5-32b-instruct"}
        except Exception as e:
            logger.error(f"OpenRouter Qwen 32B failed: {e}")
            
        raise RuntimeError("All reasoning providers failed.")

    def _call_deepseek_direct(self, prompt: str) -> str:
        key = self.km_deepseek.get_key()
        url = "https://api.deepseek.com/chat/completions"
        
        payload = {
            "model": "deepseek-reasoner",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if not resp.ok:
                logger.error(f"DeepSeek Error: {resp.status_code} - {resp.text}")
                self.km_deepseek.report_failure(key, status=resp.status_code)
                resp.raise_for_status()
            
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"DeepSeek Network Error Body: {e.response.text}")
            self.km_deepseek.report_failure(key, status=getattr(e.response, 'status_code', 0) if e.response else 0)
            raise e

    def _call_openrouter(self, prompt: str, model: str) -> str:
        key = self.km_openrouter.get_key()
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Jarvis"
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=45)
            
            if not resp.ok:
                logger.error(f"OpenRouter Error ({model}): {resp.status_code} - {resp.text}")
                self.km_openrouter.report_failure(key, status=resp.status_code)
                resp.raise_for_status()
            
            data = resp.json()
            return data["choices"][0]["message"]["content"]
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                 logger.error(f"OpenRouter Network Error Body: {e.response.text}")
            self.km_openrouter.report_failure(key, status=getattr(e.response, 'status_code', 0) if e.response else 0)
            raise e

    def _call_groq(self, prompt: str) -> str:
        key = self.km_groq.get_key()
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if not resp.ok:
                logger.error(f"Groq Error: {resp.status_code} - {resp.text}")
                self.km_groq.report_failure(key, status=resp.status_code)
                resp.raise_for_status()
                
            data = resp.json()
            return data["choices"][0]["message"]["content"]
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                 logger.error(f"Groq Network Error Body: {e.response.text}")
            self.km_groq.report_failure(key, status=getattr(e.response, 'status_code', 0) if e.response else 0)
            raise e
