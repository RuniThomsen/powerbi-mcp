"""
Enhanced PowerBI MCP Server with multiple authentication methods
This version supports:
1. Service Principal (client_id + client_secret) - original method
2. Azure CLI authentication - when Azure CLI is installed and user is logged in
3. Managed Identity - when running on Azure resources

To use Azure CLI authentication:
1. Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
2. Login: az login --tenant <your-tenant-id>
3. Set USE_AZURE_CLI=true in your .env file or MCP configuration

For tenant-level accounts (no Azure subscription):
- Set ALLOW_TENANT_LEVEL_ACCOUNT=true to suppress subscription warnings
- Power BI only requires Azure AD tenant access, not Azure subscriptions
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.routing import Route

from powerbi_rest_client import PowerBIRestClient, PowerBIRestError

# Azure authentication support
try:
    from azure.identity import AzureCliCredential, ClientSecretCredential, DefaultAzureCredential

    AZURE_AUTH_AVAILABLE = True
except ImportError:
    AZURE_AUTH_AVAILABLE = False
    DefaultAzureCredential = None
    AzureCliCredential = None
    ClientSecretCredential = None

# Configure logging to stderr for MCP debugging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stderr
)
logger = logging.getLogger(__name__)

POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Updated imports
try:
    # Prefer the canonical public types module
    from mcp.types import Prompt, Resource, TextContent, Tool
except Exception:
    # Fallback minimal stubs to satisfy static analysis / allow limited runtime behavior
    Prompt = None
    Resource = None

    class TextContent:
        def __init__(self, type: str, text: str):
            self.type = type
            self.text = text

        def __repr__(self):
            return f"TextContent(type={self.type!r}, text={self.text!r})"

    class Tool:
        def __init__(self, name: str, description: str = "", inputSchema: dict = None):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema or {}

        def __repr__(self):
            return f"Tool(name={self.name!r})"


# Load environment variables
load_dotenv()

# Track package loading attempts to avoid duplicate warnings
_adomd_load_attempted = False


def _format_markdown_table(headers: List[str], rows: List[Dict[str, Any]], limit: int = 10) -> str:
    """Render a simple Markdown table with optional row limit."""

    if not headers:
        return "*No columns available*\n"

    safe_headers = [str(h) for h in headers]
    lines = ["| " + " | ".join(safe_headers) + " |", "| " + " | ".join(["---"] * len(safe_headers)) + " |"]

    display_rows = rows[: limit if limit and limit > 0 else len(rows)]
    for row in display_rows:
        values = []
        for header in safe_headers:
            value = row.get(header, "") if isinstance(row, dict) else row
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            value = "" if value is None else str(value)
            value = value.replace("|", "\\|").replace("\n", " ")
            values.append(value[:120])
        lines.append("| " + " | ".join(values) + " |")

    if limit and limit > 0 and len(rows) > limit:
        lines.append(f"\n*({len(rows) - limit} more rows not shown)*")

    return "\n".join(lines) + "\n"


def _format_raw_json(payload: Any, title: str = "Raw response") -> str:
    try:
        body = json.dumps(payload, indent=2, default=str)
    except TypeError:
        body = str(payload)
    return f"\n<details>\n<summary>{title}</summary>\n\n```json\n{body}\n```\n</details>\n"


def _get_latest_lib_path() -> Optional[str]:
    """Get the path to the latest ADOMD.NET library from NuGet packages"""

    # Check if ADOMD_LIB_DIR is set in environment
    env_path = os.getenv("ADOMD_LIB_DIR")
    if env_path and os.path.exists(env_path):
        logger.info(f"Using ADOMD_LIB_DIR from environment: {env_path}")
        return env_path

    # Look for NuGet packages directory
    nuget_base = os.path.expanduser("~/.nuget/packages")
    if not os.path.exists(nuget_base):
        if not _adomd_load_attempted:
            logger.warning(
                "NuGet packages directory not found. Consider running 'dotnet add package Microsoft.AnalysisServices.AdomdClient' to install ADOMD.NET"
            )
        return None

    # Look for Microsoft.AnalysisServices.AdomdClient package
    adomd_pattern = os.path.join(nuget_base, "microsoft.analysisservices.adomdclient")
    if not os.path.exists(adomd_pattern):
        if not _adomd_load_attempted:
            logger.warning(f"ADOMD.NET package not found at {adomd_pattern}")
        return None

    # Find the latest version
    try:
        versions = [d for d in os.listdir(adomd_pattern) if os.path.isdir(os.path.join(adomd_pattern, d))]
        if not versions:
            return None

        # Sort versions to get the latest
        versions.sort(reverse=True)
        latest_version = versions[0]

        # Check for different target frameworks in order of preference
        targets = ["net8.0", "net6.0", "netstandard2.0", "net48", "net472", "net471", "net47"]

        for target in targets:
            lib_path = os.path.join(adomd_pattern, latest_version, "lib", target)
            if os.path.exists(lib_path):
                logger.info(f"Found ADOMD.NET at {lib_path}")
                return lib_path

        if not _adomd_load_attempted:
            logger.warning(f"No compatible target framework found for ADOMD.NET version {latest_version}")
        return None

    except Exception as e:
        if not _adomd_load_attempted:
            logger.error(f"Error finding ADOMD.NET library: {e}")
        return None


# Configure pythonnet runtime before importing clr/pyadomd
if not os.getenv("PYTHONNET_RUNTIME"):
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"


# Try to set DOTNET_ROOT if missing (common Windows install path)
if os.name == "nt" and not os.getenv("DOTNET_ROOT"):
    default_dotnet = r"C:\\Program Files\\dotnet"
    if os.path.exists(default_dotnet):
        os.environ["DOTNET_ROOT"] = default_dotnet

# Add ADOMD.NET to Python path before importing
lib_path = _get_latest_lib_path()
if lib_path and lib_path not in sys.path:
    sys.path.insert(0, lib_path)
    logger.info(f"Added {lib_path} to Python path")
    # On Windows, also add to DLL search path
    if os.name == "nt":
        try:
            os.add_dll_directory(lib_path)
        except Exception:
            pass


# Helper to add CLR references from NuGet packages
def _try_add_reference_from_nuget(pkg_name: str, dll_rel_path_candidates: list[str]) -> bool:
    base = os.path.expanduser(f"~/.nuget/packages/{pkg_name}")
    try:
        if not os.path.exists(base):
            return False
        versions = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        versions.sort(reverse=True)
        for ver in versions:
            for rel in dll_rel_path_candidates:
                fp = os.path.join(base, ver, rel)
                if os.path.exists(fp):
                    try:
                        clr.AddReference(fp)
                        logger.info(f"Loaded {pkg_name} from {fp}")
                        return True
                    except Exception as e:
                        logger.debug(f"Failed to add reference {fp}: {e}")
        return False
    except Exception as e:
        logger.debug(f"NuGet scan error for {pkg_name}: {e}")
        return False


# Helper to load ADOMD.NET assembly (prefer explicit path if present)
def _load_adomd_assembly(lib_path: Optional[str]) -> None:
    if lib_path:
        adomd_dll = os.path.join(lib_path, "Microsoft.AnalysisServices.AdomdClient.dll")
        if os.path.exists(adomd_dll):
            clr.AddReference(adomd_dll)
            logger.info(f"Loaded ADOMD.NET from {adomd_dll}")
            return
    # Fallback to GAC / default reference
    clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
    logger.info("Loaded ADOMD.NET from GAC")


# Helper to import pyadomd with simple retry loop
def _import_pyadomd_with_retries(retries: int = 3, delay_sec: float = 0.5):
    for attempt in range(retries):
        try:
            from Microsoft.AnalysisServices.AdomdClient import AdomdSchemaGuid  # type: ignore
            from pyadomd import Pyadomd  # type: ignore

            logger.info(f"Successfully imported pyadomd on attempt {attempt + 1}")
            return Pyadomd, AdomdSchemaGuid
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"pyadomd import attempt {attempt + 1} failed: {e}, retrying...")
                import time

                time.sleep(delay_sec)
            else:
                logger.error(f"Failed to import pyadomd after {retries} attempts: {e}")
    return None, None


# Import .NET libraries with enhanced error handling


try:
    import clr

    # Prime CLR import hook
    try:
        import System  # noqa: F401  # type: ignore
    except Exception:
        pass

    # Load ADOMD.NET assembly (explicit path preferred)
    _load_adomd_assembly(lib_path)

    # Proactively load common ADOMD dependencies from NuGet if present
    _try_add_reference_from_nuget(
        "system.configuration.configurationmanager",
        [
            os.path.join("lib", "net8.0", "System.Configuration.ConfigurationManager.dll"),
            os.path.join("lib", "net6.0", "System.Configuration.ConfigurationManager.dll"),
            os.path.join("lib", "netstandard2.0", "System.Configuration.ConfigurationManager.dll"),
        ],
    )

    _try_add_reference_from_nuget(
        "system.data.sqlclient",
        [
            os.path.join("lib", "net8.0", "System.Data.SqlClient.dll"),
            os.path.join("lib", "net6.0", "System.Data.SqlClient.dll"),
            os.path.join("lib", "netstandard2.0", "System.Data.SqlClient.dll"),
        ],
    )

    # Import base Microsoft namespace to prime pythonnet
    try:
        import Microsoft  # noqa: F401  # type: ignore
    except Exception:
        pass

    # Try to import pyadomd with retries
    Pyadomd, AdomdSchemaGuid = _import_pyadomd_with_retries()
    # Also import AdomdConnection for explicit token-based connections
    try:
        from Microsoft.AnalysisServices.AdomdClient import AdomdConnection  # type: ignore
    except Exception:
        AdomdConnection = None  # type: ignore

    _adomd_load_attempted = True

except Exception as e:
    logger.error(f"Failed to load .NET libraries: {str(e)}")
    Pyadomd = None
    AdomdSchemaGuid = None
    _adomd_load_attempted = True


class AzureAuthenticator:
    """Handles different Azure authentication methods"""

    def __init__(self):
        self.credential = None
        self.auth_method = None

    def authenticate(
        self,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None,
        scope: str = POWER_BI_SCOPE,
    ) -> str:
        """
        Authenticate using available methods in order of preference:
        1. Windows Authentication (if tenant_id is None - for on-premises SSAS)
        2. Azure CLI (if USE_AZURE_CLI=true and azure-identity available)
        3. Service Principal (if client_id and client_secret provided)
        4. Default Azure Credential (includes managed identity, etc.)

        Supports tenant-level accounts (no Azure subscription required):
        - Set ALLOW_TENANT_LEVEL_ACCOUNT=true to suppress warnings
        - Power BI only needs Azure AD tenant access, not subscriptions

        Returns: Access token for Power BI, or special markers:
        - "windows_auth" for Windows authentication (Integrated Security)
        - "connection_string" for Service Principal via connection string
        """
        # Check for Windows Authentication (on-premises SSAS)
        if tenant_id is None or tenant_id == "":
            self.auth_method = "Windows Authentication"
            logger.info("Using Windows Authentication (Integrated Security)")
            return "windows_auth"  # Special marker for Windows auth
        
        scope = scope or POWER_BI_SCOPE
        resource = scope[:-9] if scope.endswith("/.default") else scope
        
        # Check if tenant-level accounts are explicitly allowed
        allow_tenant_level = os.getenv("ALLOW_TENANT_LEVEL_ACCOUNT", "false").lower() == "true"
        if allow_tenant_level:
            logger.info("Tenant-level accounts allowed (no Azure subscription required)")

        if not AZURE_AUTH_AVAILABLE:
            if client_id and client_secret:
                # Fall back to connection string method for Service Principal
                return self._create_connection_string_auth(tenant_id, client_id, client_secret)
            else:
                raise Exception("azure-identity package not available and no Service Principal credentials provided")

        # Prefer Azure CLI if requested
        use_cli = os.getenv("USE_AZURE_CLI", "false").lower() == "true"
        if use_cli:
            try:
                # Prefer direct az CLI call for compatibility with DAX Studio flow
                import shutil
                import subprocess

                az_path = shutil.which("az")
                if az_path:
                    # First try modern --scope syntax
                    result = subprocess.run(
                        [
                            az_path,
                            "account",
                            "get-access-token",
                            "--tenant",
                            tenant_id,
                            "--scope",
                            scope,
                            "--query",
                            "accessToken",
                            "--output",
                            "tsv",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    token_val = result.stdout.strip() if result.returncode == 0 else None
                    if token_val:
                        self.auth_method = "Azure CLI (subprocess)"
                        logger.info("Authenticated using Azure CLI (subprocess)")
                        return token_val
                    else:
                        # Fallback to legacy --resource if --scope failed or CLI is older
                        legacy = subprocess.run(
                            [
                                az_path,
                                "account",
                                "get-access-token",
                                "--tenant",
                                tenant_id,
                                "--resource",
                                resource,
                                "--query",
                                "accessToken",
                                "--output",
                                "tsv",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        token_val = legacy.stdout.strip() if legacy.returncode == 0 else None
                        if token_val:
                            self.auth_method = "Azure CLI (subprocess)"
                            logger.info("Authenticated using Azure CLI (subprocess legacy)")
                            return token_val
                        else:
                            logger.warning(
                                "az CLI token failed (both --scope and --resource): rc=%s, stderr=%s",
                                legacy.returncode,
                                legacy.stderr.strip() if legacy.stderr else "",
                            )

                # Bind to the requested tenant to avoid cross-tenant auth issues
                try:
                    self.credential = AzureCliCredential(tenant_id=tenant_id)
                except TypeError:
                    # Older azure-identity versions may not support tenant_id param
                    self.credential = AzureCliCredential()
                token = self.credential.get_token(scope)
                self.auth_method = "Azure CLI"
                logger.info("Authenticated using Azure CLI")
                return token.token
            except Exception as e:
                logger.warning(f"Azure CLI authentication failed: {e}")

        # Next: Service Principal with client credentials
        if client_id and client_secret:
            try:
                self.credential = ClientSecretCredential(
                    tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
                )
                token = self.credential.get_token(scope)
                self.auth_method = "Service Principal"
                logger.info("Authenticated using Service Principal")
                return token.token
            except Exception as e:
                logger.warning(f"Service Principal authentication failed: {e}")

        # Finally: Default Azure Credential (managed identity, etc.)
        try:
            self.credential = DefaultAzureCredential()
            token = self.credential.get_token(scope)
            self.auth_method = "Default Azure Credential"
            logger.info("Authenticated using Default Azure Credential")
            return token.token
        except Exception as e:
            logger.error(f"All authentication methods failed. Last error: {e}")
            raise Exception(f"Authentication failed: {e}")

    def _create_connection_string_auth(self, tenant_id: str, client_id: str, client_secret: str) -> str:
        """Create connection string for Service Principal (legacy method)"""
        self.auth_method = "Service Principal (Connection String)"
        logger.info("Using Service Principal via connection string")
        return "connection_string"  # Special marker for connection string auth


class PowerBIConnector:
    def __init__(self):
        self.connection_string = None
        self.connected = False
        self.tables = []
        self.metadata = {}
        self.authenticator = AzureAuthenticator()
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        # Token-based auth state
        self._access_token = None
        self._base_conn_str = None
        self._tenant_id = None
        self._token_claims = {}
        self._identity_provider = None
        self._client_id = None
        self._client_secret = None
        self._rest_token_cache = {}

    @staticmethod
    def _safe_inspect_token(token: str) -> Dict[str, Any]:
        """Decode JWT without verification to extract minimal diagnostics (tid, aud, upn)."""
        try:
            # Lazy import to avoid hard dependency
            import base64
            import json as _json

            def _b64pad(s: str) -> bytes:
                rem = len(s) % 4
                if rem:
                    s += "=" * (4 - rem)
                return s.encode()

            parts = token.split(".")
            if len(parts) < 2:
                return {}
            payload = _json.loads(base64.urlsafe_b64decode(_b64pad(parts[1])))
            allowed = {k: payload.get(k) for k in ("tid", "aud", "upn", "preferred_username", "iss") if k in payload}
            return allowed
        except Exception:
            return {}

    def _check_pyadomd(self):
        if Pyadomd is None:
            raise Exception("Pyadomd library not available. Ensure .NET runtime and ADOMD.NET are installed")

    def _get_effective_username(self) -> Optional[str]:
        """Determine EffectiveUserName for ADOMD connections."""
        env_effective = os.getenv("PBI_EFFECTIVE_USERNAME")
        if env_effective:
            return env_effective
        if self._token_claims:
            return self._token_claims.get("upn") or self._token_claims.get("preferred_username")
        return None

    def connect(
        self,
        xmla_endpoint: str,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None,
        initial_catalog: str = None,
    ) -> bool:
        """Establish connection to Power BI dataset using available authentication methods
        
        Supports:
        - Windows Authentication: tenant_id=None (for on-premises SSAS)
        - Azure AD Authentication: tenant_id required (for Power BI/Azure AS)
        """
        self._check_pyadomd()

        try:
            # Authenticate and get token or connection string
            self._tenant_id = tenant_id
            self._client_id = client_id
            self._client_secret = client_secret
            self._rest_token_cache.clear()

            auth_result = self.authenticator.authenticate(tenant_id, client_id, client_secret)

            if auth_result == "windows_auth":
                # Windows Authentication for on-premises SSAS
                self._access_token = None
                self._base_conn_str = None
                self.connection_string = (
                    f"Provider=MSOLAP;"
                    f"Data Source={xmla_endpoint};"
                    f"Initial Catalog={initial_catalog};"
                    "Integrated Security=SSPI;"
                    "Connect Timeout=15;"
                )
                # Test using Pyadomd connection string
                logger.info(f"Testing Windows Auth connection with: {self.connection_string}")
                with Pyadomd(self.connection_string):
                    pass
                logger.info("✓ Windows Authentication connection test successful")
            elif auth_result == "connection_string":
                # Service Principal via connection string
                self._access_token = None
                self._base_conn_str = None
                self.connection_string = (
                    f"Provider=MSOLAP;"
                    f"Data Source={xmla_endpoint};"
                    f"Initial Catalog={initial_catalog};"
                    f"User ID=app:{client_id}@{tenant_id};"
                    f"Password={client_secret};"
                    "Connect Timeout=15;"
                )
                # Test using Pyadomd connection string
                with Pyadomd(self.connection_string):
                    pass
            else:
                # Token-based authentication: use direct password embedding (works with Azure CLI tokens)
                self._access_token = auth_result
                self._tenant_id = tenant_id
                self._token_claims = self._safe_inspect_token(self._access_token)
                if tenant_id:
                    self._identity_provider = f"https://login.microsoftonline.com/{tenant_id}/oauth2/authorize"
                else:
                    self._identity_provider = "https://login.microsoftonline.com/organizations/oauth2/authorize"
                token_tid = self._token_claims.get("tid") if self._token_claims else None
                if token_tid and token_tid.lower() != tenant_id.lower():
                    raise Exception(
                        "Access token was issued for tenant "
                        f"{token_tid} but tenant_id {tenant_id} was requested. Please run 'az login' for the target tenant"
                        " or provide explicit client credentials."
                    )
                if self._token_claims:
                    logger.info(
                        "Using AAD token (tid=%s, aud=%s, upn=%s)",
                        self._token_claims.get("tid"),
                        self._token_claims.get("aud"),
                        self._token_claims.get("upn") or self._token_claims.get("preferred_username"),
                    )
                
                # Use simple password embedding (works with Azure CLI tokens where ClaimsToken fails)
                # This approach was verified to work in test_cli_xmla_connection.py
                logger.info("Using direct password embedding for Azure CLI token authentication")
                self._base_conn_str = None
                self.connection_string = (
                    f"Provider=MSOLAP;"
                    f"Data Source={xmla_endpoint};"
                    f"Initial Catalog={initial_catalog};"
                    f"User ID=;"
                    f"Password={self._access_token};"
                    "Persist Security Info=True;"
                    "Connect Timeout=15;"
                )
                
                # Test connection using Pyadomd (works reliably with Azure CLI tokens)
                with Pyadomd(self.connection_string):
                    pass
                
                logger.info("✓ Connection test successful using password embedding method")

            self.connected = True
            logger.info(f"Connected to Power BI dataset: {initial_catalog} using {self.authenticator.auth_method}")
            return True

        except Exception as e:
            self.connected = False
            logger.error(f"Connection failed: {str(e)}")
            raise Exception(f"Connection failed: {str(e)}")

    def get_auth_context(self) -> Dict[str, Optional[str]]:
        """Expose current authentication context for REST clients."""
        return {
            "tenant_id": self._tenant_id,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "access_token": self._access_token,
        }

    def acquire_token(self, scope: str = POWER_BI_SCOPE, force_refresh: bool = False) -> str:
        """Acquire AAD access token for the requested scope."""

        scope = scope or POWER_BI_SCOPE
        if not force_refresh and scope in self._rest_token_cache:
            return self._rest_token_cache[scope]

        # Reuse the XMLA access token when applicable
        if not force_refresh and scope == POWER_BI_SCOPE and self._access_token:
            self._rest_token_cache[scope] = self._access_token
            return self._access_token

        tenant_id = self._tenant_id or os.getenv("DEFAULT_TENANT_ID")
        if not tenant_id:
            raise Exception(
                "Tenant ID is unknown. Connect to Power BI first or set DEFAULT_TENANT_ID before calling REST tools."
            )

        client_id = self._client_id or os.getenv("DEFAULT_CLIENT_ID")
        client_secret = self._client_secret or os.getenv("DEFAULT_CLIENT_SECRET")

        token = self.authenticator.authenticate(tenant_id, client_id, client_secret, scope=scope)
        if token == "connection_string":
            raise Exception(
                "REST API tools require azure-identity to acquire access tokens. Install azure-identity or provide a token manually."
            )

        if not force_refresh:
            self._rest_token_cache[scope] = token
            if scope == POWER_BI_SCOPE:
                self._access_token = token

        return token

    def discover_tables(self) -> List[Dict[str, Any]]:
        """Discover all user-facing tables in the dataset with their descriptions and relationships"""
        if not self.connected:
            raise Exception("Not connected to Power BI")

        self._check_pyadomd()

        # Return cached tables if already discovered
        if self.tables:
            return self.tables

        tables_list = []
        try:
            conn = self._open_connection()
            try:
                tables_dataset = conn.GetSchemaDataSet(AdomdSchemaGuid.Tables, None)

                tables_list_obj = getattr(tables_dataset, "Tables", None)
                if tables_list_obj and len(tables_list_obj) > 0:
                    schema_table = tables_list_obj[0]
                    for row in schema_table.Rows:
                        table_name = row["TABLE_NAME"]
                        if (
                            not table_name.startswith("$")
                            and not table_name.startswith("DateTableTemplate_")
                            and not row["TABLE_SCHEMA"] == "$SYSTEM"
                        ):
                            # Get table description from TMSCHEMA_TABLES
                            table_description = self._get_table_description_direct(table_name)

                            # Get relationships for this table
                            table_relationships = self._get_table_relationships(table_name)

                            tables_list.append(
                                {
                                    "name": table_name,
                                    "description": table_description or "No description available",
                                    "relationships": table_relationships,
                                }
                            )

                self.tables = tables_list
                logger.info(f"Discovered {len(tables_list)} tables with relationships")
                return tables_list
            finally:
                try:
                    conn.Close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error discovering tables: {str(e)}")
            raise Exception(f"Error discovering tables: {str(e)}")

    def _get_table_description_direct(self, table_name: str) -> Optional[str]:
        """Get table description directly from TMSCHEMA_TABLES using a different approach"""
        try:
            conn = self._open_connection()
            try:
                # Query to get table description
                description_query = f"""
                SELECT
                    [Name],
                    [Description]
                FROM $SYSTEM.TMSCHEMA_TABLES
                WHERE [Name] = '{table_name}'
                """

                command = conn.CreateCommand()
                command.CommandText = description_query

                with command.ExecuteReader() as reader:
                    if reader.Read():
                        description = reader["Description"]
                        if description and str(description).strip():
                            return str(description).strip()

                return None
            finally:
                try:
                    conn.Close()
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Could not get description for table {table_name}: {str(e)}")
            return None

    def _get_table_relationships(self, table_name: str) -> List[Dict[str, str]]:
        """Get relationships for a specific table"""
        relationships = []
        try:
            conn = self._open_connection()
            try:
                # Query for relationships where this table is involved
                relationship_query = f"""
                SELECT DISTINCT
                    r.[Name] as RelationshipName,
                    ft.[Name] as FromTable,
                    fc.[Name] as FromColumn,
                    tt.[Name] as ToTable,
                    tc.[Name] as ToColumn,
                    r.[CrossFilteringBehavior],
                    r.[SecurityFilteringBehavior]
                FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS r
                JOIN $SYSTEM.TMSCHEMA_COLUMNS fc ON r.[FromColumnID] = fc.[ID]
                JOIN $SYSTEM.TMSCHEMA_TABLES ft ON fc.[TableID] = ft.[ID]
                JOIN $SYSTEM.TMSCHEMA_COLUMNS tc ON r.[ToColumnID] = tc.[ID]
                JOIN $SYSTEM.TMSCHEMA_TABLES tt ON tc.[TableID] = tt.[ID]
                WHERE ft.[Name] = '{table_name}' OR tt.[Name] = '{table_name}'
                """

                command = conn.CreateCommand()
                command.CommandText = relationship_query

                with command.ExecuteReader() as reader:
                    while reader.Read():
                        from_table = str(reader["FromTable"])
                        to_table = str(reader["ToTable"])
                        from_column = str(reader["FromColumn"])
                        to_column = str(reader["ToColumn"])

                        # Determine the relationship direction relative to current table
                        if from_table == table_name:
                            relationship_type = "One-to-Many (outgoing)"
                            related_table = to_table
                            related_column = f"{from_column} -> {to_table}.{to_column}"
                        else:
                            relationship_type = "Many-to-One (incoming)"
                            related_table = from_table
                            related_column = f"{from_table}.{from_column} -> {to_column}"

                        relationships.append(
                            {
                                "type": relationship_type,
                                "related_table": related_table,
                                "relationship": related_column,
                            }
                        )

            finally:
                try:
                    conn.Close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not get relationships for table {table_name}: {str(e)}")

        return relationships

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get columns for a specific table"""
        if not self.connected:
            raise Exception("Not connected to Power BI")

        self._check_pyadomd()

        try:
            conn = self._open_connection()
            try:
                # Query to get column information with better data types
                columns_query = f"""
                SELECT
                    c.[Name] as ColumnName,
                    c.[DataType] as DataType,
                    c.[Description] as Description,
                    c.[IsHidden] as IsHidden,
                    c.[IsKey] as IsKey
                FROM $SYSTEM.TMSCHEMA_COLUMNS c
                JOIN $SYSTEM.TMSCHEMA_TABLES t ON c.[TableID] = t.[ID]
                WHERE t.[Name] = '{table_name}'
                AND c.[Type] = 1  -- Regular columns only
                ORDER BY c.[ExplicitName], c.[Name]
                """

                columns = []
                command = conn.CreateCommand()
                command.CommandText = columns_query

                with command.ExecuteReader() as reader:
                    while reader.Read():
                        # Convert DataType enum to readable string
                        data_type_num = reader["DataType"]
                        data_type = self._convert_data_type(data_type_num)

                        description = reader["Description"]
                        if description:
                            description = str(description).strip()

                        columns.append(
                            {
                                "name": str(reader["ColumnName"]),
                                "type": data_type,
                                "description": description or "No description available",
                                "is_hidden": bool(reader["IsHidden"]),
                                "is_key": bool(reader["IsKey"]),
                            }
                        )

                return columns
            finally:
                try:
                    conn.Close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {str(e)}")
            raise Exception(f"Error getting columns for table {table_name}: {str(e)}")

    def _convert_data_type(self, data_type_num):
        """Convert numeric data type to readable string"""
        # Common SSAS data types mapping
        type_mapping = {
            2: "String",
            6: "Int64",
            7: "DateTime",
            5: "Double",
            11: "Boolean",
            14: "Decimal",
            16: "Int32",
            131: "Currency",
        }
        return type_mapping.get(int(data_type_num), f"Type{data_type_num}")

    def query_data(self, query: str, max_rows: int = 1000) -> Dict[str, Any]:
        """Execute a DAX query and return results"""
        if not self.connected:
            raise Exception("Not connected to Power BI")

        self._check_pyadomd()

        try:
            conn = self._open_connection()
            try:
                # Add row limit to query if not present
                limited_query = query.strip()
                if not limited_query.upper().startswith("EVALUATE TOPN"):
                    # Wrap the query with TOPN if it's a table expression
                    if limited_query.upper().startswith("EVALUATE"):
                        table_expr = limited_query[8:].strip()  # Remove "EVALUATE"
                        limited_query = f"EVALUATE TOPN({max_rows}, {table_expr})"
                    else:
                        # Assume it's already a table expression
                        limited_query = f"EVALUATE TOPN({max_rows}, {limited_query})"

                command = conn.CreateCommand()
                command.CommandText = limited_query

                result_data = []
                columns_info = []

                with command.ExecuteReader() as reader:
                    # Get column information
                    for i in range(reader.FieldCount):
                        columns_info.append(
                            {
                                "name": reader.GetName(i),
                                "type": str(reader.GetFieldType(i)),
                            }
                        )

                    # Read data
                    row_count = 0
                    while reader.Read() and row_count < max_rows:
                        row = {}
                        for i in range(reader.FieldCount):
                            value = reader.GetValue(i)
                            # Convert special types to JSON-serializable format
                            if isinstance(value, (date, datetime)):
                                value = value.isoformat()
                            elif isinstance(value, Decimal):
                                value = float(value)
                            elif value is None:
                                value = None
                            else:
                                value = str(value)
                            row[columns_info[i]["name"]] = value
                        result_data.append(row)
                        row_count += 1

                return {
                    "columns": columns_info,
                    "data": result_data,
                    "row_count": len(result_data),
                    "query": limited_query,
                }
            finally:
                try:
                    conn.Close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise Exception(f"Error executing query: {str(e)}")

    def _open_connection(self):
        """Open an AdomdConnection, setting AccessToken if available."""
        if AdomdConnection is None:
            raise Exception("ADOMD.NET AdomdConnection not available. Ensure ADOMD is loaded.")
        # Choose connection string
        if self._access_token and self._base_conn_str:
            last_err = None
            effective = self._get_effective_username()
            eff_part = f"EffectiveUserName={effective};" if effective else ""
            identity_part = f"Identity Provider={self._identity_provider};" if self._identity_provider else ""
            # Strategy 1: Use AccessToken property (preferred on newer ADOMD)
            try:
                base_cs = (
                    self._base_conn_str.replace("Integrated Security=ClaimsToken;", "")
                    if "Integrated Security=ClaimsToken;" in self._base_conn_str
                    else self._base_conn_str
                )
                conn = AdomdConnection(base_cs)
                try:
                    # Not all versions expose AccessToken; ignore if not present
                    setattr(conn, "AccessToken", self._access_token)
                except Exception:
                    pass
                conn.Open()
                return conn
            except Exception as e:
                last_err = e
                logger.debug(f"AccessToken property method failed: {e}")

            # Strategy 2: ClaimsToken + Password embedding
            try:
                conn = AdomdConnection(self._base_conn_str + eff_part + f"User ID=;Password={self._access_token};")
                conn.Open()
                return conn
            except Exception as e:
                last_err = e
                logger.debug(f"ClaimsToken password method failed: {e}")

            # Strategy 3: ClaimsToken + Password=Bearer <token>
            try:
                conn = AdomdConnection(
                    self._base_conn_str + eff_part + f"User ID=;Password=Bearer {self._access_token};"
                )
                conn.Open()
                return conn
            except Exception as e:
                last_err = e
                logger.debug(f"ClaimsToken bearer password method failed: {e}")

            # Strategy 4: Plain password embedding without ClaimsToken
            try:
                data_source = re.search(r"Data Source=([^;]+);", self._base_conn_str).group(1)
                catalog = re.search(r"Initial Catalog=([^;]+);", self._base_conn_str).group(1)
                plain_base = (
                    f"Provider=MSOLAP;Data Source={data_source};"
                    f"Initial Catalog={catalog};"
                    f"{identity_part}"
                    "Persist Security Info=True;Connect Timeout=15;"
                )
                conn = AdomdConnection(plain_base + eff_part + f"User ID=;Password={self._access_token};")
                conn.Open()
                return conn
            except Exception as e:
                logger.debug(f"Plain password method failed: {e}")
                last_err = e

            # Strategy 5: Plain base + Password=Bearer <token>
            try:
                data_source = re.search(r"Data Source=([^;]+);", self._base_conn_str).group(1)
                catalog = re.search(r"Initial Catalog=([^;]+);", self._base_conn_str).group(1)
                plain_base = (
                    f"Provider=MSOLAP;Data Source={data_source};"
                    f"Initial Catalog={catalog};"
                    f"{identity_part}"
                    "Persist Security Info=True;Connect Timeout=15;"
                )
                conn = AdomdConnection(plain_base + eff_part + f"User ID=;Password=Bearer {self._access_token};")
                conn.Open()
                return conn
            except Exception as e:
                logger.debug(f"Plain bearer password method failed: {e}")
                raise last_err or e
        elif self.connection_string:
            # Service principal path or Azure CLI token path (password embedding)
            conn = AdomdConnection(self.connection_string)
            conn.Open()
            return conn
        else:
            raise Exception("Connector is not configured. Call connect() first.")


# Optional OpenAI integration for natural language analysis


try:
    from openai import OpenAI

    class DataAnalyzer:
        def __init__(self, api_key: str):
            self.client = OpenAI(api_key=api_key)

        def analyze_natural_language_query(
            self, user_query: str, table_context: List[Dict[str, Any]], column_context: Dict[str, List[Dict[str, Any]]]
        ) -> str:
            """Convert natural language query to DAX using OpenAI"""

            # Build context about available tables and columns
            context_parts = ["Available tables and columns:"]
            for table in table_context:
                table_name = table["name"]
                table_desc = table.get("description", "No description")
                context_parts.append(f"\nTable: {table_name}")
                context_parts.append(f"Description: {table_desc}")

                if table_name in column_context:
                    context_parts.append("Columns:")
                    for col in column_context[table_name]:
                        col_desc = col.get("description", "")
                        context_parts.append(f"  - {col['name']} ({col['type']}): {col_desc}")

                # Add relationships if available
                if table.get("relationships"):
                    context_parts.append("Relationships:")
                    for rel in table["relationships"]:
                        context_parts.append(f"  - {rel['type']}: {rel['relationship']}")

            context_str = "\n".join(context_parts)

            prompt = f"""You are a DAX expert. Convert this natural language query into a DAX query.

Context:
{context_str}

User Query: {user_query}

Rules:
1. Always use EVALUATE to return a table
2. Use proper DAX syntax and functions
3. Reference tables and columns correctly using 'TableName'[ColumnName] syntax
4. Add helpful comments explaining the logic
5. If aggregation is needed, use appropriate DAX functions like SUM, COUNT, AVERAGE, etc.
6. For filters, use FILTER function or table filtering syntax
7. Keep the query efficient and readable

Return only the DAX query, no explanation:"""

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.1,
                )

                dax_query = response.choices[0].message.content.strip()

                # Clean up the response
                if dax_query.startswith("```dax"):
                    dax_query = dax_query[6:]
                if dax_query.startswith("```"):
                    dax_query = dax_query[3:]
                if dax_query.endswith("```"):
                    dax_query = dax_query[:-3]

                return dax_query.strip()

            except Exception as e:
                logger.error(f"Error generating DAX query: {str(e)}")
                raise Exception(f"Error generating DAX query: {str(e)}")

except ImportError:
    logger.info("OpenAI library not available - natural language features disabled")
    DataAnalyzer = None

# MCP Server implementation
app = Server("powerbi-server")

# Initialize connector and analyzer
connector = PowerBIConnector()
analyzer = None
rest_client = PowerBIRestClient(connector, connector.authenticator)

# Connection state
is_connected = False
connection_lock = threading.Lock()


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available Power BI tools"""
    tools = [
        Tool(
            name="pbi_connect",
            description="Connect to Power BI dataset or on-premises SSAS using various authentication methods",
            inputSchema={
                "type": "object",
                "properties": {
                    "xmla_endpoint": {
                        "type": "string",
                        "description": "XMLA endpoint URL. For Power BI: 'powerbi://api.powerbi.com/v1.0/myorg/WorkspaceName'. For on-premises SSAS: server name or 'http://server/olap/msmdpump.dll'",
                    },
                    "initial_catalog": {
                        "type": "string",
                        "description": "Name of the Power BI dataset/semantic model or SSAS database to connect to",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Azure AD tenant ID (required for Power BI/Azure AS, omit or set to empty string for Windows Authentication with on-premises SSAS)",
                    },
                    "client_id": {
                        "type": "string",
                        "description": "Service Principal client ID (optional if using Azure CLI auth or Windows Authentication)",
                    },
                    "client_secret": {
                        "type": "string",
                        "description": "Service Principal client secret (optional if using Azure CLI auth or Windows Authentication)",
                    },
                },
                "required": ["xmla_endpoint", "initial_catalog"],
            },
        ),
        Tool(
            name="pbi_list_tables",
            description="List all tables in the connected Power BI dataset with descriptions and relationships",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="pbi_describe_table",
            description="Get detailed information about a specific table including all columns",
            inputSchema={
                "type": "object",
                "properties": {"table_name": {"type": "string", "description": "Name of the table to describe"}},
                "required": ["table_name"],
            },
        ),
        Tool(
            name="pbi_query_data",
            description="Execute a DAX query against the Power BI dataset",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "DAX query to execute"},
                    "max_rows": {"type": "integer", "description": "Maximum number of rows to return (default: 1000)", "default": 1000},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="pbi_rest_list_workspaces",
            description="List workspaces available to the authenticated identity via the Power BI REST API",
            inputSchema={
                "type": "object",
                "properties": {
                    "top": {
                        "type": "integer",
                        "description": "Maximum number of workspaces to return (default: 100)",
                        "default": 100,
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional case-insensitive substring to filter workspace names",
                    },
                },
            },
        ),
        Tool(
            name="pbi_rest_list_datasets",
            description="List datasets within a workspace using the Power BI REST API",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "Optional workspace GUID. When omitted, lists datasets from My Workspace",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Maximum number of datasets to return (default: 100)",
                        "default": 100,
                    },
                },
            },
        ),
        Tool(
            name="pbi_rest_execute_query",
            description="Execute the Power BI REST executeQueries endpoint for a dataset",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "Dataset/semantic model ID to query"},
                    "workspace_id": {
                        "type": "string",
                        "description": "Optional workspace GUID when querying a workspace dataset",
                    },
                    "query": {"type": "string", "description": "DAX query to execute"},
                    "measure_name": {
                        "type": "string",
                        "description": "Name of a measure to evaluate when query is not provided",
                    },
                    "measure_label": {
                        "type": "string",
                        "description": "Label to use for measure output column (default: MeasureValue)",
                        "default": "MeasureValue",
                    },
                    "include_nulls": {
                        "type": "boolean",
                        "description": "If true, preserve null values in the response payload",
                        "default": False,
                    },
                    "impersonated_user": {
                        "type": "string",
                        "description": "Optional UPN to impersonate for RLS scenarios",
                    },
                    "preview_rows": {
                        "type": "integer",
                        "description": "Number of rows to include in the preview table (default: 10)",
                        "default": 10,
                    },
                    "access_token": {
                        "type": "string",
                        "description": "Optional explicit access token to use instead of refreshing credentials",
                    },
                },
                "required": ["dataset_id"],
                "oneOf": [
                    {"required": ["query"]},
                    {"required": ["measure_name"]},
                ],
            },
        ),
    ]

    # Add natural language query tool if OpenAI is available
    if analyzer:
        tools.append(
            Tool(
                name="pbi_natural_language_query",
                description="Ask a question about the data in natural language; generates and runs DAX",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Natural language question about the data (e.g., 'Show me total sales by region')",
                        },
                        "max_rows": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default: 100)",
                            "default": 100,
                        },
                    },
                    "required": ["question"],
                },
            )
        )

    return tools


@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:  # noqa: C901
    """Handle tool calls"""
    try:
        # Backward compatibility: accept old names, but prefer pbi_* names
        if name in ("pbi_connect", "connect"):
            return [TextContent(type="text", text=await _handle_connect(arguments))]

        elif name in ("pbi_list_tables", "list_tables"):
            if not is_connected:
                return [TextContent(type="text", text="Not connected to Power BI. Use the 'connect' tool first.")]

            tables = await asyncio.get_event_loop().run_in_executor(None, connector.discover_tables)

            result = "**Available Tables:**\n\n"
            for table in tables:
                result += f"### {table['name']}\n"
                result += f"**Description:** {table['description']}\n"

                if table.get("relationships"):
                    result += "**Relationships:**\n"
                    for rel in table["relationships"]:
                        result += f"- {rel['type']}: {rel['relationship']}\n"
                else:
                    result += "**Relationships:** None\n"
                result += "\n"

            return [TextContent(type="text", text=result)]

        elif name in ("pbi_describe_table", "describe_table"):
            if not is_connected:
                return [TextContent(type="text", text="Not connected to Power BI. Use the 'connect' tool first.")]

            table_name = arguments["table_name"]
            columns = await asyncio.get_event_loop().run_in_executor(None, connector.get_columns, table_name)

            result = f"**Table: {table_name}**\n\n**Columns:**\n\n"
            for col in columns:
                visibility = " (Hidden)" if col.get("is_hidden") else ""
                key_marker = " 🔑" if col.get("is_key") else ""
                result += f"- **{col['name']}** ({col['type']}){key_marker}{visibility}: {col['description']}\n"

            return [TextContent(type="text", text=result)]

        elif name in ("pbi_query_data", "query_data"):
            if not is_connected:
                return [TextContent(type="text", text="Not connected to Power BI. Use the 'connect' tool first.")]

            query = arguments["query"]
            max_rows = arguments.get("max_rows", 1000)

            result = await asyncio.get_event_loop().run_in_executor(None, connector.query_data, query, max_rows)

            # Format results
            output = f"**Query:** `{result['query']}`\n\n"
            output += f"**Results:** {result['row_count']} rows\n\n"

            if result["data"]:
                # Create a table view
                output += "| "
                for col in result["columns"]:
                    output += f"{col['name']} | "
                output += "\n| "
                for col in result["columns"]:
                    output += "--- | "
                output += "\n"

                for row in result["data"][:10]:  # Show first 10 rows in summary
                    output += "| "
                    for col in result["columns"]:
                        value = row.get(col["name"], "")
                        if value is None:
                            value = ""
                        output += f"{str(value)[:50]} | "  # Truncate long values
                    output += "\n"

                if len(result["data"]) > 10:
                    output += f"\n*({len(result['data']) - 10} more rows...)*\n"
            else:
                output += "*No data returned*\n"

            return [TextContent(type="text", text=output)]

        elif name == "pbi_rest_list_workspaces":
            # REST API works independently - no XMLA connection needed
            top_value = arguments.get("top")
            top = None
            if top_value is not None:
                try:
                    top = int(top_value)
                except (TypeError, ValueError):
                    return [TextContent(type="text", text="Parameter 'top' must be an integer.")]
            search = arguments.get("search")

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, partial(rest_client.list_workspaces, top=top, search=search)
                )
            except PowerBIRestError as exc:
                return [TextContent(type="text", text=f"REST request failed: {exc}")]

            items = result.get("items", [])
            rows = [
                {
                    "Name": item.get("name", ""),
                    "ID": item.get("id", ""),
                    "Type": item.get("type", "Workspace"),
                    "Dedicated Capacity": "Yes" if item.get("isOnDedicatedCapacity") else "No",
                }
                for item in items
            ]

            limit = top if isinstance(top, int) and top > 0 else len(rows)
            output = "**Power BI Workspaces**\n\n"
            if not rows:
                output += "*No workspaces found.*\n"
            else:
                output += _format_markdown_table(["Name", "ID", "Type", "Dedicated Capacity"], rows, limit)

            output += _format_raw_json(result.get("raw"), title="Raw workspace list")
            return [TextContent(type="text", text=output)]

        elif name == "pbi_rest_list_datasets":
            # REST API works independently - no XMLA connection needed
            workspace_id = arguments.get("workspace_id")
            top_value = arguments.get("top")
            top = None
            if top_value is not None:
                try:
                    top = int(top_value)
                except (TypeError, ValueError):
                    return [TextContent(type="text", text="Parameter 'top' must be an integer.")]

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, partial(rest_client.list_datasets, workspace_id=workspace_id, top=top)
                )
            except PowerBIRestError as exc:
                return [TextContent(type="text", text=f"REST request failed: {exc}")]

            items = result.get("items", [])
            rows = [
                {
                    "Name": item.get("name", ""),
                    "ID": item.get("id", ""),
                    "Configured By": item.get("configuredBy", ""),
                    "Is Refreshable": "Yes" if item.get("isRefreshable") else "No",
                }
                for item in items
            ]

            limit = top if isinstance(top, int) and top > 0 else len(rows)
            scope_label = f"workspace `{workspace_id}`" if workspace_id else "My Workspace"
            output = f"**Datasets available in {scope_label}:**\n\n"
            if not rows:
                output += "*No datasets found.*\n"
            else:
                output += _format_markdown_table(["Name", "ID", "Configured By", "Is Refreshable"], rows, limit)

            output += _format_raw_json(result.get("raw"), title="Raw dataset list")
            return [TextContent(type="text", text=output)]

        elif name == "pbi_rest_execute_query":
            # REST API works independently - no XMLA connection needed
            dataset_id = arguments["dataset_id"]
            workspace_id = arguments.get("workspace_id")
            query = arguments.get("query")
            measure_name = arguments.get("measure_name")
            measure_label = arguments.get("measure_label", "MeasureValue")
            include_nulls = bool(arguments.get("include_nulls", False))
            impersonated_user = arguments.get("impersonated_user")
            preview_rows_value = arguments.get("preview_rows", 10)
            try:
                preview_rows = max(1, int(preview_rows_value))
            except (TypeError, ValueError):
                return [TextContent(type="text", text="Parameter 'preview_rows' must be an integer.")]
            access_token = arguments.get("access_token")

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    partial(
                        rest_client.execute_query,
                        dataset_id=dataset_id,
                        workspace_id=workspace_id,
                        query=query,
                        measure_name=measure_name,
                        measure_label=measure_label,
                        include_nulls=include_nulls,
                        impersonated_user=impersonated_user,
                        preview_rows=preview_rows,
                        access_token=access_token,
                    ),
                )
            except PowerBIRestError as exc:
                return [TextContent(type="text", text=f"REST request failed: {exc}")]

            preview = result.get("preview", [])
            output = f"**Dataset:** `{dataset_id}`\n\n"
            if workspace_id:
                output += f"**Workspace:** `{workspace_id}`\n\n"
            output += f"**Executed Query:** `{result.get('query')}`\n\n"

            if preview:
                for table in preview:
                    name_label = table.get("name") or "Result"
                    output += f"### {name_label}\n"
                    output += f"Rows returned: {table.get('row_count', 0)}\n\n"
                    headers = table.get("headers") or []
                    rows = []
                    for row in table.get("rows", []):
                        rows.append({header: row.get(header, "") for header in headers})
                    output += _format_markdown_table(headers, rows, preview_rows)
            else:
                output += "*No rows returned.*\n"

            output += _format_raw_json(result.get("raw"), title="Raw executeQueries response")
            return [TextContent(type="text", text=output)]

        elif name in ("pbi_natural_language_query", "natural_language_query") and analyzer:
            if not is_connected:
                return [TextContent(type="text", text="Not connected to Power BI. Use the 'connect' tool first.")]

            question = arguments["question"]
            max_rows = arguments.get("max_rows", 100)

            # Get context for AI
            tables = await asyncio.get_event_loop().run_in_executor(None, connector.discover_tables)
            column_context = {}

            # Get columns for each table
            for table in tables:
                try:
                    columns = await asyncio.get_event_loop().run_in_executor(None, connector.get_columns, table["name"])
                    column_context[table["name"]] = columns
                except Exception as e:
                    logger.warning(f"Could not get columns for table {table['name']}: {e}")
                    column_context[table["name"]] = []

            # Generate DAX query
            dax_query = await asyncio.get_event_loop().run_in_executor(
                None, analyzer.analyze_natural_language_query, question, tables, column_context
            )

            # Execute the query
            result = await asyncio.get_event_loop().run_in_executor(None, connector.query_data, dax_query, max_rows)

            # Format results
            output = f"**Question:** {question}\n\n"
            output += f"**Generated DAX:** `{dax_query}`\n\n"
            output += f"**Results:** {result['row_count']} rows\n\n"

            if result["data"]:
                # Create a table view
                output += "| "
                for col in result["columns"]:
                    output += f"{col['name']} | "
                output += "\n| "
                for col in result["columns"]:
                    output += "--- | "
                output += "\n"

                for row in result["data"][:10]:  # Show first 10 rows
                    output += "| "
                    for col in result["columns"]:
                        value = row.get(col["name"], "")
                        if value is None:
                            value = ""
                        output += f"{str(value)[:50]} | "  # Truncate long values
                    output += "\n"

                if len(result["data"]) > 10:
                    output += f"\n*({len(result['data']) - 10} more rows...)*\n"
            else:
                output += "*No data returned*\n"

            return [TextContent(type="text", text=output)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Error executing {name}: {str(e)}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def _handle_connect(arguments: Dict[str, Any]) -> str:
    """Handle connection to Power BI with enhanced authentication"""
    try:
        global is_connected, analyzer

        with connection_lock:
            # Resolve credentials and settings
            tenant_id = arguments.get("tenant_id") or os.getenv("DEFAULT_TENANT_ID")
            client_id = arguments.get("client_id") or os.getenv("DEFAULT_CLIENT_ID")
            client_secret = arguments.get("client_secret") or os.getenv("DEFAULT_CLIENT_SECRET")

            if not tenant_id:
                return "Missing tenant_id. Provide it either in the action arguments or via DEFAULT_TENANT_ID in the .env file."

            # Check if we should use Azure CLI authentication
            use_azure_cli = os.getenv("USE_AZURE_CLI", "false").lower() == "true"

            if not client_id and not client_secret and not use_azure_cli:
                return (
                    "Missing credentials. Either:\n"
                    "1. Provide client_id and client_secret for Service Principal authentication, or\n"
                    "2. Set USE_AZURE_CLI=true in .env file and ensure 'az login' is completed, or\n"
                    "3. Use managed identity on Azure resources\n\n"
                    "For Azure CLI auth, install Azure CLI and run 'az login' first."
                )

            # Establish connection
            await asyncio.get_event_loop().run_in_executor(
                None,
                connector.connect,
                arguments["xmla_endpoint"],
                tenant_id,
                client_id,
                client_secret,
                arguments["initial_catalog"],
            )

            # Initialize the analyzer with OpenAI API key (optional)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OpenAI API key not provided - natural language features disabled")
                analyzer = None
            else:
                analyzer = DataAnalyzer(api_key)

            is_connected = True

            # Discover tables in background only if analyzer is available
            if analyzer:
                asyncio.create_task(_async_prepare_context())

            auth_method = connector.authenticator.auth_method or "Unknown"
            return (
                f"Successfully connected to Power BI dataset '{arguments['initial_catalog']}' using {auth_method}. "
                "Discovering tables..."
            )

    except Exception as e:
        is_connected = False
        logger.error(f"Connection failed: {str(e)}")
        return f"Connection failed: {str(e)}"


async def _async_prepare_context():
    """Prepare context in background for better natural language query performance"""
    try:
        logger.info("Preparing context for natural language queries...")
        tables = await asyncio.get_event_loop().run_in_executor(None, connector.discover_tables)
        logger.info(f"Context prepared with {len(tables)} tables")
    except Exception as e:
        logger.warning(f"Failed to prepare context: {e}")


# Web server for SSE transport


async def handle_sse(request):
    import json

    from starlette.responses import StreamingResponse

    async def event_stream():
        # Send SSE headers and initial connection info
        yield f"data: {json.dumps({'type': 'connection', 'endpoint': '/messages'})}\n\n"

        # Keep connection alive
        while True:
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            await asyncio.sleep(30)  # Keep alive every 30 seconds

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def handle_messages(request):
    """Handle MCP JSON-RPC messages"""
    try:
        body = await request.body()
        message = json.loads(body)

        # Create streams for MCP communication
        from anyio import create_memory_object_stream

        # Create in-memory streams
        send_stream, receive_stream = create_memory_object_stream()
        response_send_stream, response_receive_stream = create_memory_object_stream()

        # Send the request through the stream
        await send_stream.send(message)

        # Process with MCP app
        async def process_message():
            await app.run(
                receive_stream,
                response_send_stream,
                InitializationOptions(server_name="powerbi", server_version="0.1.0"),
            )

        # Start processing in background
        import asyncio

        asyncio.create_task(process_message())

        # Get response
        response = await response_receive_stream.receive()

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Error handling MCP message: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# Create web application
from starlette.responses import JSONResponse

starlette_app = Starlette(
    routes=[
        Route("/sse", handle_sse, methods=["GET"]),
        Route("/messages", handle_messages, methods=["POST"]),
    ]
)

# Run server


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="PowerBI MCP Server")
    parser.add_argument("--host", default=None, help="Host to bind to (if not provided, uses stdio)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")

    args = parser.parse_args()

    logger.info(f"Azure authentication library available: {AZURE_AUTH_AVAILABLE}")
    logger.info(f"ADOMD.NET library available: {Pyadomd is not None}")

    # Check authentication configuration
    use_cli = os.getenv("USE_AZURE_CLI", "false").lower() == "true"
    has_service_principal = bool(os.getenv("DEFAULT_CLIENT_ID") and os.getenv("DEFAULT_CLIENT_SECRET"))

    logger.info("Authentication methods configured:")
    logger.info(f"  - Azure CLI: {use_cli or AZURE_AUTH_AVAILABLE}")
    logger.info(f"  - Service Principal: {has_service_principal}")

    # Run in stdio mode (for VS Code MCP) or HTTP mode
    if args.host is None:
        logger.info("Starting PowerBI MCP Server in stdio mode")
        # Proper stdio transport: provide read/write streams and initialization options
        async with stdio_server() as (read_stream, write_stream):
            capabilities = app.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            )
            await app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="powerbi",
                    server_version="0.1.0",
                    capabilities=capabilities,
                ),
            )
    else:
        logger.info(f"Starting PowerBI MCP Server on {args.host}:{args.port}")
        # Use HTTP server for testing/debugging without nesting event loops
        import uvicorn

        config = uvicorn.Config(starlette_app, host=args.host, port=args.port, loop="asyncio", log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
