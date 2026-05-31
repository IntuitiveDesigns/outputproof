# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""Command-line entry point for the OutputProof dashboard server."""

import argparse

import uvicorn

from outputproof_server.app import create_app


def main() -> None:
    """Run the OutputProof dashboard server."""
    parser = argparse.ArgumentParser(description="Run the OutputProof dashboard server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument(
        "--database",
        default=None,
        help="SQLite database path for dashboard history.",
    )
    args = parser.parse_args()

    app = create_app(
        debug=args.debug,
        allowed_origins=[
            f"http://{args.host}:{args.port}",
            f"http://localhost:{args.port}",
            f"http://127.0.0.1:{args.port}",
        ],
        database_path=args.database,
    )
    dashboard_url = f"http://{args.host}:{args.port}"
    print(f"OutputProof Dashboard: {dashboard_url}")
    print("To populate it from CLI runs, open another PowerShell window and run:")
    print(f'$env:OUTPUTPROOF_SERVER_URL = "{dashboard_url}"')
    print("python -m outputproof.cli.main verify ...")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
