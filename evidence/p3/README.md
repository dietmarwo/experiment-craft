# P3 evidence: explicit SSH placement and reconciliation

The source revisions are in [the baseline lock](../../baseline-lock.json); the [implementation log](../../implementation-log.md#p3--explicit-ssh-placement-and-reconciliation) describes the behavior and failure ledger.

The baseline uses Rust 1.88.0 for builds/tests and stable 1.99.1 for lints/docs. Schema and real-worker requirements are enabled. Sources are fresh checkouts; compiled dependency caches are reused. Exact unpublished source objects are exposed behind the canonical URLs by child-scoped local mirrors. No global Git configuration or public branch is changed.

`baseline/` contains the accepted coordinated run: commands, status, raw test output, toolchains, executable hashes and retained smoke journals/results. Copied staged executables and repetitive per-call dumps are omitted. `compatibility/` records both the old pinned SDK and the checkout SDK before moving worker pins. `extras/` records each tutorial/example, locked pin validation and real legacy execution. `before/` records the merged GitHub baseline and its failures/retry. `failures/` retains initial implementation/build failures; a later pass does not change an earlier status.

The 13 remote fixture tests use the actual Rust helper with named simulated SSH and service-manager commands. The four real SSH tests use the actual OpenSSH client (authentication, pinned host keys, encryption, binary streams and a deliberate disconnect) connected to a disposable AsyncSSH endpoint. They run real command processes and all three real Rust workers. **The service manager in both suites is simulated.** Those tests demonstrate transport/dispatch/reconciliation behavior and are not evidence for actual systemd, logout/reboot persistence, cgroup containment, distinct physical hosts or home hardware. New remote dispatch requires a responding user manager plus Linger=yes and has no foreground/nohup fallback. Actual positive backend acceptance remains RT-07.

Historical logs retain absolute scratch paths and elapsed times. They are observations of this run, not portable paths or timing claims. Numerical tolerances and mathematical solver code are unchanged.
