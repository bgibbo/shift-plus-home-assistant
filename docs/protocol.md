# Synchronization protocol

Protocol version 1 is unchanged for Shift + 5.1.0 and remains compatible with Android build 71.

Android sends replicated `active_configuration`, `annual_leave` and `overtime` records with vector versions and operation IDs. Home Assistant stores the replica, resolves deterministic conflicts, returns changes after the Android cursor and recalculates entities locally.

Android initiates every transport exchange. Home Assistant's Refresh schedule
control performs no network push. Journal records are pruned after Android
returns the newer server cursor on a later request. HA-originated and total
journal acknowledgement counts are exposed separately.

Concurrent vector versions remain available for explicit, individual
resolution. Resolving one conflict merges both vectors, writes one new
HA-originated canonical operation and uses the existing protocol to deliver it.

The active configuration contains roster and unit identifiers plus supported schedule settings. Android does not send Current Shift, Next Shift or book-on/off values; Home Assistant derives them from the synchronized inputs and bundled roster definitions.

Pairing QR fields, X25519/HKDF parameters, HMAC request format, endpoint paths and entitlement renewal contract remain unchanged. No backend or Android protocol change is required for 5.1.0.
