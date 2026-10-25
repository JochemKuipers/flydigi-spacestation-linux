#!/usr/bin/env python3
"""Back-compat wrapper — CLI lives in ``flydigi.ctl``."""

from __future__ import annotations

from flydigi.ctl import main

if __name__ == "__main__":
    raise SystemExit(main())
