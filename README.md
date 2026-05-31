# OutputProof

[![CI](https://github.com/IntuitiveDesigns/outputproof/actions/workflows/ci.yml/badge.svg)](https://github.com/IntuitiveDesigns/outputproof/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/core-Apache%202.0-blue.svg)](outputproof-sdk/LICENSE)
[![Server License: BSL 1.1](https://img.shields.io/badge/server-BSL%201.1-orange.svg)](outputproof-server/LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/IntuitiveDesigns/outputproof?include_prereleases&label=release)](https://github.com/IntuitiveDesigns/outputproof/releases)
[![GitHub stars](https://img.shields.io/github/stars/IntuitiveDesigns/outputproof?style=social)](https://github.com/IntuitiveDesigns/outputproof/stargazers)
[![GitHub watchers](https://img.shields.io/github/watchers/IntuitiveDesigns/outputproof?style=social)](https://github.com/IntuitiveDesigns/outputproof/watchers)
[![GitHub downloads](https://img.shields.io/github/downloads/IntuitiveDesigns/outputproof/total?label=downloads)](https://github.com/IntuitiveDesigns/outputproof/releases)

[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-dashboard-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-models-E92063)](https://docs.pydantic.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-local%20history-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![LangChain](https://img.shields.io/badge/LangChain-integration-1C3C3C)](https://www.langchain.com/)
[![MCP](https://img.shields.io/badge/MCP-ready-6B46C1)](https://modelcontextprotocol.io/)

**AI Agent Output Verification Platform** — infrastructure for trusting AI work product.

OutputProof is a verification layer that sits between AI agents and downstream
consumers. It asserts, scores, and logs output correctness before generated
work is trusted or acted upon.

## Packages

| Package | License | Description |
|---------|---------|-------------|
| [outputproof-sdk](./outputproof-sdk) | Apache 2.0 | Core SDK: assertion engine, LLM-as-judge, CLI, MCP/LangChain integrations |
| [outputproof-server](./outputproof-server) | BSL 1.1 | Dashboard server: verification history, SQLite storage, agent reliability scoring |

## Install From Source

OutputProof is in pre-release development and is not published to PyPI yet.
Install both packages from this repository:

```powershell
git clone https://github.com/IntuitiveDesigns/outputproof.git
cd outputproof

python -m pip install -e .\outputproof-sdk
python -m pip install -e .\outputproof-server
```

## Quick Start

Run a local verification:

```powershell
cd outputproof-sdk

@'
assertions:
  - type: output_matches
    pattern: authenticated
'@ | Set-Content demo-assertions.yaml

python -m outputproof.cli.main verify `
  --agent-id demo-agent `
  --prompt "Create auth" `
  --output "authenticated" `
  -a demo-assertions.yaml
```

Populate the dashboard:

```powershell
# Terminal 1
cd outputproof-server
python -m outputproof_server.cli --port 8080

# Terminal 2
cd outputproof-sdk

@'
assertions:
  - type: output_matches
    pattern: authenticated
'@ | Set-Content demo-assertions.yaml

$env:OUTPUTPROOF_SERVER_URL = "http://127.0.0.1:8080"
python -m outputproof.cli.main verify --agent-id demo-agent --prompt "Create auth" --output "authenticated" -a demo-assertions.yaml
```

Open `http://127.0.0.1:8080`. You should see `demo-agent`, a `PASS` verdict,
and the dashboard counters update.

## Python SDK

```python
from outputproof import verify, assertions as a


@verify(
    assertions=[
        a.output_matches("authenticated"),
        a.function_present("authenticate_user"),
    ],
    retry_on_fail=False,
)
async def generate_auth_module(prompt: str) -> str:
    return """
def authenticate_user(username: str, password: str) -> str:
    return "authenticated"
"""
```

## Documentation

- [SDK documentation](./outputproof-sdk/README.md)
- [Dashboard server documentation](./outputproof-server/README.md)
- [Commercial boundary](./outputproof-sdk/COMMERCIAL.md)

## Search Keywords

AI agent verification, LLM output validation, LLM-as-judge, agent reliability,
AI coding agent testing, LangChain verification, Claude Code MCP, Model Context
Protocol, FastAPI dashboard, policy engine, local-first AI governance, output
quality gates, Python SDK, CI guardrails.

For GitHub discovery, set repository topics in the GitHub About panel:

```text
ai, llm, ai-agents, agent-verification, llm-evaluation, llm-as-judge,
output-validation, langchain, mcp, fastapi, python, pytest, ai-governance,
developer-tools, ci-cd
```

## License

- Core SDK: [Apache 2.0](outputproof-sdk/LICENSE)
- Dashboard server: [Business Source License 1.1](outputproof-server/LICENSE)

---

*A product of [StreamKernel LLC](https://streamkernel.io) · [outputproof.io](https://outputproof.io) · <steven.lopez@streamkernel.io>*
