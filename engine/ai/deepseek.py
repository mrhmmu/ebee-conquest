import json
import os
from threading import RLock
import urllib.error
import urllib.request

from .provider import AIProviderError


class DeepSeekProvider:
    name = "deepseek"

    def __init__(
        self,
        api_key=None,
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        timeout=30,
    ):
        self._lock = RLock()
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def configure(self, **config):
        allowed_keys = {"api_key", "model", "base_url", "timeout"}
        unknown_keys = sorted(set(config) - allowed_keys)
        if unknown_keys:
            unknown_text = ", ".join(unknown_keys)
            raise ValueError(f"DeepSeek does not recognize config value(s): {unknown_text}.")

        with self._lock:
            if "api_key" in config:
                self.api_key = config["api_key"]
            if "model" in config:
                self.model = config["model"] or self.model
            if "base_url" in config:
                self.base_url = str(config["base_url"]).rstrip("/")
            if "timeout" in config:
                self.timeout = int(config["timeout"])

    def ask(self, prompt: str) -> str:
        with self._lock:
            api_key = self.api_key
            model = self.model
            base_url = self.base_url
            timeout = self.timeout

        if not api_key:
            raise AIProviderError(
                "DeepSeek API key is missing. Set it with "
                "AIManager.set_provider_config('deepseek', api_key='...')."
            )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = self._read_error_message(error)
            raise AIProviderError(f"DeepSeek request failed: {message}") from error
        except urllib.error.URLError as error:
            raise AIProviderError("Could not connect to DeepSeek. Please check your connection.") from error
        except TimeoutError as error:
            raise AIProviderError("DeepSeek took too long to respond. Please try again.") from error

        try:
            data = json.loads(raw_body)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise AIProviderError("DeepSeek returned an unexpected response.") from error

        return str(content).strip()

    def _read_error_message(self, error):
        fallback = f"HTTP {error.code}"
        try:
            body = error.read().decode("utf-8")
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return fallback

        if isinstance(data, dict):
            detail = data.get("error")
            if isinstance(detail, dict):
                return str(detail.get("message") or fallback)
            if isinstance(detail, str):
                return detail
            if isinstance(data.get("message"), str):
                return data["message"]

        return fallback
