#!/usr/bin/env python3
"""Run commands in the win10 libvirt guest via QEMU guest agent (no SSH needed).

Examples:
  python3 tools/win_guest.py whoami
  python3 tools/win_guest.py --ps "Get-Service sshd"
  python3 tools/win_guest.py --cmd "dir C:\\"
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time


URI = "qemu:///system"
DOMAIN = "win10"


def guest_exec(
    path: str,
    argv: list[str],
    *,
    timeout: float = 120.0,
) -> tuple[int, bytes, bytes]:
    payload = {
        "execute": "guest-exec",
        "arguments": {
            "path": path,
            "arg": argv,
            "capture-output": True,
        },
    }
    # virsh wants the JSON command object as one arg
    started = subprocess.check_output(
        ["virsh", "-c", URI, "qemu-agent-command", DOMAIN, json.dumps(payload)],
        text=True,
    )
    pid = json.loads(started)["return"]["pid"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = subprocess.check_output(
            [
                "virsh",
                "-c",
                URI,
                "qemu-agent-command",
                DOMAIN,
                json.dumps(
                    {"execute": "guest-exec-status", "arguments": {"pid": pid}}
                ),
            ],
            text=True,
        )
        ret = json.loads(st)["return"]
        if ret.get("exited"):
            out = base64.b64decode(ret.get("out-data") or "")
            err = base64.b64decode(ret.get("err-data") or "")
            return int(ret.get("exitcode") or 0), out, err
        time.sleep(0.4)
    raise TimeoutError(f"guest-exec pid={pid} timed out after {timeout}s")


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-16le", "cp437", "latin1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin1", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--ps", help="PowerShell -Command string")
    ap.add_argument("--cmd", help="cmd.exe /c string")
    ap.add_argument("words", nargs="*", help="shortcut: cmd /c <words…>")
    args = ap.parse_args()

    if args.ps:
        path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        argv = ["-NoProfile", "-NonInteractive", "-Command", args.ps]
    elif args.cmd:
        path = r"C:\Windows\System32\cmd.exe"
        argv = ["/c", args.cmd]
    elif args.words:
        path = r"C:\Windows\System32\cmd.exe"
        argv = ["/c", " ".join(args.words)]
    else:
        ap.error("provide --ps, --cmd, or a command string")

    try:
        code, out, err = guest_exec(path, argv, timeout=args.timeout)
    except (subprocess.CalledProcessError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
        print(f"guest-exec failed: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(_decode(out))
    if err:
        sys.stderr.write(_decode(err))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
