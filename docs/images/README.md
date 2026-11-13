# Documentation image checklist

`shift-plus-icon.png` is the approved Shift + Android product icon.
`shift-plus-promotional.png` is approved official promotional artwork linking to
[shiftplus.plus](https://www.shiftplus.plus/). It is not a Home Assistant
screenshot.

Do not add AI-generated, mock, recreated, or modified application screenshots. The developer will supply official Play promotional artwork and genuine Android/Home Assistant captures for review before they are used.

## Required genuine screenshots

Capture on a real test installation with fictional or sanitised data. PNG is preferred. Crop to the relevant UI, use at least 1440 pixels wide for desktop screenshots and 1080 pixels wide for phone screenshots, and retain source captures for review.

| Filename | Recommended size | Capture and intended use |
|---|---:|---|
| `marketplace-shift-plus-install.png` | 1440 × 900 | Home Assistant Marketplace page for Shift +; installation guide |
| `hacs-shift-plus-install.png` | 1440 × 900 | HACS Integration page for Shift +; older-installation guide |
| `shift-plus-home-assistant-configuration.png` | 365 × 244 | Genuine integration configuration controls; README |
| `shift-plus-home-assistant-entities-1.png` and `shift-plus-home-assistant-entities-2.png` | supplied captures | Genuine two-part entity-list capture; README |
| `shift-plus-home-assistant-roster-card.png` | 529 × 808 | Genuine monthly roster card; README/dashboard guide |
| `shift-plus-android-calendar.jpg` | 945 × 2048 | Genuine Android roster calendar; README |
| `android-pairing-shift-plus.png` | 1080 × 1920 | Android pairing flow with all QR/private data removed; installation guide |
| `shift-plus-initial-sync.png` | 1440 × 900 | Completed initial sync/device page with safe data; installation guide |
| `shift-plus-entities.png` | 1440 × 900 | Populated Home Assistant entity list; installation guide/entity reference |
| `shift-plus-roster-card.png` | 1440 × 900 | Optional wider monthly-card capture for a future documentation update |
| `shift-plus-card-editor.png` | 1440 × 900 | Manual-card editor and safe YAML; installation guide |
| `shift-plus-card-presentation.png` | 1440 × 900 | Card showing documented font/layout settings; dashboard guide |
| `shift-plus-promotional.png` | supplied original | Approved official promotional artwork; README |

## Review and sanitization

Before committing an image, inspect both visible pixels and metadata:

- Use fictional roster, leave, overtime, people, location, and organisation data.
- Remove URLs, IP addresses, device IDs, unique entity IDs, email addresses, and diagnostic values.
- Remove all QR codes, pairing payloads, tokens, credentials, purchase data, and private notes.
- Do not crop in a way that implies a mock or illustration is a live UI.
- Confirm every image is genuine; label any illustration as an illustration.
- Remove EXIF and metadata after full-resolution review.

When approved, place images in this directory and reference them only where the documentation accurately describes their content.
