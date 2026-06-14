"""HTTP virtualization (record/replay) — thin façade over `cassette`.

Kept as the stable, documented entry point. The real implementation lives in
`husk_sandbox.cassette`; these helpers monkeypatch httpx so any SDK that builds
its own client is captured/served transparently.

    install_record_mode(dir)   # record every sync httpx request to `dir`
    install_replay_mode(dir)   # serve from `dir`; cache-miss falls through to net
    uninstall()                # restore httpx
"""

from __future__ import annotations

from husk_sandbox.cassette import (
    CassetteStore,
    install_record_mode,
    install_replay_mode,
    uninstall,
)

__all__ = ["CassetteStore", "install_record_mode", "install_replay_mode", "uninstall"]
