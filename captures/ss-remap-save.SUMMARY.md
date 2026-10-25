# Space Station remap Save — host usbmon (2026-10-25)

File: `ss-remap-save.pcap` (LINKTYPE_USB_LINUX_MMAPPED, ~5.5 MiB)

## What happened

1. **DInput device** (`dev46`, report/EP 5, padded 32 B) — SS probes then forces XInput:
   - `05 EC` device info  
   - `05 11` / `05 F5 01` / `05 EB` / `05 FA` …  
   - **`05 ED`** = `getSwitchAndroid2XInput` ← the “leave firmware-update / go standard” click  

2. Re-enumerate → **XInput device** (`dev47`, EP 5).

3. XInput setup (`A5` framing, 15 B, trailing sum CRC):
   - `A5 10` GamePadInfo, `A5 11` DongleInfo, `A5 20` GetCurConfigId, …  
   - `A5 50 04` (cmd 80 / sub 4) several times  
   - `A5 A0` SpecifyConfigId / UUID-class  

4. **Remap Save** (three key slots, then flash commit):

| OUT | Meaning (`CommandDic`) |
|-----|------------------------|
| `A5 23 07 01 A0 …` | **StartFLashDataKMPC** (35) |
| `A5 24 FF 00 00 14 02 0F …` | **WriteDataKMPC** (36) — key `0x14` |
| `A5 23` + `A5 24 … 20 …` | same for key `0x20` |
| `A5 23` + `A5 24 … FE …` | same for key `0xFE` |
| **`A5 50 03 0C 97 …`** | **SaveFlashConfig** — cmd **80**, sub **3** |

So on Windows/XInput, SS does **not** stream the full DInput 234/840 B blob for a UI remap. It uses the short **KMPC** start/write packets, then the same **80/3 SaveFlash** we already use (only with `A5` XInput header instead of DInput `05`).

## Implication for Linux

- DInput path (our daemon): keep omit-last 234 + `05 50 03` SaveFlash if that still persists.  
- Optional later: port **StartFLashDataKMPC / WriteDataKMPC** for surgical key updates (what SS used here).  
- SS “firmware update mode” gate on this VM is literally **`05 ED` → XInput** before the app UI will open.
