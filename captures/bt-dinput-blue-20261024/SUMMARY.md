# BT blue LED = DInput (native Flydigi)

- BlueZ: Flydigi VADER4P  A4:C1:38:10:33:34
- HID: 0005:D7D7:0041  driver=hid-generic
- Report: standard Game Pad id 0x01 (not USB 04 FE V1)
- GATT extras: Nordic UART + vendor 00010203-… (config path TBD)
- Kernel creates incomplete/noisy input node; flydigi-vader4d bridges via evdev→uinput
