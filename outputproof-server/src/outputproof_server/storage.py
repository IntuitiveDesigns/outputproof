# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""SQLite storage for the OutputProof dashboard server."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Optional, Union

from outputproof_server.time import parse_timestamp, utc_now


def default_database_path() -> Path:
    """Return the default local database path for the dashboard server."""
    configured = os.getenv("OUTPUTPROOF_SERVER_DB")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".outputproof" / "outputproof-server.db"


class VerificationStore:
    """SQLite-backed repository for verification history and dashboard stats."""

    def __init__(self, database_path: Optional[Union[str, Path]] = None) -> None:
        self.database_path = database_path or default_database_path()
        self._lock = RLock()
        self._connection = self._connect()
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS verifications (
                    request_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_verifications_timestamp
                    ON verifications(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_verifications_agent
                    ON verifications(agent_id);
                CREATE INDEX IF NOT EXISTS idx_verifications_verdict
                    ON verifications(verdict);
                """
            )

    def add_verification(self, result: dict[str, Any]) -> dict[str, Any]:
        """Store or replace a verification result."""
        normalized = dict(result)
        normalized.setdefault("agent_id", "unknown")
        normalized.setdefault("assertion_results", [])
        normalized.setdefault("timestamp", utc_now().isoformat())
        normalized["timestamp"] = parse_timestamp(normalized["timestamp"]).isoformat()

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO verifications
                    (request_id, agent_id, verdict, confidence_score, timestamp, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["request_id"],
                    normalized["agent_id"],
                    normalized["verdict"],
                    float(normalized["confidence_score"]),
                    normalized["timestamp"],
                    json.dumps(normalized, sort_keys=True),
                ),
            )
        return normalized

    def list_verifications(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_id: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List verification results and the total count before pagination."""
        clauses = []
        params: list[Any] = []
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if verdict:
            clauses.append("verdict = ?")
            params.append(verdict)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total_row = self._connection.execute(
                f"SELECT COUNT(*) AS total FROM verifications {where}",
                params,
            ).fetchone()
            rows = self._connection.execute(
                f"""
                SELECT payload FROM verifications
                {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        return [json.loads(row["payload"]) for row in rows], int(total_row["total"])

    def get_verification(self, request_id: str) -> Optional[dict[str, Any]]:
        """Fetch one verification result by request id."""
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM verifications WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def recent_verifications(self, days: int) -> list[dict[str, Any]]:
        """Return verifications within the requested lookback window."""
        cutoff = utc_now() - timedelta(days=days)
        records, _ = self.list_verifications(limit=10000)
        return [
            record
            for record in records
            if parse_timestamp(record["timestamp"]) >= cutoff
        ]

    def list_failures(self, days: int, limit: int) -> list[dict[str, Any]]:
        """Return recent failed or partial verification records."""
        failures = [
            record
            for record in self.recent_verifications(days)
            if record.get("verdict") in ("FAIL", "PARTIAL")
        ]
        failures.sort(key=lambda record: record["timestamp"], reverse=True)
        return failures[:limit]

    def list_agent_stats(self) -> list[dict[str, Any]]:
        """Aggregate agent reliability stats from stored verifications."""
        records, _ = self.list_verifications(limit=10000)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped.setdefault(record.get("agent_id", "unknown"), []).append(record)

        stats = []
        for agent_id, agent_records in grouped.items():
            passed = sum(1 for record in agent_records if record.get("verdict") == "PASS")
            avg_confidence = sum(
                float(record.get("confidence_score", 0)) for record in agent_records
            ) / len(agent_records)
            stats.append(
                {
                    "agent_id": agent_id,
                    "total_verifications": len(agent_records),
                    "pass_rate": passed / len(agent_records),
                    "avg_confidence": round(avg_confidence, 3),
                    "last_verification": max(record["timestamp"] for record in agent_records),
                }
            )

        stats.sort(key=lambda item: item["last_verification"], reverse=True)
        return stats

    def get_agent_details(self, agent_id: str) -> Optional[dict[str, Any]]:
        """Return detailed stats and recent records for one agent."""
        records, total = self.list_verifications(limit=10000, agent_id=agent_id)
        if total == 0:
            return None

        passed = sum(1 for record in records if record.get("verdict") == "PASS")
        failures = [record for record in records if record.get("verdict") in ("FAIL", "PARTIAL")]
        failure_categories: dict[str, int] = {}
        for record in failures:
            for assertion in record.get("assertion_results", []):
                if not assertion.get("passed", True):
                    category = assertion.get("assertion_type", "unknown")
                    failure_categories[category] = failure_categories.get(category, 0) + 1

        integration_type = next(
            (
                record.get("integration_type")
                for record in records
                if record.get("integration_type")
            ),
            "unknown",
        )

        return {
            "profile": {
                "agent_id": agent_id,
                "integration_type": integration_type,
                "pass_rate_7d": passed / total,
                "pass_rate_30d": passed / total,
                "total_verifications": total,
            },
            "failure_categories": failure_categories,
            "recent_verifications": records[:10],
        }

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._connection.close()
