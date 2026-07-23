"""Cost Engine v0 — NYC building cost estimation.

Design principle (never violated): LLMs parse unstructured input into structured
data; deterministic code produces every number. No model output is ever used
directly as a dollar figure or a confidence level.
"""

__version__ = "0.1.0"
