# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""
OutputProof Dashboard Server.

This module provides the FastAPI application for the verification dashboard,
including API routes and static file serving.
"""

from pathlib import Path
from typing import Any, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from outputproof_server.storage import VerificationStore
from outputproof_server.time import utc_now

SERVER_VERSION = "1.1.0"


class VerificationSummary(BaseModel):
    """Summary of verification statistics."""

    total: int
    passed: int
    failed: int
    partial: int
    avg_confidence: float


class AgentStats(BaseModel):
    """Statistics for an individual agent."""

    agent_id: str
    total_verifications: int
    pass_rate: float
    avg_confidence: float
    last_verification: Optional[str] = None


class ReliabilityLeaderboardRow(BaseModel):
    """Reliability ranking row for a team analytics dimension."""

    dimension: str
    name: str
    total_verifications: int
    passed: int
    failed: int
    partial: int
    pass_rate: float
    avg_confidence: float
    last_verification: Optional[str] = None


def create_app(
    debug: bool = False,
    allowed_origins: Optional[list[str]] = None,
    database_path: Optional[Union[str, Path]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        debug: Whether to enable debug mode.
        allowed_origins: Browser origins allowed to call the local API.
        database_path: SQLite database path. Defaults to OUTPUTPROOF_SERVER_DB
            or ~/.outputproof/outputproof-server.db.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="OutputProof Dashboard",
        description="AI Agent Output Verification Platform - Dashboard API",
        version=SERVER_VERSION,
        debug=debug,
    )

    # Configure CORS
    cors_origins = allowed_origins or [
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.store = VerificationStore(database_path)

    # Register routes
    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    """Register API routes.

    Args:
        app: The FastAPI application.
    """

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Send browser users to the dashboard UI."""
        return RedirectResponse(url="/dashboard")

    @app.get("/api/status")
    async def api_status() -> dict[str, str]:
        """Server status endpoint."""
        return {
            "name": "OutputProof Dashboard",
            "version": SERVER_VERSION,
            "status": "running",
        }

    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": utc_now().isoformat()}

    @app.get("/api/summary")
    async def get_summary(days: int = 7) -> VerificationSummary:
        """Get verification summary statistics."""
        recent = app.state.store.recent_verifications(days)

        if not recent:
            return VerificationSummary(
                total=0, passed=0, failed=0, partial=0, avg_confidence=0.0
            )

        passed = sum(1 for v in recent if v["verdict"] == "PASS")
        failed = sum(1 for v in recent if v["verdict"] == "FAIL")
        partial = sum(1 for v in recent if v["verdict"] == "PARTIAL")
        avg_confidence = sum(v["confidence_score"] for v in recent) / len(recent)

        return VerificationSummary(
            total=len(recent),
            passed=passed,
            failed=failed,
            partial=partial,
            avg_confidence=round(avg_confidence, 3),
        )

    @app.get("/api/verifications")
    async def list_verifications(
        limit: int = 50,
        offset: int = 0,
        agent_id: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> dict[str, Any]:
        """List verification results with pagination."""
        results, total = app.state.store.list_verifications(
            limit=limit,
            offset=offset,
            agent_id=agent_id,
            verdict=verdict,
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": results,
        }

    @app.get("/api/verifications/{verification_id}")
    async def get_verification(verification_id: str) -> dict[str, Any]:
        """Get a specific verification result."""
        result = app.state.store.get_verification(verification_id)
        if result is not None:
            return result

        raise HTTPException(status_code=404, detail="Verification not found")

    @app.post("/api/verifications")
    async def create_verification(result: dict[str, Any]) -> dict[str, str]:
        """Store a new verification result."""
        required_fields = ("request_id", "verdict", "confidence_score")
        missing = [field for field in required_fields if field not in result]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field(s): {', '.join(missing)}",
            )

        stored = app.state.store.add_verification(result)
        return {"status": "created", "id": stored["request_id"]}

    @app.get("/api/agents")
    async def list_agents() -> list[AgentStats]:
        """List all registered agents with their statistics."""
        return [
            AgentStats(**agent_stats)
            for agent_stats in app.state.store.list_agent_stats()
        ]

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str) -> dict[str, Any]:
        """Get detailed statistics for a specific agent."""
        agent = app.state.store.get_agent_details(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    @app.get("/api/leaderboard")
    async def get_reliability_leaderboard(
        dimension: str = "agent",
        days: int = 30,
        limit: int = 20,
        sort: str = "worst",
    ) -> list[ReliabilityLeaderboardRow]:
        """Rank agents, developers, or task types by verification reliability."""
        if dimension not in {"agent", "developer", "task_type"}:
            raise HTTPException(
                status_code=400,
                detail="dimension must be one of: agent, developer, task_type",
            )
        if sort not in {"worst", "best"}:
            raise HTTPException(status_code=400, detail="sort must be worst or best")

        rows = app.state.store.list_reliability_leaderboard(
            dimension=dimension,
            days=days,
            limit=limit,
            worst_first=sort == "worst",
        )
        return [ReliabilityLeaderboardRow(**row) for row in rows]

    @app.get("/api/failures")
    async def list_failures(
        limit: int = 20,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """List recent verification failures."""
        return app.state.store.list_failures(days=days, limit=limit)

    @app.get("/dashboard")
    async def dashboard() -> HTMLResponse:
        """Serve the dashboard HTML page."""
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>OutputProof Dashboard</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    background-color: #0a0a0a;
                    color: #e5e5e5;
                    min-height: 100vh;
                }
                .header {
                    background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                    padding: 2rem;
                    text-align: center;
                }
                .header h1 {
                    font-size: 2.5rem;
                    font-weight: 700;
                    margin-bottom: 0.5rem;
                }
                .header p {
                    opacity: 0.8;
                    font-size: 1.1rem;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 2rem;
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 1.5rem;
                    margin-bottom: 2rem;
                }
                .stat-card {
                    background: #1a1a1a;
                    border-radius: 12px;
                    padding: 1.5rem;
                    border: 1px solid #333;
                }
                .stat-card h3 {
                    font-size: 0.875rem;
                    color: #888;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: 0.5rem;
                }
                .stat-card .value {
                    font-size: 2rem;
                    font-weight: 700;
                }
                .stat-card .value.green { color: #22c55e; }
                .stat-card .value.red { color: #ef4444; }
                .stat-card .value.yellow { color: #eab308; }
                .stat-card .value.blue { color: #3b82f6; }
                .section {
                    background: #1a1a1a;
                    border-radius: 12px;
                    padding: 1.5rem;
                    margin-bottom: 1.5rem;
                    border: 1px solid #333;
                }
                .section h2 {
                    font-size: 1.25rem;
                    margin-bottom: 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid #333;
                }
                .leaderboard-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                    gap: 1.5rem;
                }
                .leaderboard-block h3 {
                    color: #cbd5e1;
                    font-size: 0.95rem;
                    font-weight: 600;
                    margin-bottom: 0.75rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .table-wrap {
                    overflow-x: auto;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    text-align: left;
                    padding: 0.75rem 1rem;
                    border-bottom: 1px solid #333;
                }
                th {
                    color: #888;
                    font-weight: 500;
                    font-size: 0.875rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .badge {
                    display: inline-block;
                    padding: 0.25rem 0.75rem;
                    border-radius: 9999px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }
                .badge-pass { background: #22c55e33; color: #22c55e; }
                .badge-fail { background: #ef444433; color: #ef4444; }
                .badge-partial { background: #eab30833; color: #eab308; }
                .footer {
                    text-align: center;
                    padding: 2rem;
                    color: #666;
                    font-size: 0.875rem;
                }
                .loading {
                    text-align: center;
                    padding: 3rem;
                    color: #666;
                }
                .empty-state {
                    text-align: center;
                    padding: 2rem;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>OutputProof Dashboard</h1>
                <p>AI Agent Output Verification Platform</p>
            </div>
            <div class="container">
                <div class="stats-grid" id="stats">
                    <div class="stat-card">
                        <h3>Total Verifications</h3>
                        <div class="value blue" id="total">-</div>
                    </div>
                    <div class="stat-card">
                        <h3>Pass Rate</h3>
                        <div class="value green" id="passRate">-</div>
                    </div>
                    <div class="stat-card">
                        <h3>Failed</h3>
                        <div class="value red" id="failed">-</div>
                    </div>
                    <div class="stat-card">
                        <h3>Avg Confidence</h3>
                        <div class="value yellow" id="confidence">-</div>
                    </div>
                </div>

                <div class="section">
                    <h2>Recent Verifications</h2>
                    <div id="verifications">
                        <div class="loading">Loading...</div>
                    </div>
                </div>

                <div class="section">
                    <h2>Agent Reliability</h2>
                    <div id="agents">
                        <div class="loading">Loading...</div>
                    </div>
                </div>

                <div class="section">
                    <h2>Team Reliability Leaderboard</h2>
                    <div class="leaderboard-grid">
                        <div class="leaderboard-block">
                            <h3>Worst Agents</h3>
                            <div id="leaderboardAgents">
                                <div class="loading">Loading...</div>
                            </div>
                        </div>
                        <div class="leaderboard-block">
                            <h3>Worst Developers</h3>
                            <div id="leaderboardDevelopers">
                                <div class="loading">Loading...</div>
                            </div>
                        </div>
                        <div class="leaderboard-block">
                            <h3>Worst Task Types</h3>
                            <div id="leaderboardTasks">
                                <div class="loading">Loading...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="footer">
                <p>OutputProof Server v1.1.0 | BSL 1.1 | StreamKernel LLC</p>
            </div>

            <script>
                function renderLeaderboard(rows, emptyLabel) {
                    if (rows.length === 0) {
                        return `<p class="empty-state">${emptyLabel}</p>`;
                    }
                    return `<div class="table-wrap">
                        <table>
                            <thead><tr><th>Name</th><th>Runs</th><th>Pass Rate</th><th>Non-Pass</th></tr></thead>
                            <tbody>
                                ${rows.map(row => `
                                    <tr>
                                        <td>${row.name}</td>
                                        <td>${row.total_verifications}</td>
                                        <td>${(row.pass_rate * 100).toFixed(0)}%</td>
                                        <td>${row.failed + row.partial}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>`;
                }

                async function loadData() {
                    try {
                        // Load summary
                        const summary = await fetch('/api/summary').then(r => r.json());
                        document.getElementById('total').textContent = summary.total;
                        document.getElementById('passRate').textContent = summary.total > 0 ? Math.round((summary.passed / summary.total) * 100) + '%' : '-';
                        document.getElementById('failed').textContent = summary.failed;
                        document.getElementById('confidence').textContent = summary.avg_confidence.toFixed(2);

                        // Load verifications
                        const verifications = await fetch('/api/verifications?limit=10').then(r => r.json());
                        const verifHTML = verifications.results.length > 0 ?
                            `<table>
                                <thead><tr><th>Time</th><th>Agent</th><th>Verdict</th><th>Confidence</th></tr></thead>
                                <tbody>
                                    ${verifications.results.map(v => `
                                        <tr>
                                            <td>${new Date(v.timestamp).toLocaleString()}</td>
                                            <td>${v.agent_id || 'unknown'}</td>
                                            <td><span class="badge badge-${v.verdict.toLowerCase()}">${v.verdict}</span></td>
                                            <td>${(v.confidence_score * 100).toFixed(0)}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>` : '<p style="text-align:center;padding:2rem;color:#666;">No verifications yet</p>';
                        document.getElementById('verifications').innerHTML = verifHTML;

                        // Load agents
                        const agents = await fetch('/api/agents').then(r => r.json());
                        const agentsHTML = agents.length > 0 ?
                            `<table>
                                <thead><tr><th>Agent</th><th>Verifications</th><th>Pass Rate</th><th>Avg Confidence</th></tr></thead>
                                <tbody>
                                    ${agents.map(a => `
                                        <tr>
                                            <td>${a.agent_id}</td>
                                            <td>${a.total_verifications}</td>
                                            <td>${(a.pass_rate * 100).toFixed(0)}%</td>
                                            <td>${(a.avg_confidence * 100).toFixed(0)}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>` : '<p style="text-align:center;padding:2rem;color:#666;">No agents registered</p>';
                        document.getElementById('agents').innerHTML = agentsHTML;

                        // Load team reliability leaderboards
                        const leaderboardConfigs = [
                            ['agent', 'leaderboardAgents', 'No agent reliability data yet'],
                            ['developer', 'leaderboardDevelopers', 'No developer reliability data yet'],
                            ['task_type', 'leaderboardTasks', 'No task type reliability data yet']
                        ];
                        await Promise.all(leaderboardConfigs.map(async ([dimension, elementId, emptyLabel]) => {
                            const rows = await fetch(`/api/leaderboard?dimension=${dimension}&days=30&limit=5&sort=worst`).then(r => r.json());
                            document.getElementById(elementId).innerHTML = renderLeaderboard(rows, emptyLabel);
                        }));
                    } catch (error) {
                        console.error('Error loading data:', error);
                    }
                }

                // Load data on page load
                loadData();
                // Refresh every 30 seconds
                setInterval(loadData, 30000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    @app.get("/dashboard/*{path:path}")
    async def dashboard_static(path: str) -> HTMLResponse:
        """Serve dashboard sub-pages."""
        return await dashboard()
