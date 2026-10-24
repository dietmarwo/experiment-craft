# Historical session drivers

These are source snapshots for the recorded argv/environment in the logs.
They use the original iteration workspace layout and absolute paths and
are not installed project tools. For portable reproduction use delivery.py
from the patch ZIP for the baseline, and optimization-jobs' existing
.github/workflows/ci.yml mixed-node steps for pinned/checkout SDK checks.
The baseline tool itself writes the authoritative source, binary, toolchain
and per-step summaries; the outer driver only records command execution.
