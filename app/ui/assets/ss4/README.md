# Space Station 4 F4 assets

Source: Flydigi Space Station **4.2.2.3** (`vendor/spacestation-4.2.2.3/app/resources/app.asar`).

| File | Origin |
|------|--------|
| `device_config_f4.json` | `device_config_f4-*.js` |
| `device_wireframe_f4.svg` | `device_wireframe_f4-*.js` (paths extracted) |
| `default_product_f4.png` | `default_product-f4*.png` (card art only) |

Hotspots are absolute CSS px on **`device_wireframe_f4.svg`** (viewBox **508×421**) —
the same pairing Space Station uses (`DeviceWireframe` + `supported_keys`). Do
**not** place them on `default_product_f4.png` (different framing).

Numeric `id` values match Space Station controller key ids (also used in onboard
key map slots for 0–31).
