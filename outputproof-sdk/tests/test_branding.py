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

"""Tests for OutputProof public branding and compatibility imports."""

from pathlib import Path

import outputproof
from outputproof.judge import LLMJudge


SDK_ROOT = Path(__file__).resolve().parents[1]


def test_outputproof_public_import_alias():
    assert outputproof.__author__ == "StreamKernel LLC"
    assert outputproof.__email__ == "steven.lopez@streamkernel.io"
    assert outputproof.__license__ == "Apache-2.0"
    assert callable(outputproof.verify)
    assert LLMJudge.__name__ == "LLMJudge"


def test_readme_uses_outputproof_public_branding():
    readme = (SDK_ROOT / "README.md").read_text(encoding="utf-8")

    assert "OutputProof is not published to PyPI yet" in readme
    assert "python -m pip install -e ." in readme
    assert "https://outputproof.io/docs" in readme
    assert "steven.lopez@streamkernel.io" in readme
    assert "github.com/IntuitiveDesigns/outputproof" in readme
    assert "https://outputproof.io" in readme
