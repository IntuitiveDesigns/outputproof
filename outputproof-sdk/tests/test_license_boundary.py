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

"""Tests for the Apache SDK / BSL server license boundary."""

from pathlib import Path


SDK_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SDK_ROOT.parent
SERVER_ROOT = WORKSPACE_ROOT / "outputproof-server"


def test_sdk_package_does_not_ship_server_implementation():
    """The Apache SDK package should not contain the BSL dashboard server."""
    assert not (SDK_ROOT / "src" / "outputproof" / "server").exists()


def test_sdk_metadata_stays_apache_only():
    """The SDK package metadata should remain Apache 2.0."""
    pyproject = (SDK_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = {text = "Apache-2.0"}' in pyproject
    assert '"fastapi>=0.109.0"' not in pyproject
    assert '"uvicorn>=0.27.0"' not in pyproject
    assert '"aiosqlite' not in pyproject
    assert 'name = "outputproof"' in pyproject
    assert '"outputproof-server>=1.0.0"' in pyproject


def test_commercial_docs_describe_bsl_server_boundary():
    commercial = (SDK_ROOT / "COMMERCIAL.md").read_text(encoding="utf-8")
    history = (SDK_ROOT / "LICENSE-HISTORY.md").read_text(encoding="utf-8")

    assert "`outputproof` is Apache 2.0" in commercial
    assert "`outputproof-server` is BSL 1.1" in commercial
    assert "Business Source License 1.1" in history


def test_server_package_uses_bsl_license():
    license_text = (SERVER_ROOT / "LICENSE").read_text(encoding="utf-8")
    app_source = (
        SERVER_ROOT / "src" / "outputproof_server" / "app.py"
    ).read_text(encoding="utf-8")
    storage_source = (
        SERVER_ROOT / "src" / "outputproof_server" / "storage.py"
    ).read_text(encoding="utf-8")

    assert "Business Source License 1.1" in license_text
    assert "Licensor: StreamKernel LLC" in license_text
    assert "internal self-hosted use by a single organization" in license_text
    assert "Change License: Apache License, Version 2.0" in license_text
    assert "SPDX-License-Identifier: BUSL-1.1" in app_source
    assert "SPDX-License-Identifier: BUSL-1.1" in storage_source
