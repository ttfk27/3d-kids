import requests

from .config import LLMCfg
from .util import MptProError, extract_json


class LLM:
    """Any OpenAI-compatible chat endpoint (Ollama, vLLM, LM Studio, llama.cpp server, ...)."""

    def __init__(self, cfg: LLMCfg):
        self.cfg = cfg

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        body = {
            "model": self.cfg.model,
            "temperature": self.cfg.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode and self.cfg.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        try:
            r = requests.post(url, json=body, headers=headers, timeout=self.cfg.timeout_s)
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")  # server without JSON mode
                r = requests.post(url, json=body, headers=headers, timeout=self.cfg.timeout_s)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            raise MptProError(f"LLM request failed ({url}): {e}")

    def chat_json(self, system: str, user: str, attempts: int = 3):
        last = None
        for _ in range(attempts):
            reply = self.chat(system, user, json_mode=True)
            try:
                return extract_json(reply)
            except ValueError as e:
                last = e
        raise MptProError(f"LLM did not return valid JSON after {attempts} attempts: {last}")
