# OutputProof Commercial Model

OutputProof follows the StreamKernel-style mixed model: an Apache 2.0 SDK surface,
source-available server/dashboard components, and separately licensed hosted
commercial services.

## Clear Boundary

- `outputproof` is Apache 2.0. It contains the Python SDK, assertion engine,
  LLM-as-judge module, CLI, MCP integration scaffolding, local audit log helpers,
  and data models.
- `outputproof-server` is BSL 1.1. It contains the web dashboard, team API
  foundations, and future policy engine/cloud sync hooks.
- `outputproof-gha` should remain Apache 2.0 when added, because the GitHub Actions
  gate is an adoption channel.
- Customer-authored assertions, policies, integrations, and plugins remain
  customer-owned unless a separate written agreement says otherwise.

Apache 2.0 is intentionally retained for the SDK surface: developers and
enterprise legal teams can audit, vendor, and integrate the verifier without
trusting a black box. BSL 1.1 protects the hosted dashboard, team governance,
and cloud sync lane that funds the business.

## Commercial License Required For

- Offering OutputProof Server, OutputProof Dashboard, policy engine features, or a
  substantially similar hosted/managed verification dashboard to third parties.
- OEM embedding, resale, sublicensing, white-labeling, or external
  redistribution of BSL-governed server/dashboard components.
- Team governance features beyond the BSL Additional Use Grant, including SSO,
  audit export, enterprise policy management, cloud sync, Slack/email alerts,
  SLA, private builds, or dedicated onboarding.
- Commercial hosted infrastructure, support contracts, and negotiated enterprise
  deployment terms.

## No Commercial License Required

- Using the Apache 2.0 SDK, assertion engine, judge module, CLI, and MCP
  integration scaffolding.
- Writing custom assertions or internal verification policies against the SDK.
- Internal self-hosted use of `outputproof-server` within the BSL 1.1 Additional
  Use Grant.

## Common Commercial Packages

| Package | Fit |
|---|---|
| Individual Cloud | Hosted sync, longer history, alerts, and priority support. |
| Team Governance | Shared dashboard, team scorecards, policy engine, GHA gates, Slack alerts, SSO. |
| Enterprise | BYO storage, air-gapped deployment, SLA, audit export, and onboarding. |
| OEM / Managed Service | Embed or operate BSL server components for third-party customers. |

## Trademark Notice

"OutputProof" is used here as the product name for this project. Source licenses
cover source code only; they do not grant trademark rights, hosted service
access, commercial support, or enterprise contract rights.
