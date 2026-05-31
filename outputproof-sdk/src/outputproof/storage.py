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
Local verification audit storage.

The open-source core stores newline-delimited JSON locally. This keeps the SDK
self-hostable and easy to inspect while leaving shared sync and governance
workflows to commercial/team deployments.
"""

import json
from pathlib import Path
from typing import Any, Optional, Union

from outputproof.models import VerificationResult

DEFAULT_STORAGE_PATH = Path.home() / ".outputproof" / "verifications.jsonl"


def append_verification(
    result: VerificationResult,
    path: Optional[Union[str, Path]] = None,
) -> Path:
    """Append a verification result to the local audit log."""
    storage_path = Path(path) if path else DEFAULT_STORAGE_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(storage_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(result.to_dict(), sort_keys=True) + "\n")
    return storage_path


def load_verifications(
    path: Optional[Union[str, Path]] = None,
) -> list[dict[str, Any]]:
    """Load verification records from the local audit log."""
    storage_path = Path(path) if path else DEFAULT_STORAGE_PATH
    if not storage_path.exists():
        return []

    records = []
    with open(storage_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_verification(
    result_id: str,
    path: Optional[Union[str, Path]] = None,
) -> Optional[dict[str, Any]]:
    """Find a verification record by request/result id."""
    for record in load_verifications(path):
        if record.get("request_id") == result_id:
            return record
    return None
