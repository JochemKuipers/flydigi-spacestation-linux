#!/usr/bin/env python3
"""Stage FHS trees for flydigi-vader4d and vader-companion packages."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def _py_site(prefix: Path, *, layout: str) -> Path:
    """layout: site-packages (Arch/Fedora) or dist-packages (Debian/Ubuntu)."""
    if layout == "dist-packages":
        return prefix / "usr" / "lib" / "python3" / "dist-packages"
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    return prefix / "usr" / "lib" / f"python{ver}" / "site-packages"


def _write_script(path: Path, module: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        f"from {module} import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _copy_pkg(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", ".git", "*.service"
        ),
    )
    # Do not compile here — bytecode embeds build paths and trips namcap/makepkg.


def stage_driver(dest: Path, *, layout: str = "site-packages") -> None:
    if dest.exists():
        shutil.rmtree(dest)
    site = _py_site(dest, layout=layout)
    site.mkdir(parents=True)
    _copy_pkg(ROOT / "flydigi", site / "flydigi")
    _copy_pkg(ROOT / "driver", site / "driver")

    _write_script(dest / "usr/bin/flydigi-vader4d", "driver.flydigi_vader4d")
    _write_script(dest / "usr/bin/flydigi-ctl", "flydigi.ctl")

    unit = dest / "usr/lib/systemd/user/flydigi-vader4d.service"
    unit.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/systemd/flydigi-vader4d.service", unit)

    rules = dest / "usr/lib/udev/rules.d/99-flydigi-vader4.rules"
    rules.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "udev/99-flydigi-vader4.rules", rules)

    doc = dest / "usr/share/doc/flydigi-vader4d"
    doc.mkdir(parents=True)
    shutil.copy2(ROOT / "README.md", doc / "README.md")
    print(f"staged driver → {dest}")


def stage_companion(
    dest: Path, *, bundle_flydigi: bool = False, layout: str = "site-packages"
) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    site = _py_site(dest, layout=layout)
    site.mkdir(parents=True)
    if bundle_flydigi:
        _copy_pkg(ROOT / "flydigi", site / "flydigi")
    _copy_pkg(ROOT / "app", site / "app")
    _write_script(dest / "usr/bin/vader-companion", "app.vader_companion")

    apps = dest / "usr/share/applications"
    apps.mkdir(parents=True)
    shutil.copy2(
        ROOT / "packaging/desktop/vader-companion.desktop",
        apps / "vader-companion.desktop",
    )

    icon = dest / "usr/share/icons/hicolor/scalable/apps/vader-companion.svg"
    icon.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "app/ui/assets/vader4pro_app_icon.svg", icon)

    fw_src = ROOT / "archive/firmware/f4/6.9.3.3/F4_Telink87_Gamepad_6933_1025.bin"
    fw_dst = dest / "usr/share/vader-companion/firmware"
    fw_dst.mkdir(parents=True)
    if fw_src.is_file():
        shutil.copy2(fw_src, fw_dst / fw_src.name)

    doc = dest / "usr/share/doc/vader-companion"
    doc.mkdir(parents=True)
    shutil.copy2(ROOT / "README.md", doc / "README.md")
    print(f"staged companion → {dest} (bundle_flydigi={bundle_flydigi})")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("what", choices=("driver", "companion", "all"))
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--bundle-flydigi",
        action="store_true",
        help="Ship flydigi inside companion (AppImage). Distro pkgs depend on the driver instead.",
    )
    p.add_argument(
        "--layout",
        choices=("site-packages", "dist-packages"),
        default="site-packages",
        help="Python lib layout (dist-packages for Debian/Ubuntu).",
    )
    args = p.parse_args()
    if args.what in ("driver", "all"):
        stage_driver(args.out or BUILD / "stage-driver", layout=args.layout)
    if args.what in ("companion", "all"):
        out = args.out
        if args.what == "all":
            out = BUILD / "stage-companion"
        stage_companion(
            out or BUILD / "stage-companion",
            bundle_flydigi=args.bundle_flydigi,
            layout=args.layout,
        )
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
