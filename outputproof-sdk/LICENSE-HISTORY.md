# OutputProof License History

This file records the release history and package boundary for OutputProof's
mixed-license model.

## Initial Public SDK Releases

The `outputproof` package is Apache License 2.0. This includes the developer
SDK, assertion engine, LLM-as-judge module, CLI, MCP integration scaffolding,
local audit log helpers, and data models.

Recipients who obtain a release of `outputproof` under Apache 2.0 retain those
Apache 2.0 rights for that release. Those rights are not revoked retroactively.

## Server/Dashboard Boundary

The web dashboard, team API, policy engine, team aggregation, and cloud sync
surface are commercial differentiators. They are distributed separately as
`outputproof-server` under Business Source License 1.1.

The BSL-governed server package converts to Apache License 2.0 on the Change
Date specified in `outputproof-server/LICENSE`.

## Practical Meaning

- Build agent verification workflows against the SDK: allowed under Apache 2.0.
- Create custom assertions and policy files against the SDK: author-owned by
  default unless a separate written agreement says otherwise.
- Use the dashboard server internally within the BSL Additional Use Grant:
  allowed under BSL 1.1.
- Offer the dashboard/server/policy engine as a hosted service, managed service,
  OEM component, resale bundle, or external redistribution: requires a
  commercial license.

## Related Files

- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [COMMERCIAL.md](COMMERCIAL.md)
- [outputproof-server LICENSE](../outputproof-server/LICENSE)
