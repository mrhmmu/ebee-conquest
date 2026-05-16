from typing import Protocol


class AIProviderError(Exception):
    """raise when an AI provider cannot complete a request"""


class AIProvider(Protocol):
    """unified interface for ai providers later on"""

    name: str

    def configure(self, **config) -> None:
        """apply providerspecific configuration values"""
        ...

    def ask(self, prompt: str) -> str:
        """return a text response for the provided prompt"""
        ...
