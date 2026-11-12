# Documentation image checklist

`shift-plus-icon.png` is the approved Shift + Android product icon. No other branding or promotional asset is currently approved for this repository.

Do not add AI-generated, mock, recreated, or modified application screenshots. The developer will supply official Play promotional artwork and genuine Android/Home Assistant captures for review before they are used.

## Required genuine screenshots

Capture on a real test installation with fictional or sanitised data. PNG is preferred. Crop to the relevant UI, use at least 1440 pixels wide for desktop screenshots and 1080 pixels wide for phone screenshots, and retain source captures for review.

| Filename | Recommended size | Capture and intended use |
|---|---:|---|
| `hacs-shift-plus-install.png` | 1440 × 900 | HACS Integration page for Shift +; installation guide |
| `add-integration-shift-plus.png` | 1440 × 900 | Settings → Devices & services → Add integration search; installation guide |
| `android-pairing-shift-plus.png` | 1080 × 1920 | Android pairing flow with all QR/private data removed; installation guide |
| `shift-plus-initial-sync.png` | 1440 × 900 | Completed initial sync/device page with safe data; installation guide |
| `shift-plus-entities.png` | 1440 × 900 | Populated Home Assistant entity list; installation guide/entity reference |
| `shift-plus-roster-card.png` | 1440 × 900 | Monthly card with fictional duties, leave and overtime; README/dashboard guide |
| `shift-plus-card-editor.png` | 1440 × 900 | Manual-card editor and safe YAML; installation guide |
| `shift-plus-card-presentation.png` | 1440 × 900 | Card showing documented font/layout settings; dashboard guide |
| `shift-plus-play-promo.png` | supplied original | Approved unmodified Google Play artwork; README only after approval |

## Review and sanitization

Before committing an image, inspect both visible pixels and metadata:

- Use fictional roster, leave, overtime, people, location, and organisation data.
- Remove URLs, IP addresses, device IDs, unique entity IDs, email addresses, and diagnostic values.
- Remove all QR codes, pairing payloads, tokens, credentials, purchase data, and private notes.
- Do not crop in a way that implies a mock or illustration is a live UI.
- Confirm every image is genuine; label any illustration as an illustration.
- Remove EXIF and metadata after full-resolution review.

When approved, place images in this directory and reference them only where the documentation accurately describes their content.
