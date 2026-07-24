"""PII scanner â€” backward-compatibility shim.

The PII detection implementation has moved to the ``etlpipe-governance``
sub-package.  This module re-exports everything from there so that all
existing code continues to work unchanged:

    from etlpipe._pii import scan_pii, PIIWarning        # still works
    from etlpipe import scan_pii                          # still works
    from etlpipe_governance import scan_pii, mask_pii    # new canonical home

.. deprecated::
    Import from ``etlpipe_governance`` directly for access to the full
    feature set, including :func:`etlpipe_governance.pii.mask_pii`.
    The shim re-exports will be removed in etlpipe 3.0.
"""

from __future__ import annotations

# Re-export everything the original module exposed, sourced from the
# governance sub-package (single source of truth).
from etlpipe_governance.pii import (
    _DEFAULT_PATTERNS,
    PIIWarning,
    scan_pii,
)

__all__ = ["scan_pii", "PIIWarning", "_DEFAULT_PATTERNS"]
