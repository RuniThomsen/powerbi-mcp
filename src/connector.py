"""Simplified PowerBI Connector for MCP Server

Enhancements:
- Auto-discover ADOMD.NET assembly path (or use ADOMD_LIB_DIR)
- Use Azure CLI token-based XMLA authentication (no client secret)
"""

import base64
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Assembly loading helpers
# Global variables for late imports
Pyadomd = None
AdomdSchemaGuid = None

_TFM_PREFERENCE = ("net8.0", "net6.0", "netstandard2.0", "net48", "net472", "net471", "net47")


def _find_nuget_lib(package_name: str) -> Optional[str]:
    """Find the latest NuGet package lib folder for a given package name."""
    base = os.path.join(os.path.expanduser("~"), ".nuget", "packages", package_name)
    if not os.path.isdir(base):
        return None
    try:
        versions = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        versions.sort(reverse=True)
        for ver in versions:
            for tfm in _TFM_PREFERENCE:
                p = os.path.join(base, ver, "lib", tfm)
                if os.path.isdir(p):
                    return p
    except Exception:
        return None
    return None


def _safe_add_dll_dir(path: str) -> None:
    """On Windows, add a directory to the DLL search path if possible."""
    if not path:
        return
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(path)
        except Exception:
            pass


def _add_adomd_to_path(lib_dir: Optional[str]) -> Optional[str]:
    """Add ADOMD library path to sys.path; return the path if found."""
    # If explicit lib dir provided and exists, use it
    if lib_dir and os.path.isdir(lib_dir):
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        _safe_add_dll_dir(lib_dir)
        return lib_dir

    # Try to auto-discover in user's NuGet cache
    base = os.path.join(os.path.expanduser("~"), ".nuget", "packages", "microsoft.analysisservices.adomdclient")
    if not os.path.isdir(base):
        # Fallback to common Windows install locations (SSMS / Feature Pack)
        common_paths = [
            r"C:\\Program Files\\Microsoft.NET\\ADOMD.NET\\160",
            r"C:\\Program Files\\Microsoft.NET\\ADOMD.NET\\150",
            r"C:\\Program Files (x86)\\Microsoft.NET\\ADOMD.NET\\160",
            r"C:\\Program Files (x86)\\Microsoft.NET\\ADOMD.NET\\150",
            r"C:\\Program Files (x86)\\MicrosoftOffice\\root\\vfs\\ProgramFilesX86\\Microsoft.NET\\ADOMD.NET\\130",
        ]
        for p in common_paths:
            if os.path.isdir(p):
                if p not in sys.path:
                    sys.path.insert(0, p)
                _safe_add_dll_dir(p)
                return p
        return None
    try:
        versions = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        versions.sort(reverse=True)
        for ver in versions:
            for tfm in _TFM_PREFERENCE:
                p = os.path.join(base, ver, "lib", tfm)
                if os.path.isdir(p):
                    if p not in sys.path:
                        sys.path.insert(0, p)
                    _safe_add_dll_dir(p)
                    return p
    except Exception:
        return None
    return None


def _import_pyadomd():
    """Dynamically import pyadomd and ADOMD.NET with broad compatibility."""
    global Pyadomd, AdomdSchemaGuid
    if Pyadomd is not None:
        return
    try:
        discovered = _add_adomd_to_path(os.getenv("ADOMD_LIB_DIR"))
        if discovered:
            logger.info(f"Using ADOMD lib path: {discovered}")
        else:
            logger.warning("ADOMD lib path not found; attempting to load by assembly name")

        import clr  # type: ignore

        # Name-based reference first
        try:
            clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
        except Exception as name_err:
            # Fallback to explicit load via System.Reflection if a path is available
            if not discovered:
                raise name_err
            adomd_path = os.path.join(discovered, "Microsoft.AnalysisServices.AdomdClient.dll")
            try:
                from System.Reflection import Assembly  # type: ignore

                if not os.path.isfile(adomd_path):
                    raise name_err
                Assembly.LoadFrom(adomd_path)
            except Exception as load_err:
                logger.error(f"Failed to load ADOMD.NET assembly: {load_err}")
                raise

        from Microsoft.AnalysisServices.AdomdClient import AdomdSchemaGuid as ASGUID  # type: ignore
        from pyadomd import Pyadomd as PyAdomd

        Pyadomd = PyAdomd
        AdomdSchemaGuid = ASGUID
        logger.info("Successfully imported pyadomd and ADOMD.NET")
    except ImportError as e:
        logger.error(f"Failed to import .NET dependencies: {e}")
        raise Exception(f"ADOMD.NET not available. Please run setup scripts first: {e}")
    except Exception as e:
        logger.error(f"Failed to import pyadomd: {e}")
        raise Exception(f"Failed to import pyadomd: {e}")


def _extract_tenant_id_from_jwt(access_token: str) -> Optional[str]:
    """Extract 'tid' (tenant ID) claim from an AAD access token (JWT) without verification."""
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        # Base64url decode
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        payload = json.loads(payload_json)
        tid = payload.get("tid") or payload.get("tenant")
        return tid
    except Exception:
        return None


# End of assembly loading helpers


class PowerBIConnector:
    def __init__(self, workspace_name: str = "CN_DEV", model_name: str = "Model", use_azure_cli: bool = True):
        self.workspace_name = workspace_name
        self.model_name = model_name
        self.use_azure_cli = use_azure_cli
        self.connection_string = None
        self.connected = False
        self.tables = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        # Store last error message (if any)
        self.last_error = None

        # Initialize connection
        self._setup_connection()

    def _setup_connection(self):
        """Setup PowerBI connection string"""
        # FORCE DEBUG: HARDCODED DAX STUDIO VERSION
        logger.error("=== HARDCODED DAX STUDIO CONNECTOR RUNNING ===")

        try:
            _import_pyadomd()

            # HARDCODE everything to force DAX Studio approach
            workspace = "CN_DEV"
            model = "Model"
            tenant_id = "17f69c66-2114-4826-9fb1-6e496607aebc"

            logger.error(f"HARDCODED VALUES: workspace={workspace}, model={model}, tenant={tenant_id}")

            # Get token directly (inline implementation)
            token_value = None
            try:
                import shutil
                import subprocess

                # Check if az command is available
                az_path = shutil.which("az")
                logger.error(f"Az command path: {az_path}")
                if not az_path:
                    raise Exception("Az command not found in PATH")

                logger.error(f"Attempting Azure CLI token for tenant: {tenant_id}")
                result = subprocess.run(
                    [
                        "az",
                        "account",
                        "get-access-token",
                        "--tenant",
                        tenant_id,
                        "--resource",
                        "https://analysis.windows.net/powerbi/api",
                        "--query",
                        "accessToken",
                        "--output",
                        "tsv",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                logger.error(f"Azure CLI returncode: {result.returncode}")
                logger.error(f"Azure CLI stdout: {result.stdout[:100]}...")
                logger.error(f"Azure CLI stderr: {result.stderr}")

                if result.returncode == 0 and result.stdout.strip():
                    token_value = result.stdout.strip()
                    logger.error("Azure CLI token obtained successfully")
                else:
                    logger.error(f"Azure CLI failed: returncode={result.returncode}, stderr={result.stderr}")
            except Exception as e:
                logger.error(f"Azure CLI token exception: {e}")

            if not token_value:
                logger.error("CRITICAL: Subprocess token acquisition failed, trying azure-identity")
                # Fallback to azure-identity library
                try:
                    from azure.identity import AzureCliCredential, DefaultAzureCredential

                    scope = "https://analysis.windows.net/powerbi/api/.default"

                    logger.error(f"Trying AzureCliCredential with tenant_id: {tenant_id}")
                    try:
                        cred = AzureCliCredential(tenant_id=tenant_id) if tenant_id else AzureCliCredential()
                        token_obj = cred.get_token(scope)
                        token_value = token_obj.token
                        logger.error("AzureCliCredential succeeded")
                    except Exception as cli_err:
                        logger.error(f"AzureCliCredential failed: {cli_err}")
                        logger.error("Trying DefaultAzureCredential")
                        token_obj = DefaultAzureCredential().get_token(scope)
                        token_value = token_obj.token
                        logger.error("DefaultAzureCredential succeeded")

                except Exception as auth_err:
                    logger.error(f"Azure identity library failed: {auth_err}")

            if not token_value:
                logger.error("CRITICAL: All token acquisition methods failed")
                raise Exception("Failed to obtain Azure CLI token - both subprocess and azure-identity failed")

            logger.error("Token obtained successfully")

            # HARDCODED DAX Studio connection string - ONLY THIS ONE
            conn_str = (
                "Provider=MSOLAP;"
                f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{workspace};"
                f"Initial Catalog={model};"
                "User ID=;"
                f"Password={token_value};"
                "Persist Security Info=True;"
            )

            logger.error(f"HARDCODED CONNECTION STRING: {conn_str}")

            self.connection_string = conn_str
            self._test_connection()
            logger.error("HARDCODED CONNECTION SUCCESSFUL!")
            return

        except Exception as e:
            logger.error(f"HARDCODED CONNECTION FAILED: {e}")
            self.last_error = f"Hardcoded DAX Studio approach failed: {e}"
            raise

            # Acquire token via Azure CLI (fallback to DefaultAzureCredential)
            token_value: Optional[str] = None
            auth_method = None
            tenant_id: Optional[str] = os.getenv("AZURE_TENANT_ID") or os.getenv("DEFAULT_TENANT_ID")

            # Try direct az CLI call first for precise tenant control
            if tenant_id:
                try:
                    import subprocess

                    result = subprocess.run(
                        [
                            "az",
                            "account",
                            "get-access-token",
                            "--tenant",
                            tenant_id,
                            "--resource",
                            "https://analysis.windows.net/powerbi/api",
                            "--query",
                            "accessToken",
                            "--output",
                            "tsv",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        token_value = result.stdout.strip()
                        auth_method = "Azure CLI Direct"
                        logger.info(f"Acquired token via az CLI for tenant {tenant_id}")
                except Exception as e:
                    logger.warning(f"Direct az CLI failed: {e}")

            # Fallback to azure-identity
            if not token_value:
                try:
                    from azure.identity import AzureCliCredential, DefaultAzureCredential

                    scope = "https://analysis.windows.net/powerbi/api/.default"
                    try:
                        cred = AzureCliCredential(tenant_id=tenant_id) if tenant_id else AzureCliCredential()
                        token_value = cred.get_token(scope).token
                        auth_method = "AzureCliCredential"
                    except Exception:
                        token_value = DefaultAzureCredential().get_token(scope).token
                        auth_method = "DefaultAzureCredential"
                except Exception as auth_err:
                    raise Exception(f"Failed to acquire Azure token: {auth_err}")

            if not token_value:
                raise Exception("Failed to acquire Azure AD token for Power BI API")

            # Try to infer tenant id from token if not provided
            if not tenant_id:
                inferred_tid = _extract_tenant_id_from_jwt(token_value)
                if inferred_tid:
                    tenant_id = inferred_tid

            # PRIORITY: Try the exact DAX Studio approach first (user confirmed this works)
            logger.info("Trying DAX Studio approach (Priority #1)")
            dax_studio_conn = (
                "Provider=MSOLAP;"
                f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{self.workspace_name};"
                f"Initial Catalog={self.model_name};"
                "User ID=;"
                f"Password={token_value};"
                "Persist Security Info=True;"
            )
            self.connection_string = dax_studio_conn
            logger.info(
                f"DAX Studio connection string: Provider=MSOLAP;Data Source=powerbi://api.powerbi.com/v1.0/myorg/{self.workspace_name};Initial Catalog={self.model_name};..."
            )
            try:
                self._test_connection()
                logger.info("DAX Studio approach successful!")
                return
            except Exception as dax_err:
                logger.error(f"DAX Studio approach failed: {dax_err}")
                self.last_error = f"DAX Studio approach failed: {dax_err}"

            # If a full connection string template is provided, try it next
            template = os.getenv("POWERBI_CONNSTR_TEMPLATE")
            logger.info(f"Template check: {'Found template' if template else 'No template'}")
            if template:
                # Replace token placeholder
                conn = template.replace("{TOKEN}", token_value)
                # Ensure ends with semicolon for Pyadomd
                if not conn.endswith(";"):
                    conn += ";"
                self.connection_string = conn
                logger.info(f"Using POWERBI_CONNSTR_TEMPLATE with {auth_method} token")
                logger.info(f"Template connection string: {conn}")
                try:
                    self._test_connection()
                    logger.info("Template connection successful!")
                    return
                except Exception as template_err:
                    logger.error(f"Template connection failed: {template_err}")
                    # Continue to fallback variants instead of failing completely
                    self.last_error = f"Template failed: {template_err}"

            # Endpoints and catalog overrides
            xmla_endpoint = f"powerbi://api.powerbi.com/v1.0/myorg/{self.workspace_name}"
            pbiazure_endpoint = "pbiazure://api.powerbi.com"
            data_source_override: Optional[str] = os.getenv("POWERBI_DATASOURCE")
            internal_catalog: Optional[str] = os.getenv("POWERBI_INTERNAL_CATALOG") or os.getenv(
                "POWERBI_INITIAL_CATALOG"
            )
            idp_triple: Optional[str] = os.getenv("POWERBI_IDP_TRIPLE")

            # Build a set of connection string candidates (prefer Excel-proven variants first)
            candidates = []

            # FORCE DAX Studio approach as the very first candidate (hardcoded for testing)
            candidates.append(
                [
                    "Provider=MSOLAP",
                    f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{self.workspace_name}",
                    f"Initial Catalog={self.model_name}",
                    "User ID=",
                    f"Password={token_value}",
                    "Persist Security Info=True",
                ]
            )

            # A) Minimal pbiazure + internal catalog (simple token auth)
            if internal_catalog:
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={pbiazure_endpoint}",
                        f"Initial Catalog={internal_catalog}",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )
            # 1) ClaimsToken with provided tenant
            if tenant_id:
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={xmla_endpoint}",
                        f"Initial Catalog={self.model_name}",
                        "Integrated Security=ClaimsToken",
                        f"Identity Provider=https://login.microsoftonline.com/{tenant_id}/oauth2/authorize",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )
            # 2) ClaimsToken with 'organizations'
            candidates.append(
                [
                    "Provider=MSOLAP",
                    f"Data Source={xmla_endpoint}",
                    f"Initial Catalog={self.model_name}",
                    "Integrated Security=ClaimsToken",
                    "Identity Provider=https://login.microsoftonline.com/organizations/oauth2/authorize",
                    "User ID=",
                    f"Password={token_value}",
                    "Persist Security Info=True",
                ]
            )
            # 3) ClaimsToken with 'common'
            candidates.append(
                [
                    "Provider=MSOLAP",
                    f"Data Source={xmla_endpoint}",
                    f"Initial Catalog={self.model_name}",
                    "Integrated Security=ClaimsToken",
                    "Identity Provider=https://login.microsoftonline.com/common/oauth2/authorize",
                    "User ID=",
                    f"Password={token_value}",
                    "Persist Security Info=True",
                ]
            )
            # 4) [Removed] Token as password with Authority ID (no ClaimsToken)
            # Historically attempted adding 'Authority ID' to guide tenant resolution, but
            # ADOMD.NET rejects this property with a parsing error. Do not include.
            # 5) Token as password without Authority ID
            candidates.append(
                [
                    "Provider=MSOLAP",
                    f"Data Source={xmla_endpoint}",
                    f"Initial Catalog={self.model_name}",
                    "User ID=",
                    f"Password={token_value}",
                    "Persist Security Info=True",
                ]
            )

            # 6) If Identity Provider triple explicitly provided (mirror Excel), try ClaimsToken with triple
            if idp_triple:
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={xmla_endpoint}",
                        f"Initial Catalog={self.model_name}",
                        "Integrated Security=ClaimsToken",
                        f"Identity Provider={idp_triple}",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )

                # 6a) pbiazure + internal catalog + ClaimsToken + Identity Provider triple (matches Excel ODC closely)
                if internal_catalog:
                    candidates.append(
                        [
                            "Provider=MSOLAP",
                            f"Data Source={pbiazure_endpoint}",
                            f"Initial Catalog={internal_catalog}",
                            "Integrated Security=ClaimsToken",
                            f"Identity Provider={idp_triple}",
                            "User ID=",
                            f"Password={token_value}",
                            "Persist Security Info=True",
                        ]
                    )
                # 6b) pbiazure + model display name + ClaimsToken + Identity Provider triple
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={pbiazure_endpoint}",
                        f"Initial Catalog={self.model_name}",
                        "Integrated Security=ClaimsToken",
                        f"Identity Provider={idp_triple}",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )

            # 7) Try pbiazure endpoint with minimal token style
            for ds in filter(None, [data_source_override, pbiazure_endpoint]):
                # 7a) Using display name as catalog
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={ds}",
                        f"Initial Catalog={self.model_name}",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )
                # 7b) If internal catalog override is provided (e.g., 'sobe_wowvirtualserver-<guid>'), try it
                if internal_catalog:
                    candidates.append(
                        [
                            "Provider=MSOLAP",
                            f"Data Source={ds}",
                            f"Initial Catalog={internal_catalog}",
                            "User ID=",
                            f"Password={token_value}",
                            "Persist Security Info=True",
                        ]
                    )

            # 8) Try powerbi endpoint with internal catalog (if provided)
            if internal_catalog:
                candidates.append(
                    [
                        "Provider=MSOLAP",
                        f"Data Source={xmla_endpoint}",
                        f"Initial Catalog={internal_catalog}",
                        "User ID=",
                        f"Password={token_value}",
                        "Persist Security Info=True",
                    ]
                )

            last_exc: Optional[Exception] = None
            for idx, parts in enumerate(candidates, start=1):
                try:
                    self.connection_string = ";".join(parts) + ";"
                    # Log key properties of the attempt for diagnostics
                    try:
                        ds = next((p for p in parts if p.startswith("Data Source=")), "Data Source=")
                        ic = next((p for p in parts if p.startswith("Initial Catalog=")), "Initial Catalog=")
                        is_claims = any(p.startswith("Integrated Security=ClaimsToken") for p in parts)
                        logger.info(f"Trying variant {idx} using {auth_method}: {ds}; {ic}; ClaimsToken={is_claims}")
                    except Exception:
                        pass
                    self._test_connection()
                    # success
                    break
                except Exception as e:
                    # Include variant context with the error to bubble up via last_error
                    try:
                        ds = next((p for p in parts if p.startswith("Data Source=")), "Data Source=")
                        ic = next((p for p in parts if p.startswith("Initial Catalog=")), "Initial Catalog=")
                        e = Exception(f"{e}\n[Variant {idx}] {ds}; {ic}")
                    except Exception:
                        pass
                    last_exc = e
                    continue

            if not self.connected and last_exc:
                raise last_exc

        except Exception as e:
            logger.error(f"Failed to setup connection: {e}")
            self.connected = False
            self.last_error = str(e)

    def _test_connection(self):
        """Test the PowerBI connection"""
        try:
            with Pyadomd(self.connection_string):
                self.connected = True
                logger.info("Successfully connected to PowerBI")
        except Exception as e:
            self.connected = False
            logger.error(f"Connection test failed: {e}")
            raise Exception(f"Connection test failed: {e}")

    def get_tables(self) -> List[str]:
        """Get list of table names"""
        if not self.connected:
            raise Exception("Not connected to PowerBI")

        try:
            tables = []
            with Pyadomd(self.connection_string) as pyadomd_conn:
                adomd_connection = pyadomd_conn.conn
                tables_dataset = adomd_connection.GetSchemaDataSet(AdomdSchemaGuid.Tables, None)

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
                            tables.append(table_name)

            self.tables = tables
            return tables

        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            raise Exception(f"Failed to get tables: {e}")

    def execute_query(self, query: str) -> str:
        """Execute a DAX query and return results as formatted string"""
        if not self.connected:
            raise Exception("Not connected to PowerBI")

        try:
            with Pyadomd(self.connection_string) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # Get rows
                rows = cursor.fetchall()

                if not rows:
                    return "No data returned"

                # Format as simple table
                result = []
                if columns:
                    result.append(" | ".join(columns))
                    result.append("-" * (len(" | ".join(columns))))

                for row in rows:
                    result.append(" | ".join(str(cell) if cell is not None else "NULL" for cell in row))

                return "\n".join(result)

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise Exception(f"Query execution failed: {e}")

    def get_table_schema(self, table_name: str) -> str:
        """Get schema information for a specific table"""
        if not self.connected:
            raise Exception("Not connected to PowerBI")

        try:
            with Pyadomd(self.connection_string) as pyadomd_conn:
                adomd_connection = pyadomd_conn.conn
                columns_dataset = adomd_connection.GetSchemaDataSet(AdomdSchemaGuid.Columns, None)

                schema_info = []
                tables_list_obj = getattr(columns_dataset, "Tables", None)
                if tables_list_obj and len(tables_list_obj) > 0:
                    schema_table = tables_list_obj[0]
                    for row in schema_table.Rows:
                        if row["TABLE_NAME"] == table_name:
                            column_name = row["COLUMN_NAME"]
                            data_type = row["DATA_TYPE"]
                            schema_info.append(f"• {column_name} ({data_type})")

                if schema_info:
                    return "\n".join(schema_info)
                else:
                    return f"No schema information found for table '{table_name}'"

        except Exception as e:
            logger.error(f"Failed to get table schema: {e}")
            raise Exception(f"Failed to get table schema: {e}")

    def get_relationships(self) -> List[str]:
        """Get all relationships in the data model"""
        if not self.connected:
            raise Exception("Not connected to PowerBI")

        try:
            relationships = []
            # Simple DAX query to get relationship information
            query = """
            EVALUATE
            ADDCOLUMNS(
                TMSCHEMA_RELATIONSHIPS(),
                "RelationshipInfo",
                [FromTable] & "[" & [FromColumn] & "] -> " & [ToTable] & "[" & [ToColumn] & "]"
            )
            """
            result = self.execute_query(query)
            # Parse the result to extract relationship info
            lines = result.split("\n")
            for line in lines[2:]:  # Skip header lines
                if line.strip() and "->" in line:
                    relationships.append(line.split("|")[-1].strip())

            return relationships if relationships else ["No relationships found"]

        except Exception as e:
            logger.error(f"Failed to get relationships: {e}")
            # Fallback to simple approach
            return [f"Error getting relationships: {e}"]

    def get_measures(self) -> List[str]:
        """Get all measures in the data model"""
        if not self.connected:
            raise Exception("Not connected to PowerBI")

        try:
            measures = []
            # Use DAX to get measures
            query = "EVALUATE TMSCHEMA_MEASURES()"
            result = self.execute_query(query)

            # Parse the result to extract measure names
            lines = result.split("\n")
            for line in lines[2:]:  # Skip header lines
                if line.strip() and "|" in line:
                    parts = line.split("|")
                    if len(parts) > 1:
                        measure_name = parts[1].strip()  # Assuming measure name is in second column
                        if measure_name and not measure_name.startswith("-"):
                            measures.append(measure_name)

            return measures if measures else ["No measures found"]

        except Exception as e:
            logger.error(f"Failed to get measures: {e}")
            # Fallback approach
            try:
                with Pyadomd(self.connection_string) as pyadomd_conn:
                    adomd_connection = pyadomd_conn.conn
                    measures_dataset = adomd_connection.GetSchemaDataSet(AdomdSchemaGuid.Measures, None)

                    tables_list_obj = getattr(measures_dataset, "Tables", None)
                    if tables_list_obj and len(tables_list_obj) > 0:
                        schema_table = tables_list_obj[0]
                        for row in schema_table.Rows:
                            measure_name = row["MEASURE_NAME"]
                            if not measure_name.startswith("_"):
                                measures.append(measure_name)

                return measures if measures else ["No measures found"]
            except:
                return [f"Error getting measures: {e}"]

    def is_connected(self) -> bool:
        """Check if connected to PowerBI"""
        return self.connected
