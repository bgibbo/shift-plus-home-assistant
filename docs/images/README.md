# Public image and screenshot checklist

`shift-plus-icon.png` is the official Shift + Android product icon.

The original Play Store feature graphic was not present in the established
local Android project during the documentation audit. Do not recreate,
download or recompress it for this repository; add the original source asset
only if it becomes available and passes the privacy checks below.

## Genuine Home Assistant screenshots still needed

Capture these from a real, fully paired test installation:

| Filename | Capture |
|---|---|
| `hacs-shift-plus.png` | Shift + repository page in HACS, showing the released version |
| `add-integration-shift-plus.png` | Home Assistant Add integration search result for Shift + |
| `shift-plus-device.png` | Finished Shift + device page with the five released entities |
| `home-assistant-dashboard.png` | Built-in-card dashboard example |
| `home-assistant-roster-card.png` | Custom Shift + monthly roster card |

For the pairing journey, capture the Home Assistant notification layout only
after the QR image has been completely removed or replaced with a clearly
labelled solid placeholder. Never publish a live or expired QR because its
payload contains pairing information.

## Sanitization requirements

Before adding any screenshot:

- use fictional roster, leave and overtime data;
- remove names, email addresses and device identifiers;
- remove Home Assistant URLs, IP addresses and location names;
- remove private entity IDs and installation-specific identifiers;
- remove QR codes, tokens, credentials and diagnostic values;
- remove organisation, Garda and work information;
- inspect embedded image metadata as well as visible pixels.

Keep screenshots tightly cropped around the relevant Home Assistant interface.
Use PNG without additional recompression and verify the final image at full
resolution before committing it.
