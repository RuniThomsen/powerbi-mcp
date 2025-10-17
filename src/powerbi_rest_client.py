"""Power BI REST API helper client used by MCP tools."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import requests

POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

if TYPE_CHECKING:  # pragma: no cover - typing only
    from server_enhanced import AzureAuthenticator, PowerBIConnector

logger = logging.getLogger(__name__)


class PowerBIRestError(RuntimeError):
    """Raised when a Power BI REST API call fails."""


class PowerBIRestClient:
    """Minimal REST client that reuses the MCP connector authentication."""

    API_ROOT = "https://api.powerbi.com/v1.0/myorg"

    def __init__(
        self,
        connector: "PowerBIConnector",
        authenticator: "AzureAuthenticator",
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> None:
        self._connector = connector
        self._authenticator = authenticator
        self._session = session or requests.Session()
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_workspaces(self, top: Optional[int] = None, search: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if top:
            params["$top"] = max(1, min(int(top), 5000))

        url = f"{self.API_ROOT}/groups"
        data = self._request("GET", url, params=params)
        items: List[Dict[str, Any]] = data.get("value", [])  # type: ignore[assignment]

        if search:
            query = search.lower()
            items = [item for item in items if query in (item.get("name") or "").lower()]

        return {"items": items, "raw": data}

    def list_datasets(self, workspace_id: Optional[str] = None, top: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if top:
            params["$top"] = max(1, min(int(top), 5000))

        if workspace_id:
            url = f"{self.API_ROOT}/groups/{workspace_id}/datasets"
        else:
            url = f"{self.API_ROOT}/datasets"

        data = self._request("GET", url, params=params)
        items: List[Dict[str, Any]] = data.get("value", [])  # type: ignore[assignment]
        return {"items": items, "raw": data}

    def execute_query(
        self,
        dataset_id: str,
        workspace_id: Optional[str] = None,
        query: Optional[str] = None,
        measure_name: Optional[str] = None,
        measure_label: str = "MeasureValue",
        include_nulls: bool = False,
        impersonated_user: Optional[str] = None,
        preview_rows: int = 10,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        dax_query = self._resolve_query(query=query, measure_name=measure_name, measure_label=measure_label)

        payload: Dict[str, Any] = {
            "queries": [{"query": dax_query}],
            "serializerSettings": {"includeNulls": bool(include_nulls)},
        }
        if impersonated_user:
            payload["impersonatedUserName"] = impersonated_user

        if workspace_id:
            url = f"{self.API_ROOT}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
        else:
            url = f"{self.API_ROOT}/datasets/{dataset_id}/executeQueries"

        data = self._request("POST", url, json_payload=payload, access_token=access_token)
        results: List[Dict[str, Any]] = data.get("results", [])  # type: ignore[assignment]
        preview = self._build_preview(results, preview_rows)

        return {
            "results": results,
            "preview": preview,
            "raw": data,
            "query": dax_query,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_token(self, *, access_token: Optional[str] = None, force_refresh: bool = False) -> str:
        if access_token:
            return access_token
        try:
            return self._connector.acquire_token(scope=POWER_BI_SCOPE, force_refresh=force_refresh)
        except Exception as exc:  # pragma: no cover - bubble up as REST error
            raise PowerBIRestError(str(exc)) from exc

    def _headers(self, *, access_token: Optional[str] = None) -> Dict[str, str]:
        token = self._ensure_token(access_token=access_token)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        headers = self._headers(access_token=access_token)
        response = self._send(method, url, headers, params=params, json_payload=json_payload)

        # Retry once on unauthorized to refresh token
        if response.status_code == 401 and access_token is None:
            headers = self._headers(access_token=self._ensure_token(force_refresh=True))
            response = self._send(method, url, headers, params=params, json_payload=json_payload)

        return self._parse_response(response)

    def _send(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        try:
            return self._session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_payload,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure path
            raise PowerBIRestError(f"Request to {url} failed: {exc}") from exc

    @staticmethod
    def _parse_response(response: requests.Response) -> Dict[str, Any]:
        if response.status_code >= 400:
            raise PowerBIRestError(
                f"Power BI REST API call failed ({response.status_code}): {PowerBIRestClient._extract_error(response)}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PowerBIRestError(f"Failed to decode JSON response: {exc}") from exc

    @staticmethod
    def _extract_error(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text

        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return message
        return response.text

    @staticmethod
    def _resolve_query(
        *,
        query: Optional[str],
        measure_name: Optional[str],
        measure_label: str,
    ) -> str:
        provided = sum(bool(v) for v in (query, measure_name))
        if provided == 0:
            raise PowerBIRestError("Provide either 'query' or 'measure_name'.")
        if provided > 1:
            raise PowerBIRestError("Specify only one of 'query' or 'measure_name'.")

        if query:
            return query.strip()

        assert measure_name is not None
        label = measure_label or "MeasureValue"
        return f'EVALUATE ROW("{label}", [{measure_name}])'

    @staticmethod
    def _build_preview(results: List[Dict[str, Any]], max_rows: int) -> List[Dict[str, Any]]:
        preview: List[Dict[str, Any]] = []
        for result in results:
            tables = result.get("tables") or []
            for table in tables:
                rows = table.get("rows") or []
                headers = list(rows[0].keys()) if rows else []
                preview.append(
                    {
                        "name": table.get("name"),
                        "row_count": len(rows),
                        "headers": headers,
                        "rows": rows[: max_rows if max_rows > 0 else len(rows)],
                    }
                )
        return preview

