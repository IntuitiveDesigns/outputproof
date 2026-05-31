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
OutputProof CLI - Command-line interface for AI agent output verification.

This module provides the main CLI entry point for OutputProof, including commands
for running verifications, viewing reports, managing policies, and starting
the dashboard server.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler

import outputproof
from outputproof.models import VerificationResult, VerificationVerdict
from outputproof.storage import append_verification, get_verification, load_verifications

console = Console()

# Configure logging with Rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def load_assertions_from_yaml(path: str) -> list:
    """Load assertion declarations from a YAML file."""
    import yaml

    from outputproof.assertions import assertion_from_config

    with open(path, "r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    if isinstance(raw_config, list):
        assertion_configs = raw_config
    elif isinstance(raw_config, dict):
        assertion_configs = raw_config.get("assertions", [])
    else:
        raise click.ClickException("Assertion YAML must be a list or mapping.")

    if not isinstance(assertion_configs, list):
        raise click.ClickException("'assertions' must be a list.")

    return [assertion_from_config(config) for config in assertion_configs]


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    """OutputProof - AI Agent Output Verification Platform

    Infrastructure for trusting AI work product.

    \b
    Examples:
        outputproof verify --prompt "Create a function" --output "def func():..."
        outputproof report --id abc123
        outputproof dashboard --port 8080
        outputproof policy list
    """
    if version:
        console.print(f"[bold blue]OutputProof[/bold blue] v{outputproof.__version__}")
        console.print(f"Author: {outputproof.__author__}")
        console.print(f"License: {outputproof.__license__}")
        ctx.exit()

    if ctx.invoked_subcommand is None:
        console.print(Panel.fit(
            f"[bold blue]OutputProof[/bold blue] v{outputproof.__version__}\n"
            f"[dim]AI Agent Output Verification Platform[/dim]\n\n"
            f"Run [bold]outputproof --help[/bold] for available commands.",
            title="OutputProof",
            border_style="blue",
        ))


@cli.command()
@click.option("--prompt", required=True, help="The original prompt given to the agent.")
@click.option("--output", required=True, help="The output produced by the agent.")
@click.option("--agent-id", default="default", help="Agent identifier.")
@click.option("--assertions", "-a", multiple=True, help="Assertion config files (YAML).")
@click.option("--use-judge", is_flag=True, help="Use LLM-as-Judge for scoring.")
@click.option("--judge-model", default="claude-haiku-4-5", help="Judge model to use.")
@click.option("--output-json", is_flag=True, help="Output result as JSON.")
def verify(
    prompt: str,
    output: str,
    agent_id: str,
    assertions: tuple[str, ...],
    use_judge: bool,
    judge_model: str,
    output_json: bool,
) -> None:
    """Run verification on agent output.

    This command verifies agent output against specified assertions and
    optionally uses an LLM-as-Judge for semantic scoring.

    \b
    Examples:
        outputproof verify --prompt "Create auth" --output "def authenticate():..."
        outputproof verify --prompt "Create auth" --output "..." --use-judge
        outputproof verify --prompt "Create auth" --output "..." -a assertions.yaml
    """
    from outputproof.core import Verifier, VerificationError
    from outputproof.models import RetryConfig
    from outputproof.judge import JudgeConfig

    async def run_verification() -> None:
        # Load assertions from files if provided
        assertion_list = []
        for assertion_file in assertions:
            try:
                assertion_list.extend(load_assertions_from_yaml(assertion_file))
            except Exception as e:
                raise click.ClickException(f"Error loading {assertion_file}: {e}") from e

        # Configure judge if requested
        judge_config = None
        if use_judge:
            api_key = _load_judge_api_key(judge_model)
            use_local = judge_model.startswith("ollama/")
            model = judge_model.split("/", 1)[1] if use_local else judge_model
            if not use_local and not api_key:
                raise click.ClickException(
                    "No judge API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
                    "or use a local model name like 'ollama/llama3'."
                )

            judge_config = JudgeConfig(
                model=model,
                api_key=api_key,
                use_local=use_local,
            )

        # Create verifier
        verifier = Verifier(
            assertions=assertion_list,
            judge_config=judge_config,
            retry_config=RetryConfig(enabled=False),
        )

        # Run verification
        try:
            result = await verifier.verify(
                prompt=prompt,
                output=output,
                agent_id=agent_id,
            )

            if output_json:
                console.print(json.dumps(result.to_dict(), indent=2))
            else:
                _print_verification_result(result)
            _persist_verification(result, output_json)

            if not result.passed:
                ctx = click.get_current_context()
                ctx.exit(1)

        except VerificationError as e:
            if output_json:
                console.print(json.dumps(e.result.to_dict(), indent=2))
            else:
                console.print("[red bold]Verification Failed[/red bold]")
                _print_verification_result(e.result)
            _persist_verification(e.result, output_json)
            ctx = click.get_current_context()
            ctx.exit(1)

    asyncio.run(run_verification())


def _load_judge_api_key(model: str) -> Optional[str]:
    """Load a judge API key without inventing demo credentials."""
    if model.startswith("ollama/"):
        return None
    if model.startswith("claude"):
        key_file = Path.home() / ".anthropic" / "key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        return os.getenv("ANTHROPIC_API_KEY")
    return os.getenv("OPENAI_API_KEY")


def _persist_verification(result: VerificationResult, output_json: bool) -> None:
    """Store a verification locally and optionally sync it to the dashboard."""
    append_verification(result)
    synced = _sync_verification_to_server(result)
    if output_json:
        return

    if synced:
        console.print("[dim]Synced verification to OutputProof dashboard.[/dim]")
    elif os.getenv("OUTPUTPROOF_SERVER_URL", "").strip():
        console.print(
            "[yellow]Dashboard sync failed; check OUTPUTPROOF_SERVER_URL.[/yellow]"
        )


def _sync_verification_to_server(
    result: VerificationResult,
    server_url: Optional[str] = None,
) -> bool:
    """Best-effort sync of a local verification result to outputproof-server."""
    target = (server_url or os.getenv("OUTPUTPROOF_SERVER_URL", "")).strip()
    if not target:
        return False

    url = f"{target.rstrip('/')}/api/verifications"
    try:
        response = httpx.post(url, json=result.to_dict(), timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("Could not sync verification to %s: %s", url, exc)
        return False

    return True


@cli.command()
@click.option("--id", "result_id", required=True, help="Verification result ID.")
@click.option("--output-json", is_flag=True, help="Output result as JSON.")
def report(result_id: str, output_json: bool) -> None:
    """View a verification report.

    Retrieve and display details of a specific verification result.

    \b
    Examples:
        outputproof report --id abc123
        outputproof report --id abc123 --output-json
    """
    record = get_verification(result_id)
    if not record:
        raise click.ClickException(f"Verification not found: {result_id}")

    if output_json:
        console.print(json.dumps(record, indent=2))
        return

    _print_record(record)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=8080, help="Port to bind to.")
@click.option("--debug", is_flag=True, help="Enable debug mode.")
@click.option(
    "--database",
    type=click.Path(dir_okay=False, path_type=Path),
    envvar="OUTPUTPROOF_SERVER_DB",
    help="SQLite database path for dashboard history.",
)
def dashboard(host: str, port: int, debug: bool, database: Optional[Path]) -> None:
    """Start the verification dashboard server.

    Launch a local web dashboard for viewing verification history,
    agent reliability scores, and failure patterns.

    \b
    Examples:
        outputproof dashboard
        outputproof dashboard --port 8080 --debug
    """
    try:
        from outputproof_server.app import create_app
    except ImportError as exc:
        raise click.ClickException(
            "The dashboard server is distributed separately as outputproof-server "
            "under BSL 1.1. Install the server package to use this command."
        ) from exc

    app = create_app(
        debug=debug,
        allowed_origins=[
            f"http://{host}:{port}",
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ],
        database_path=database,
    )

    console.print(Panel(
        f"[bold blue]OutputProof Dashboard[/bold blue]\n\n"
        f"Starting server at [link=http://{host}:{port}]http://{host}:{port}[/link]\n\n"
        f"To populate the dashboard from CLI runs, open another PowerShell "
        f"window and run:\n"
        f"[bold]$env:OUTPUTPROOF_SERVER_URL = \"http://{host}:{port}\"[/bold]\n"
        f"[bold]python -m outputproof.cli.main verify ...[/bold]\n\n"
        f"Press [bold]Ctrl+C[/bold] to stop.",
        title="Dashboard Server",
        border_style="blue",
    ))

    try:
        import uvicorn
        uvicorn.run(app, host=host, port=port, log_level="info" if not debug else "debug")
    except ImportError:
        console.print("[red]Error:[/red] uvicorn is required. Install with: pip install outputproof-server")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


@cli.group()
def policy() -> None:
    """Manage verification policies."""
    pass


@policy.command("list")
@click.option("--output-json", is_flag=True, help="Output as JSON.")
def list_policies(output_json: bool) -> None:
    """List all verification policies."""
    from outputproof.models import Policy, EnforcementMode

    # Sample policies for demo
    policies = [
        Policy(
            policy_id="pol-001",
            name="Default Policy",
            scope="global",
            enforcement=EnforcementMode.WARN,
            threshold=0.7,
        ),
        Policy(
            policy_id="pol-002",
            name="Strict Policy",
            scope="global",
            enforcement=EnforcementMode.BLOCK,
            threshold=0.9,
        ),
    ]

    if output_json:
        console.print(json.dumps([p.__dict__ for p in policies], indent=2, default=str))
    else:
        table = Table(title="Verification Policies")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Scope")
        table.add_column("Enforcement")
        table.add_column("Threshold")
        table.add_column("Enabled")

        for policy in policies:
            table.add_row(
                policy.policy_id,
                policy.name,
                policy.scope,
                policy.enforcement.value,
                f"{policy.threshold:.1f}",
                "Yes" if policy.enabled else "No",
            )

        console.print(table)


@policy.command("create")
@click.option("--name", required=True, help="Policy name.")
@click.option("--scope", default="global", help="Policy scope (global, agent, task).")
@click.option("--enforcement", default="warn", help="Enforcement mode (block, warn, log).")
@click.option("--threshold", default=0.7, help="Minimum confidence threshold.")
def create_policy(
    name: str,
    scope: str,
    enforcement: str,
    threshold: float,
) -> None:
    """Create a new verification policy."""
    from outputproof.models import Policy, EnforcementMode

    policy = Policy(
        policy_id=f"pol-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        name=name,
        scope=scope,
        enforcement=EnforcementMode(enforcement),
        threshold=threshold,
    )

    # TODO: Save policy to storage
    console.print(f"[green]Policy created:[/green] {policy.name}")
    console.print(f"ID: {policy.policy_id}")


@policy.command("delete")
@click.option("--id", "policy_id", required=True, help="Policy ID to delete.")
def delete_policy(policy_id: str) -> None:
    """Delete a verification policy."""
    # TODO: Implement policy deletion
    console.print(f"[yellow]Policy deletion not yet implemented.[/yellow]")
    console.print(f"Would delete policy ID: [bold]{policy_id}[/bold]")


@cli.command()
@click.option("--agent-id", help="Filter by agent ID.")
@click.option("--days", default=7, help="Number of days to include.")
@click.option("--output-json", is_flag=True, help="Output as JSON.")
def history(agent_id: Optional[str], days: int, output_json: bool) -> None:
    """View verification history."""
    records = load_verifications()
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    filtered = []
    for record in records:
        if agent_id and record.get("agent_id") != agent_id:
            continue
        try:
            record_ts = datetime.fromisoformat(record["timestamp"]).timestamp()
        except (KeyError, ValueError):
            record_ts = 0
        if record_ts >= cutoff:
            filtered.append(record)

    if agent_id:
        console.print(f"Filtering by agent: [bold]{agent_id}[/bold]")

    if output_json:
        console.print(json.dumps(filtered, indent=2))
        return

    table = Table(title=f"Verification History ({days} days)")
    table.add_column("Time")
    table.add_column("ID", style="cyan")
    table.add_column("Agent")
    table.add_column("Verdict")
    table.add_column("Confidence")
    table.add_column("Retries")

    for record in sorted(filtered, key=lambda item: item.get("timestamp", ""), reverse=True):
        table.add_row(
            record.get("timestamp", ""),
            record.get("request_id", ""),
            record.get("agent_id") or "unknown",
            record.get("verdict", "UNKNOWN"),
            f"{record.get('confidence_score', 0):.2f}",
            str(record.get("retry_count", 0)),
        )

    console.print(table)


@cli.command()
def init() -> None:
    """Initialize OutputProof configuration.

    Creates the configuration directory and default config files.
    """
    config_dir = Path.home() / ".outputproof"
    config_dir.mkdir(exist_ok=True)

    config_file = config_dir / "config.yaml"
    if not config_file.exists():
        config_file.write_text("""# OutputProof Configuration
# Generated by outputproof init

judge:
  model: claude-haiku-4-5
  # api_key: ${ANTHROPIC_API_KEY}

dashboard:
  host: 127.0.0.1
  port: 8080

storage:
  type: sqlite
  path: ~/.outputproof/outputproof.db
""")
        console.print(f"[green]Created config file:[/green] {config_file}")
    else:
        console.print(f"[yellow]Config already exists:[/yellow] {config_file}")

    console.print("[green]OutputProof initialized![/green]")


def _print_verification_result(result) -> None:
    """Print a verification result in a readable format."""
    # Status panel
    if result.passed:
        status = "[green bold]PASSED[/green bold]"
    elif result.verdict == VerificationVerdict.PARTIAL:
        status = "[yellow bold]PARTIAL[/yellow bold]"
    else:
        status = "[red bold]FAILED[/red bold]"

    console.print(Panel(
        f"Verdict: {status}\n"
        f"Confidence: {result.confidence_score:.2f}\n"
        f"Assertions: {len(result.assertion_results)} evaluated, "
        f"{sum(1 for a in result.assertion_results if a.passed)} passed",
        title="Verification Result",
        border_style="green" if result.passed else "red",
    ))

    # Assertion details table
    if result.assertion_results:
        table = Table(title="Assertion Results")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Message")

        for assertion in result.assertion_results:
            status_style = "green" if assertion.passed else "red"
            status = "PASS" if assertion.passed else "FAIL"
            table.add_row(
                assertion.name,
                assertion.assertion_type.value,
                f"[{status_style}]{status}[/{status_style}]",
                assertion.message[:60] + ("..." if len(assertion.message) > 60 else ""),
            )

        console.print(table)

    # Judge explanation
    if result.judge_explanation:
        console.print(Panel(
            result.judge_explanation,
            title="Judge Explanation",
            border_style="blue",
        ))


def _print_record(record: dict) -> None:
    """Print a stored verification record."""
    verdict = record.get("verdict", "UNKNOWN")
    confidence = record.get("confidence_score", 0.0)
    console.print(
        Panel(
            f"ID: {record.get('request_id')}\n"
            f"Agent: {record.get('agent_id') or 'unknown'}\n"
            f"Verdict: {verdict}\n"
            f"Confidence: {confidence:.2f}\n"
            f"Retries: {record.get('retry_count', 0)}",
            title="Verification Report",
            border_style="green" if verdict == "PASS" else "red",
        )
    )

    assertions = record.get("assertion_results", [])
    if assertions:
        table = Table(title="Assertion Results")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Message")
        for assertion in assertions:
            passed = assertion.get("passed", False)
            table.add_row(
                assertion.get("name", ""),
                assertion.get("assertion_type", ""),
                "PASS" if passed else "FAIL",
                assertion.get("message", ""),
            )
        console.print(table)


if __name__ == "__main__":
    cli()
