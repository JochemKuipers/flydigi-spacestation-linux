"""CLI client for flydigi-vader4d control socket."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flydigi.ipc import DaemonClient, default_socket_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--socket", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping")
    sub.add_parser("info")
    rumble = sub.add_parser("rumble")
    rumble.add_argument("low", type=int)
    rumble.add_argument("high", type=int)
    rumble.add_argument(
        "--ms",
        type=int,
        default=1500,
        help="how long to keep refreshing rumble packets (0 = one shot / stop)",
    )
    sub.add_parser("led-get")
    led = sub.add_parser("led-set")
    led.add_argument(
        "--mode", type=int, default=5, help="0=off 1=stream 2=breath 5=steady"
    )
    led.add_argument("--r", type=int, default=0)
    led.add_argument("--g", type=int, default=255)
    led.add_argument("--b", type=int, default=0)
    led.add_argument("--brightness", type=int, default=80)
    led.add_argument("--speed", type=int, default=50)
    sub.add_parser("config-get")
    sticks = sub.add_parser("deadzone")
    sticks.add_argument("--left", type=int, default=None)
    sticks.add_argument("--right", type=int, default=None)

    args = p.parse_args()
    path = args.socket or default_socket_path()
    try:
        with DaemonClient(path) as c:
            if args.cmd == "ping":
                print(json.dumps(c.request("ping"), indent=2))
            elif args.cmd == "info":
                print(json.dumps(c.request("info"), indent=2))
            elif args.cmd == "rumble":
                print(
                    json.dumps(
                        c.request(
                            "rumble",
                            low=args.low,
                            high=args.high,
                            duration_ms=args.ms,
                        ),
                        indent=2,
                    )
                )
            elif args.cmd == "led-get":
                print(json.dumps(c.request("led_get"), indent=2))
            elif args.cmd == "led-set":
                print(
                    json.dumps(
                        c.request(
                            "led_set",
                            mode=args.mode,
                            r=args.r,
                            g=args.g,
                            b=args.b,
                            brightness=args.brightness,
                            speed=args.speed,
                        ),
                        indent=2,
                    )
                )
            elif args.cmd == "config-get":
                print(json.dumps(c.request("config_get"), indent=2))
            elif args.cmd == "deadzone":
                payload: dict = {}
                if args.left is not None:
                    payload["left_stick"] = {"zero": args.left}
                if args.right is not None:
                    payload["right_stick"] = {"zero": args.right}
                print(json.dumps(c.request("config_set_sticks", **payload), indent=2))
    except (ConnectionError, FileNotFoundError, OSError) as exc:
        print(f"Cannot reach daemon at {path}: {exc}", file=sys.stderr)
        print("Start: systemctl --user start flydigi-vader4d.service", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
