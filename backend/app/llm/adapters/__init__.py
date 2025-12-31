"""LLM 适配器模块。"""

from .base import BaseLLM
from .openai_compat import OpenAICompatLLM

__all__ = ["BaseLLM", "OpenAICompatLLM"]
