"""Unit tests for the PowerBIRestClient helper."""

import json
import os
import sys
from unittest.mock import MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from powerbi_rest_client import POWER_BI_SCOPE, PowerBIRestClient, PowerBIRestError


@pytest.fixture
def mock_connector():
    connector = MagicMock()
    connector.acquire_token.return_value = "rest-token"
    return connector


@pytest.fixture
def mock_session():
    return MagicMock()


def make_response(payload, *, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = json.dumps(payload)
    return response


def test_list_workspaces_filters_results(mock_connector, mock_session):
    payload = {
        "value": [
            {"id": "1", "name": "Analytics"},
            {"id": "2", "name": "Finance"},
        ]
    }
    mock_session.request.return_value = make_response(payload)

    client = PowerBIRestClient(mock_connector, MagicMock(), session=mock_session)

    result = client.list_workspaces(search="Ana")

    mock_connector.acquire_token.assert_called_once_with(scope=POWER_BI_SCOPE, force_refresh=False)
    mock_session.request.assert_called_once_with(
        method="GET",
        url="https://api.powerbi.com/v1.0/myorg/groups",
        headers={
            "Authorization": "Bearer rest-token",
            "Content-Type": "application/json",
        },
        params={},
        json=None,
        timeout=30.0,
    )

    assert result["items"] == [{"id": "1", "name": "Analytics"}]
    assert result["raw"] == payload


def test_execute_query_builds_payload_and_preview(mock_connector, mock_session):
    payload = {
        "results": [
            {
                "tables": [
                    {
                        "name": "Table",
                        "rows": [{"MeasureValue": 42}, {"MeasureValue": 43}],
                    }
                ]
            }
        ]
    }
    mock_session.request.return_value = make_response(payload)

    client = PowerBIRestClient(mock_connector, MagicMock(), session=mock_session)
    result = client.execute_query(dataset_id="abc", measure_name="Revenue")

    assert result["query"] == 'EVALUATE ROW("MeasureValue", [Revenue])'
    assert result["preview"][0]["headers"] == ["MeasureValue"]
    assert result["preview"][0]["row_count"] == 2
    assert mock_session.request.call_args.kwargs["json"]["queries"][0]["query"] == 'EVALUATE ROW("MeasureValue", [Revenue])'


def test_request_refreshes_token_on_401(mock_connector, mock_session):
    mock_session.request.side_effect = [
        make_response({}, status_code=401),
        make_response({"value": []}),
    ]
    mock_connector.acquire_token.side_effect = ["token-a", "token-b"]

    client = PowerBIRestClient(mock_connector, MagicMock(), session=mock_session)
    result = client.list_workspaces()

    assert result["items"] == []
    assert mock_session.request.call_count == 2
    assert mock_connector.acquire_token.call_args_list == [
        call(scope=POWER_BI_SCOPE, force_refresh=False),
        call(scope=POWER_BI_SCOPE, force_refresh=True),
    ]


def test_execute_query_requires_query_or_measure(mock_connector, mock_session):
    client = PowerBIRestClient(mock_connector, MagicMock(), session=mock_session)

    with pytest.raises(PowerBIRestError):
        client.execute_query(dataset_id="abc")


def test_execute_query_rejects_both_query_and_measure(mock_connector, mock_session):
    client = PowerBIRestClient(mock_connector, MagicMock(), session=mock_session)

    with pytest.raises(PowerBIRestError):
        client.execute_query(dataset_id="abc", query="EVALUATE ROW()", measure_name="Sales")
