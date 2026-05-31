# OutputProof

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/IntuitiveDesigns/outputproof/actions/workflows/ci.yml/badge.svg)](https://github.com/IntuitiveDesigns/outputproof/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Package](https://img.shields.io/badge/package-outputproof-blue.svg)](https://github.com/IntuitiveDesigns/outputproof/tree/main/outputproof-sdk)
[![GitHub stars](https://img.shields.io/github/stars/IntuitiveDesigns/outputproof?style=social)](https://github.com/IntuitiveDesigns/outputproof/stargazers)
[![GitHub watchers](https://img.shields.io/github/watchers/IntuitiveDesigns/outputproof?style=social)](https://github.com/IntuitiveDesigns/outputproof/watchers)
[![GitHub downloads](https://img.shields.io/github/downloads/IntuitiveDesigns/outputproof/total?label=downloads)](https://github.com/IntuitiveDesigns/outputproof/releases)

**AI Agent Output Verification Platform** — Infrastructure for trusting AI work product.

## Overview

OutputProof is a developer-first verification layer that sits between AI agents and their downstream consumers — asserting, scoring, and logging output correctness before results are trusted or acted upon.

Modern AI coding agents and task automation agents suffer from a documented reliability problem: they optimize for appearing helpful over being correct. OutputProof solves this by providing:

- **Assertion-based verification** — Developer-defined rules to validate agent output
- **LLM-as-Judge scoring** — Semantic verification using configurable judge models
- **Retry orchestration** — Automatic decorator retry with corrective prompts on failure
- **Verification dashboard** — Separate BSL 1.1 server package for history and team analytics

## How OutputProof Is Used

OutputProof sits in the path where an AI agent produces work:

```text
AI agent output -> OutputProof SDK assertions/judge -> VerificationResult -> local pass/fail gate -> optional dashboard sync
```

Common usage patterns:

- **Local development** — Run `python -m outputproof.cli.main verify ...` against an agent output before accepting it.
- **CI or automation** — Run `python -m outputproof.cli.main github-gate` after an agent writes files; the command exits non-zero when verification fails.
- **Application code** — Wrap an agent function with `@outputproof.verify(...)` so generated output is checked before downstream code receives it.
- **Team visibility** — Run `outputproof-server` and set `OUTPUTPROOF_SERVER_URL` so CLI verification results are sent to the dashboard.

The dashboard is an aggregation surface. It does not inspect your project files
or automatically read the SDK local history file. It populates when a producer
sends verification results to the server API.

## Features

- 🔍 **Assertion Engine** — Structural, behavioral, semantic, and contract assertions
- 🤖 **LLM-as-Judge** — Configurable secondary scoring with any OpenAI-compatible endpoint
- 🔄 **Retry Orchestration** — Automatic decorator retry with corrective prompts
- 🧱 **GitHub Actions Gate** — PR-blocking verification with GitHub job summaries
- 📊 **Verification Dashboard** — Separate BSL 1.1 `outputproof-server` package
- 🔌 **Multiple Integrations** — Claude Code MCP and LangChain today; OpenAI Agents, Cursor, and REST proxy planned
- 🛡️ **Local-First** — Zero required cloud dependency for core verification
- 📝 **Structured Reports** — Pass/fail, confidence score, failure reasons, corrective hints

## Installation

OutputProof is not published to PyPI yet. Install it from this repository while
the project is in pre-release development.

```powershell
# From C:\workspace\ai-agent-output-verification
cd outputproof-sdk
python -m pip install -e .

# Optional: install the BSL dashboard server from the sibling package
cd ..\outputproof-server
python -m pip install -e .
```

The planned PyPI package names are `outputproof` and `outputproof-server`, but
those packages should not be installed from PyPI until the first public release
is published.

## Quick Start

### CLI Usage

The easiest way to get started is through the command-line interface. On
Windows PowerShell, use the `python -m ...` commands exactly as shown; the bare
`outputproof` executable may not be on `PATH` after a user install.

```powershell
# Run verification on agent output
python -m outputproof.cli.main verify --prompt "Create a function" --output "def add(a, b): return a + b"

# Run verification with YAML assertion rules
@'
assertions:
  - type: output_matches
    pattern: authenticated
'@ | Set-Content assertions.yaml

python -m outputproof.cli.main verify --prompt "Create auth" --output "authenticated" -a assertions.yaml

# Start the dashboard server
# Requires the separate outputproof-server package.
python -m outputproof.cli.main dashboard --port 8080
# Then open http://127.0.0.1:8080

# Optional: choose a SQLite history database
python -m outputproof.cli.main dashboard --database ~/.outputproof/outputproof-server.db

# View available commands
python -m outputproof.cli.main --help
```

If PowerShell says `outputproof` is not recognized, keep using the `python -m`
form above.

### GitHub Actions Gate

The `github-gate` command turns OutputProof into an enforcement step. It loads
YAML assertions, builds the verification output from changed PR files, writes a
GitHub job summary, and exits non-zero unless the verdict is `PASS`.

Add an assertion file:

```yaml
# .outputproof/github-gate.yaml
assertions:
  - type: command_succeeds
    command: python -m pytest -q
    timeout: 180
```

Then add a workflow step after checkout and install:

```yaml
- name: OutputProof GitHub Actions gate
  env:
    OUTPUTPROOF_AGENT_ID: ${{ github.actor }}
    OUTPUTPROOF_DEVELOPER_ID: ${{ github.actor }}
    OUTPUTPROOF_TASK_TYPE: code_generation
    OUTPUTPROOF_BASE_REF: origin/${{ github.base_ref || 'main' }}
  run: python -m outputproof.cli.main github-gate --assertions .outputproof/github-gate.yaml
```

Use `actions/checkout` with `fetch-depth: 0` so the gate can diff the PR against
the base branch. Set `OUTPUTPROOF_SERVER_URL` to also send CI results to the
dashboard and team leaderboard.

### See The Dashboard Populate

The CLI stores verification history locally by default. The dashboard reads from
`outputproof-server`, so you need to point the CLI at the running server.

If the dashboard is empty, that means no verification records have been sent to
the server yet. Use this copy/paste check to prove the full loop is working.

In one PowerShell window:

```powershell
cd C:\workspace\ai-agent-output-verification\outputproof-server
python -m outputproof_server.cli --port 8080
```

Open `http://127.0.0.1:8080`. The dashboard may show zero records at first.

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

Refresh `http://127.0.0.1:8080`. You should see the verification count,
pass rate, recent verification row, and `demo-agent` reliability entry update.

Behind the scenes, the CLI creates a `VerificationResult` and posts it to:

```text
POST http://127.0.0.1:8080/api/verifications
```

Expected dashboard change:

```text
Total Verifications: 1
Pass Rate: 100%
Recent Verifications: demo-agent / PASS
Agent Reliability: demo-agent
```

### Python SDK Usage

You can also use OutputProof as a Python library in your own code:

```python
# Save this as my_verification.py
import asyncio

from outputproof import verify, assertions as a


@verify(
    assertions=[
        a.file_exists("src/auth.py", within_output=True),
        a.function_present("authenticate_user"),
        a.contains_import("jwt"),
    ],
    assertion_mode="all",
    retry_on_fail=False,
)
async def generate_auth_module(prompt: str) -> str:
    return """
# File: src/auth.py
import jwt

def authenticate_user(username: str, password: str) -> str:
    return jwt.encode({"username": username}, "secret-key")
"""


async def main() -> None:
    output = await generate_auth_module("Create JWT auth")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
```

Then run your script:

```powershell
python my_verification.py
```

On verification failure, the SDK raises a `VerificationError` containing the full `VerificationResult` — which assertions failed, the judge's confidence score, retry history, and a corrective prompt ready for agent retry.

YAML assertion files can be either a top-level list or an `assertions:` mapping:

```yaml
assertions:
  - type: function_present
    function_name: authenticate_user
  - type: tests_pass
    test_command: pytest
    test_path: tests/test_auth.py
```

### Running Examples

The package includes example scripts in the `examples/` directory:

```powershell
cd outputproof-sdk
python examples/basic_verification.py
```

## Documentation

The docs site will live at [outputproof.io/docs](https://outputproof.io/docs).
Until the docs site is published, this README is the source of truth for setup
and local development.

Planned documentation sections:

- [Installation Guide](https://outputproof.io/docs/installation)
- [Assertion Reference](https://outputproof.io/docs/assertions)
- [LLM-as-Judge Configuration](https://outputproof.io/docs/judge)
- [Integration Guides](https://outputproof.io/docs/integrations)
- [Dashboard Setup](https://outputproof.io/docs/dashboard)
- [API Reference](https://outputproof.io/docs/api)

## Supported Integrations

| Integration | Status | Description |
|-------------|--------|-------------|
| Claude Code | 🧪 Beta | MCP protocol scaffolding and verification hooks |
| LangChain/LangGraph | 🧪 Beta | Drop-in callback handler |
| OpenAI Agents SDK | Planned | Output interceptor |
| Cursor | Planned | VS Code extension wrapper |
| Generic REST | Planned | Local HTTP proxy mode |

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Agent      │───▶│ OutputProof SDK  │───▶│   Downstream    │
│   (Claude,      │    │   - Assertions   │    │   Consumer      │
│    LangChain,   │    │   - Judge LLM    │    │                 │
│    etc.)        │    │   - Retry Logic  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ outputproof-server│
                       │ BSL dashboard    │
                       │ team API         │
                       └──────────────────┘
```

## Development

```powershell
# Navigate to the SDK directory (already in your workspace)
cd outputproof-sdk

# Install development dependencies
python -m pip install -e ".[dev]"

# Run tests
python -m pytest -o addopts= -p no:cacheprovider
```

## Project Structure

```
outputproof-sdk/
├── src/outputproof/
│   ├── __init__.py          # Main package entry point
│   ├── core.py              # Core verification logic
│   ├── models.py            # Data models
│   ├── assertions/          # Assertion engine
│   │   ├── __init__.py
│   │   ├── base.py          # Base assertion classes
│   │   ├── structural.py    # File/function existence checks
│   │   ├── behavioral.py    # Test execution assertions
│   │   └── semantic.py      # LLM-based semantic matching
│   ├── judge/               # LLM-as-Judge scorer
│   │   ├── __init__.py
│   │   ├── scorer.py        # Judge implementation
│   │   └── prompts.py       # Judge prompt templates
│   ├── integrations/        # Agent integrations
│   │   ├── __init__.py
│   │   ├── claude_code.py   # Claude Code MCP
│   │   └── langchain.py     # LangChain callback
│   └── cli/                 # Command-line interface
│       ├── __init__.py
│       └── main.py          # CLI entry point
├── tests/                   # Test suite
├── docs/                    # Documentation
├── examples/                # Example usage
├── pyproject.toml           # Project configuration
├── LICENSE                  # Apache 2.0 License
├── NOTICE                   # License boundary summary
├── LICENSE-HISTORY.md       # Release and package license boundary
└── COMMERCIAL.md            # Open-core monetization boundary
```

The dashboard server now lives in the sibling `outputproof-server` package under
BSL 1.1.

## Roadmap

- [x] Core SDK with assertion engine
- [x] Assertion composition: all, any, threshold, weighted
- [x] LLM-as-Judge scorer
- [x] CLI interface
- [x] Dashboard server split into BSL 1.1 `outputproof-server`
- [x] LangChain callback integration
- [x] GitHub Actions gate (v1.1)
- [x] Team reliability leaderboard (v1.1)
- [ ] Production Claude Code MCP server
- [ ] Policy engine (v1.1)

## Open Core and Commercial Features

OutputProof uses an open-core model. The SDK, assertion engine, LLM-as-judge
module, CLI, MCP integration scaffolding, and local verification workflows are
Apache 2.0 open source. The dashboard server, team API, policy engine, team
aggregation, and cloud sync surface are distributed separately as
`outputproof-server` under BSL 1.1. Paid plans are intended to add hosted
convenience and governance features: cloud dashboard sync, longer hosted
history, alerts, team aggregate scoring, GitHub Actions gates, SSO, audit
export, SLA, BYO storage support, and onboarding.

See [COMMERCIAL.md](COMMERCIAL.md) for the monetization boundary.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on:

- Code of Conduct
- Development setup
- Submitting pull requests
- Reporting issues

## License

Copyright 2026 StreamKernel LLC.

The `outputproof` package is licensed under the Apache License 2.0 — see the
[LICENSE](LICENSE) file for details. The server/dashboard package is licensed
separately under BSL 1.1; see [LICENSE-HISTORY.md](LICENSE-HISTORY.md) and
[COMMERCIAL.md](COMMERCIAL.md).

## Author

OutputProof is developed by **StreamKernel LLC**.

- GitHub: [IntuitiveDesigns/outputproof](https://github.com/IntuitiveDesigns/outputproof)
- Maintainer contact: <steven.lopez@streamkernel.io>

## Support

- 📧 Email: <steven.lopez@streamkernel.io>
- 💬 Discussions: [GitHub Discussions](https://github.com/IntuitiveDesigns/outputproof/discussions)
- 🐛 Issues: [GitHub Issues](https://github.com/IntuitiveDesigns/outputproof/issues)

---

*OutputProof — Infrastructure for trusting AI work product.*
