# OutputProof Server

Source-available dashboard server and team API for OutputProof.

This package contains the monetizable server/dashboard surface described in the
OutputProof product requirements:

- local and team dashboard API
- verification history views
- agent reliability scorecards
- failure pattern analysis foundations
- SQLite-backed local persistence with no external database required
- future policy engine, team aggregation, and cloud sync hooks

The core SDK, assertion engine, LLM-as-judge module, CLI, and MCP integration
remain Apache 2.0 in `outputproof`.

## Where Dashboard Data Comes From

The dashboard shows verification records stored by `outputproof-server`.
Records are created through the server API:

```text
POST /api/verifications
```

In normal local use, the CLI sends those records when `OUTPUTPROOF_SERVER_URL`
points at the running server. In production/team use, CI jobs, agent runners,
MCP integrations, or application code send the same `VerificationResult` JSON
to the API.

The server does not scan your workspace and does not automatically import the
SDK local history file at `~/.outputproof/verifications.jsonl`; that local file
is the Apache SDK audit log. The BSL server dashboard has its own SQLite
database, defaulting to `~/.outputproof/outputproof-server.db`.

## Usage

Install the Apache SDK first, then install this server package from the sibling
directory:

```powershell
# From C:\workspace\ai-agent-output-verification
cd outputproof-sdk
python -m pip install -e .

cd ..\outputproof-server
python -m pip install -e .
```

Run the dashboard server:

```powershell
python -m outputproof_server.cli --port 8080
# Then open http://127.0.0.1:8080

# Optional: choose a specific SQLite file
python -m outputproof_server.cli --database ~/.outputproof/outputproof-server.db
```

If PowerShell says `outputproof-server` is not recognized, keep using the
`python -m outputproof_server.cli` form above.

The default database path is `~/.outputproof/outputproof-server.db`. You can
also set `OUTPUTPROOF_SERVER_DB`.

## See The Dashboard Populate

The dashboard reads from the server API and SQLite database. To create a real
dashboard record from the SDK, use this copy/paste check.

In one PowerShell window:

```powershell
cd C:\workspace\ai-agent-output-verification\outputproof-server
python -m outputproof_server.cli --port 8080
```

Open `http://127.0.0.1:8080`. An empty dashboard means the server is running but
no verification records have been written yet.

In a second PowerShell window:

```powershell
cd C:\workspace\ai-agent-output-verification\outputproof-sdk

@'
assertions:
  - type: output_matches
    pattern: authenticated
'@ | Set-Content demo-assertions.yaml

$env:OUTPUTPROOF_SERVER_URL = "http://127.0.0.1:8080"
python -m outputproof.cli.main verify --agent-id demo-agent --prompt "Create auth" --output "authenticated" -a demo-assertions.yaml
```

Refresh `http://127.0.0.1:8080`; the summary cards, recent verifications table,
and agent reliability table should update.

Expected dashboard change:

```text
Total Verifications: 1
Pass Rate: 100%
Recent Verifications: demo-agent / PASS
Agent Reliability: demo-agent
```

You can also insert a dashboard record directly through the API:

```powershell
$body = @{
  request_id = "manual-demo-1"
  agent_id = "demo-agent"
  verdict = "PASS"
  confidence_score = 1.0
  assertion_results = @()
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8080/api/verifications" `
  -ContentType "application/json" `
  -Body $body
```

## License

`outputproof-server` is licensed under the Business Source License 1.1. It converts
to Apache License 2.0 on the Change Date listed in [LICENSE](LICENSE).

The Additional Use Grant allows internal self-hosted production use for small
teams while requiring a commercial license for hosted service, resale, OEM,
external redistribution, team governance, SSO, SLA, audit export, and cloud sync
offerings.
