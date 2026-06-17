"""Husk's automatic LLM debugger (BYOK).

Local-first: the user's API key lives only on their machine (``~/.husk/secrets.json``
or an env var) and the debugger's provider calls go straight from this local
backend to the provider — never through any Husk server. The key is never logged,
never written into traces, and never included in exports.
"""
