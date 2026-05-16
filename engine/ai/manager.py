from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from itertools import count
from threading import RLock

from .provider import AIProvider


@dataclass(frozen=True)
class AIRequest:
    request_id: int
    prompt: str
    provider_name: str
    future: Future

    def done(self) -> bool:
        return self.future.done()

    def result(self) -> str:
        return self.future.result()


class AIManager:
    """to coordinate providers and unified interface"""

    def __init__(self, max_workers=2):
        self._providers = {}
        self._active_provider_name = None
        self._lock = RLock()
        self._request_counter = count(1)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="EbeeAI",
        )

    @property
    def active_provider_name(self):
        with self._lock:
            return self._active_provider_name

    def register_provider(self, provider: AIProvider, select=False):
        provider_name = getattr(provider, "name", None)
        if not provider_name:
            raise ValueError("ai provider need name")

        with self._lock:
            self._providers[provider_name] = provider
            if select or self._active_provider_name is None:
                self._active_provider_name = provider_name
        return provider

    def select_provider(self, provider_name):
        with self._lock:
            if provider_name not in self._providers:
                raise ValueError(f"ai provider '{provider_name}' is not there")

            self._active_provider_name = provider_name
            return self._providers[provider_name]

    def set_provider_config(self, provider_name: str, **config):
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider is None:
                raise ValueError(f"AI provider '{provider_name}' is not registered.")

            provider.configure(**config)
        return provider

    def ask(self, prompt: str) -> str:
        provider_name, provider, cleanprompt = self._prepare_request(prompt)
        return provider.ask(cleanprompt)

    def ask_async(self, prompt: str) -> AIRequest:
        provider_name, provider, cleanprompt = self._prepare_request(prompt)
        request_id = next(self._request_counter)
        future = self._executor.submit(provider.ask, cleanprompt)
        return AIRequest(
            request_id=request_id,
            prompt=cleanprompt,
            provider_name=provider_name,
            future=future,
        )

    def shutdown(self, wait=False):
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _prepare_request(self, prompt):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("need prompt before asking ai")

        with self._lock:
            if self._active_provider_name is None:
                raise RuntimeError("no ai provider")

            provider_name = self._active_provider_name
            provider = self._providers[provider_name]

        return provider_name, provider, prompt.strip()


def create_default_manager():
    from .deepseek import DeepSeekProvider

    manager = AIManager()
    manager.register_provider(DeepSeekProvider(), select=True)
    return manager
