# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""
OutputProof source-available dashboard server package.

The core SDK remains Apache 2.0. This package contains the server/dashboard
surface that protects the commercial lane under BSL 1.1.
"""

from outputproof_server.app import create_app

__version__ = "1.0.0"
__license__ = "BUSL-1.1"

__all__ = ["__license__", "__version__", "create_app"]
