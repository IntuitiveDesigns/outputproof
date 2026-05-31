# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""Time helpers shared by the OutputProof server."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    """Parse stored timestamps and treat legacy naive values as UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
