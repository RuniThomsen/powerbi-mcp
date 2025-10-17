#!/usr/bin/env python
"""Utility script to call the Power BI Execute Queries REST endpoint."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import (
    AzureCliCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
)

PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def build_arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute a DAX query or measure against a Power BI dataset using the REST API."
    )
    parser.add_argument("--dataset-id", required=True, help="Power BI dataset ID to query.")
    parser.add_argument(
        "--workspace-id",
        help="Optional workspace ID (group ID). If omitted, the personal 'myorg' endpoint is used.",
    )
    parser.add_argument(
        "--query",
        help="DAX query to execute. Use either --query, --query-file, or --measure-name.",
    )
    parser.add_argument(
        "--query-file",
        type=Path,
        help="Path to a file containing a DAX query.",
    )
    parser.add_argument(
        "--measure-name",
        help="Name of a measure to evaluate. The script will wrap it in EVALUATE ROW().",
    )
    parser.add_argument(
        "--measure-label",
        default="MeasureValue",
        help="Column label to use when rendering a measure with --measure-name (default: MeasureValue).",
    )
    parser.add_argument(
        "--include-nulls",
        action="store_true",
        help="Include null values in the response payload (serializerSettings.includeNulls).",
    )
    parser.add_argument(
        "--impersonate",
        help="Optional UPN to impersonate when the dataset has row-level security enabled.",
    )
    parser.add_argument(
        "--access-token",
        help="Provide an explicit access token instead of acquiring one via Azure Identity.",
    )
    parser.add_argument(
        "--credential",
        choices=["auto", "cli", "default", "interactive"],
        default="auto",
        help="Credential acquisition strategy when --access-token is not supplied (default: auto).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the raw JSON response.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=10,
        help="Number of rows to preview per result table (default: 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the composed request and exit without sending it.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional debugging information.",
    )
    return parser


def load_query(args: argparse.Namespace) -> str:
    provided = sum(bool(x) for x in (args.query, args.query_file, args.measure_name))
    if provided == 0:
        raise ValueError("You must supply --query, --query-file, or --measure-name.")
    if provided > 1:
        raise ValueError("Only one of --query, --query-file, or --measure-name may be used at a time.")

    if args.query:
        return args.query.strip()
    if args.query_file:
        if not args.query_file.exists():
            raise FileNotFoundError(f"Query file not found: {args.query_file}")
        return args.query_file.read_text(encoding="utf-8").strip()
    assert args.measure_name
    label = args.measure_label or "MeasureValue"
    return f'EVALUATE ROW("{label}", [{args.measure_name}])'


def acquire_access_token(args: argparse.Namespace) -> str:
    if args.access_token:
        if args.verbose:
            print("Using access token supplied via --access-token")
        return args.access_token

    errors: List[str] = []

    def _attempt(name: str, credential) -> Optional[str]:
        try:
            token = credential.get_token(PBI_SCOPE)
            if args.verbose:
                print(f"Acquired token with {name}; expires at {token.expires_on}")
            return token.token
        except ClientAuthenticationError as exc:  # type: ignore[assignment]
            errors.append(f"{name}: {exc}")
            return None
        except Exception as exc:  # pragma: no cover - defensive logging
            errors.append(f"{name}: {exc}")
            return None

    if args.credential in ("auto", "cli"):
        token = _attempt("AzureCliCredential", AzureCliCredential())
        if token:
            return token
        if args.credential == "cli":
            raise RuntimeError(
                "Failed to acquire token with Azure CLI. Details: " + " | ".join(errors)
            )

    if args.credential in ("auto", "default"):
        token = _attempt("DefaultAzureCredential", DefaultAzureCredential(exclude_cli_credential=True))
        if token:
            return token
        if args.credential == "default":
            raise RuntimeError(
                "Failed to acquire token with DefaultAzureCredential. Details: " + " | ".join(errors)
            )

    if args.credential == "interactive":
        token = _attempt("InteractiveBrowserCredential", InteractiveBrowserCredential())
        if token:
            return token

    if args.credential == "auto":
        token = _attempt("InteractiveBrowserCredential", InteractiveBrowserCredential())
        if token:
            return token

    raise RuntimeError(
        "Unable to acquire an access token. Attempted credentials: " + "; ".join(errors)
    )


def build_request_payload(dax_query: str, args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "queries": [{"query": dax_query}],
        "serializerSettings": {"includeNulls": bool(args.include_nulls)},
    }
    if args.impersonate:
        payload["impersonatedUserName"] = args.impersonate
    return payload


def build_endpoint(args: argparse.Namespace) -> str:
    if args.workspace_id:
        return f"https://api.powerbi.com/v1.0/myorg/groups/{args.workspace_id}/datasets/{args.dataset_id}/executeQueries"
    return f"https://api.powerbi.com/v1.0/myorg/datasets/{args.dataset_id}/executeQueries"


def preview_results(data: Dict[str, Any], preview_rows: int) -> None:
    results: List[Dict[str, Any]] = data.get("results", [])  # type: ignore[assignment]
    if not results:
        print("No results returned.")
        return

    for result_idx, result in enumerate(results, start=1):
        tables: List[Dict[str, Any]] = result.get("tables", [])  # type: ignore[assignment]
        if not tables:
            print(f"Result {result_idx}: no tables returned")
            continue
        for table_idx, table in enumerate(tables, start=1):
            rows: List[Dict[str, Any]] = table.get("rows", [])  # type: ignore[assignment]
            count = len(rows)
            print(f"Result {result_idx}, table {table_idx}: {count} rows")
            if not rows:
                continue
            headers = list(rows[0].keys())
            print(" | ".join(headers))
            limit = min(preview_rows, count)
            for row in rows[:limit]:
                values = [str(row.get(header, "")) for header in headers]
                print(" | ".join(values))
            if count > limit:
                print(f"... ({count - limit} additional row(s) not shown)")


def main() -> int:
    parser = build_arguments()
    args = parser.parse_args()

    try:
        dax_query = load_query(args)
    except Exception as exc:
        parser.error(str(exc))
        return 1

    payload = build_request_payload(dax_query, args)
    endpoint = build_endpoint(args)

    if args.dry_run:
        print("[DRY RUN] Endpoint:")
        print(endpoint)
        print("[DRY RUN] Payload:")
        print(json.dumps(payload, indent=2))
        return 0

    try:
        token = acquire_access_token(args)
    except Exception as exc:
        print(f"Failed to acquire access token: {exc}", file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if args.verbose:
        print(f"POST {endpoint}")
        print(json.dumps(payload, indent=2))

    response = requests.post(endpoint, headers=headers, json=payload, timeout=args.timeout)

    if args.verbose:
        print(f"HTTP {response.status_code}")

    if response.status_code != 200:
        print(
            f"Request failed with status {response.status_code}: {response.text}",
            file=sys.stderr,
        )
        return 1

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        print(f"Failed to parse JSON response: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Response written to {args.output}")

    preview_results(data, args.preview_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
