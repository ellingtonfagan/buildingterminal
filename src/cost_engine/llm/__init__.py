"""LLM subsystem: versioned prompts, aggressive caching, and a structured-output
client with schema validation and retry. The LLM only ever parses input into a
structured shape — it never produces a number used as a cost or confidence."""
