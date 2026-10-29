# HTI v0.3 Release Status

## Current production candidate

`historical-theological-intelligence-v0.3-native-authoring-transaction-candidate.zip`

- Bytes: `1,390,380`
- SHA-256: `283ee82bb5a052e0f6eb51f5341f4621395e4a8cd69d0a15ded28ce0c3259085`
- Regular ZIP entries: `138`
- Internal `SHA256SUMS.txt`: `137/137 PASS`
- ZIP CRC: `PASS`
- Duplicate paths: `0`
- Unsafe paths: `0`
- Symlinks: `0`
- Clean extracted tree equals packaged source tree byte-for-byte: `PASS`
- Deterministic rebuild: `BYTE-IDENTICAL PASS`

## Qualification state

The native-authoring transaction candidate passed its bounded local qualification:

- inherited qualification: `63/63 PASS`
- negative transaction gates: `8/8 PASS`
- shipped validator: `PASS`
- clean ZIP revalidation: `PASS`
- pre-live gate: `PASS`

This status does **not** claim a formal HTI v0.3 release.

The later final Claude acceptance automation package is a validation campaign package, not the production Skill. Campaign completion and production release authorization remain separate decisions.

## Repository publication rule

The production candidate is preserved exactly under `dist/`. Its source tree is unpacked into `skill/historical-theological-intelligence/` only after the repository workflow verifies the outer archive SHA-256 and the complete internal checksum manifest.

Development handoffs, retained Work state, evaluator ground truth, live-validation runtime state, and author-specific regression material are excluded from the production source tree.
