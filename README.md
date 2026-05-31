# OutputProof

**AI Agent Output Verification Platform** — Infrastructure for trusting AI work product.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](outputproof-sdk/LICENSE)
[![BSL](https://img.shields.io/badge/Server-BSL_1.1-orange.svg)](outputproof-server/LICENSE)

OutputProof is an open-source verification layer that sits between your AI agent and your codebase — asserting, scoring, and logging output correctness before results are trusted or acted upon.

## Packages

| Package | License | Description |
|---------|---------|-------------|
| [outputproof-sdk](./outputproof-sdk) | Apache 2.0 | Core SDK — assertion engine, LLM-as-judge, CLI, integrations |
| [outputproof-server](./outputproof-server) | BSL 1.1 | Dashboard server — verification history, agent reliability scoring |

## Quick Install

\\\ash
pip install outputproof
\\\

## Quick Start

\\\python
from outputproof import verify, assertions as a

@verify(
    assertions=[
        a.file_exists("src/auth.py"),
        a.function_present("authenticate_user"),
        a.tests_pass("pytest tests/test_auth.py"),
        a.semantic_match(intent="implement JWT auth with refresh tokens"),
    ],
    retry_on_fail=True,
    max_retries=2,
)
async def generate_auth_module(prompt: str):
    return await your_agent(prompt)
\\\

## Documentation

See [outputproof-sdk/README.md](./outputproof-sdk/README.md) for full documentation.

## License

- Core SDK: [Apache 2.0](outputproof-sdk/LICENSE)
- Dashboard server: [BSL 1.1](outputproof-server/LICENSE)

---

*A product of [StreamKernel LLC](https://streamkernel.io) · [outputproof.io](https://outputproof.io) · steven.lopez@streamkernel.io*
