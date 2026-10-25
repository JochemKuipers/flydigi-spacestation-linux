# Windows VM oracle (`win10`)

Keep the project on Linux. Use the libvirt guest as a reference for Space
Station behavior — don’t Remote-SSH Cursor into Windows.

## Why guest USBPcap failed

`win10` uses **SPICE usbredir**. Inside the guest, USBPcap mostly sees
**enumeration** for redirected pads, not HID interrupt OUT (config writes).
That’s a redirect limitation, not a filter mistake.

**Capture instead on the Linux host** with `usbmon` while the pad is attached
as a libvirt **hostdev** (full USB passthrough):

SS4 on this VM treats DInput as “firmware update mode” and **won’t open the
app until you switch to standard/XInput**. That’s expected — capture the Save
**after** that switch (XInput `045e:028e` is fine).

```bash
sudo ./tools/capture-ss-usb.sh
# VM: accept standard/XInput → enter app → remap → Save
# then Enter on the host
```

Output: `captures/ss-remap-save.pcap`

## Guest commands without SSH

QEMU guest agent is already working:

```bash
python3 tools/win_guest.py whoami
python3 tools/win_guest.py --ps "Get-Process | Select -First 5"
```

## Optional: OpenSSH into the guest

```bash
./tools/win-setup-ssh.sh   # installs OpenSSH.Server + project key → Host win10
ssh win10 "whoami"         # → DESKTOP-…\jochem
```

Already configured on this machine: `Host win10` → `192.168.122.89` as user
`jochem` with `tools/win10_agent_ed25519` (gitignored).

Shared folder: host `~/Downloads` → virtiofs in the guest. Prefer capture
outputs under the git `captures/` tree on the host.
