# Local media source and execution receipts

Adds bounded local video/audio selections and per-execution input/output receipts to the existing download queue. Migration 0018 preserves all legacy direct-download fields, files and history; old rows acquire no invented execution history. Source digests exclude their own derived hash.

Backup, restore and offline integrity verify source ownership, copied inputs and final output receipts. Metadata-only capacity accounting shares existing limits and does not read source/receipt contents. Restart marks current running work interrupted without replay. Local creation and mux execution are not implemented here; their API entry remains unavailable.

Validation: two supported Python versions each passed 499 related tests and the final 61 source tests (overlapping counts, no skips). All 50 frozen application modules matched source. Source and frozen receipt/backup/restore CLI checks each passed 14, including corrupt-output rejection; API compatibility each passed 85. Receipt fixtures use synthetic bytes and metadata, not a real native mux result.

Retained failures: two initial fixture placeholder mismatches were corrected without weakening migration assertions. Nine Windows link-fixture permission failures were rerun successfully with the same assertions. A migration-failure injection verified rollback and backup retention.

Current-head CI must be checked separately. Review is deferred and manual testing cancelled under user instructions. The next backend task adds real controlled dual-track mux, cancellation and failure recovery; desktop UI, station extraction/downloads, fragmented formats and release readiness remain separate. No merge or release is requested.
