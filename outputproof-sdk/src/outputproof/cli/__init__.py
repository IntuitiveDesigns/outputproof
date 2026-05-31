# Copyright 2026 StreamKernel LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
CLI module for OutputProof.

This module provides the command-line interface for OutputProof, allowing
users to run verifications, view reports, and manage policies from the terminal.
"""

__all__ = ["cli"]


def __getattr__(name: str):
    """Load the Click entry point lazily for `python -m outputproof.cli.main`."""
    if name == "cli":
        from outputproof.cli.main import cli

        return cli
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
