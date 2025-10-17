#!/usr/bin/env python
"""Discover Power BI workspace and dataset IDs using REST API."""
import json
import subprocess
import sys

import requests


def get_token():
    """Get Power BI access token via Azure CLI."""
    try:
        result = subprocess.run(
            [
                r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
                "account",
                "get-access-token",
                "--tenant",
                "17f69c66-2114-4826-9fb1-6e496607aebc",
                "--resource",
                "https://analysis.windows.net/powerbi/api",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            token_data = json.loads(result.stdout)
            return token_data["accessToken"]
        else:
            print(f"Failed to get token: {result.stderr}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Error getting token: {e}", file=sys.stderr)
        return None


def main():
    token = get_token()
    if not token:
        print("❌ Failed to acquire Power BI token")
        return 1

    print("✅ Token acquired\n")

    headers = {"Authorization": f"Bearer {token}"}

    # Get all workspaces
    print("📊 Fetching workspaces...")
    response = requests.get("https://api.powerbi.com/v1.0/myorg/groups", headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"❌ Failed to get workspaces: {response.status_code} - {response.text}")
        return 1

    workspaces = response.json().get("value", [])
    print(f"Found {len(workspaces)} workspaces\n")

    # Find CN_DEV workspace
    cn_dev = None
    for ws in workspaces:
        if "CN_DEV" in ws.get("name", ""):
            cn_dev = ws
            break

    if not cn_dev:
        print("❌ CN_DEV workspace not found")
        print("\nAvailable workspaces:")
        for ws in workspaces[:10]:
            print(f"  - {ws['name']} ({ws['id']})")
        return 1

    print(f"✅ Found workspace: {cn_dev['name']}")
    print(f"   Workspace ID: {cn_dev['id']}\n")

    # Get datasets in CN_DEV
    print("📊 Fetching datasets...")
    datasets_response = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/groups/{cn_dev['id']}/datasets", headers=headers, timeout=30
    )

    if datasets_response.status_code != 200:
        print(f"❌ Failed to get datasets: {datasets_response.status_code}")
        return 1

    datasets = datasets_response.json().get("value", [])
    print(f"Found {len(datasets)} datasets:\n")

    for ds in datasets:
        print(f"  📋 {ds['name']}")
        print(f"     Dataset ID: {ds['id']}")
        print(f"     Configured: {ds.get('configuredBy', 'N/A')}")
        print()

    # Print command template
    if datasets:
        first_ds = datasets[0]
        print("\n" + "=" * 60)
        print("📝 Sample execute_queries.py command:")
        print("=" * 60)
        print(
            f"python scripts/execute_queries.py \\\n"
            f"  --workspace-id {cn_dev['id']} \\\n"
            f'  --dataset-id {first_ds["id"]} \\\n'
            f'  --query "EVALUATE TOPN(5, Model)"'
        )
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
