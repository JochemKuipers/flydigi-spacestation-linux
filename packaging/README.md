# Packaging

Separate packages:

| Package | What | Formats |
|---------|------|---------|
| **flydigi-vader4d** | Driver, `flydigi-ctl`, udev rules, user systemd unit | AUR, `.deb`, `.rpm` |
| **vader-companion** | Qt companion UI + desktop entry + bundled F4 firmware | AUR, `.deb`, `.rpm`, **AppImage** |

Version is read from [`../VERSION`](../VERSION).

## Quick local stage (no package manager)

```bash
python3 packaging/stage.py all
# → build/stage-driver   build/stage-companion
```

Inspect the FHS trees under `build/stage-*`, then install with `sudo cp -a` if you want a manual smoke test.

## AUR

Recipes live in `aur/flydigi-vader4d/` and `aur/vader-companion/`.

Until a public tarball/tag exists, build from a local clone:

```bash
cd packaging/aur/flydigi-vader4d
# Point source at the repo root for a local makepkg:
#   source=("flydigi-vader4d-$pkgver::git+file://$PWD/../../..")
makepkg -si
cd ../vader-companion && makepkg -si
```

Companion depends on `flydigi-vader4d`. After install:

```bash
systemctl --user enable --now flydigi-vader4d.service
vader-companion
```

## Debian / Ubuntu (`.deb`)

```bash
# needs: debhelper, dpkg-dev, python3, dh-python, python3-evdev, …
./packaging/build-deb.sh
# → dist/flydigi-vader4d_*.deb  dist/vader-companion_*.deb
```

## Fedora / RHEL (`.rpm`)

```bash
# needs: rpm-build, python3, …
./packaging/build-rpm.sh
# → dist/*.rpm
```

## AppImage (companion only)

```bash
./packaging/companion/appimage/build-appimage.sh
# → dist/Vader_Companion-<ver>-x86_64.AppImage
```

The AppImage bundles PySide6/evdev. The **driver is not inside the AppImage** — install `flydigi-vader4d` from your distro package (or run it from source) so the companion can talk to the pad.

## Layout after install

```
/usr/bin/flydigi-vader4d
/usr/bin/flydigi-ctl
/usr/bin/vader-companion
/usr/lib/systemd/user/flydigi-vader4d.service
/usr/lib/udev/rules.d/99-flydigi-vader4.rules
/usr/share/applications/vader-companion.desktop
/usr/share/vader-companion/firmware/*.bin
```
