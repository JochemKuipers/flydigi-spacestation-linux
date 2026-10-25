Name:           flydigi-vader
Version:        0.1.1
Release:        1%{?dist}
Summary:        Flydigi Vader 4 Pro Linux driver and companion
License:        MIT
URL:            https://origin.cursor.com/jochem-kuipers/flydigi-spacestation-linux
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3

%description
Metapackage split into flydigi-vader4d and vader-companion.

%package -n flydigi-vader4d
Summary:        Userspace DInput driver for Flydigi Vader 4 Pro
Requires:       python3, python3-evdev, systemd

%description -n flydigi-vader4d
Provides a uinput gamepad and Unix control socket for the Flydigi Vader 4 Pro.

%package -n vader-companion
Summary:        Vader Companion for Flydigi Vader 4 Pro
Requires:       python3, python3-evdev, python3-pyside6, flydigi-vader4d

%description -n vader-companion
Desktop app to configure lighting, feel, buttons, and firmware.

%prep
%autosetup -n flydigi-spacestation-linux-%{version}

%build
python3 packaging/stage.py driver --out %{_builddir}/stage-driver
python3 packaging/stage.py companion --out %{_builddir}/stage-companion

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a %{_builddir}/stage-driver/. %{buildroot}/
# Merge companion on top (binaries/docs are distinct).
cp -a %{_builddir}/stage-companion/. %{buildroot}/

%files -n flydigi-vader4d
%doc README.md
/usr/bin/flydigi-vader4d
/usr/bin/flydigi-ctl
/usr/lib/python3.*/site-packages/flydigi
/usr/lib/python3.*/site-packages/driver
/usr/lib/systemd/user/flydigi-vader4d.service
/usr/lib/udev/rules.d/99-flydigi-vader4.rules
/usr/share/doc/flydigi-vader4d/

%files -n vader-companion
/usr/bin/vader-companion
/usr/lib/python3.*/site-packages/app
/usr/share/applications/vader-companion.desktop
/usr/share/icons/hicolor/scalable/apps/vader-companion.svg
/usr/share/vader-companion/
/usr/share/doc/vader-companion/

%post -n flydigi-vader4d
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger >/dev/null 2>&1 || :
echo "Enable the driver with: systemctl --user enable --now flydigi-vader4d.service"

%changelog
* Sun Oct 25 2026 jochem-kuipers <jochem@localhost> - 0.1.1-1
- Move flydigi-ctl into flydigi.ctl so driver no longer ships site-packages/app.

* Sun Oct 25 2026 jochem-kuipers <jochem@localhost> - 0.1.0-1
- Initial package split: flydigi-vader4d + vader-companion.
