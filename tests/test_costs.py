import json
import os
import pytest
from unittest.mock import patch, MagicMock
from verinfast.cloud.aws.costs import runAws

# Mock AWS CLI responses
MOCK_RESPONSE_1 = {
    "ResultsByTime": [
        {
            "TimePeriod": {"Start": "2024-01-01"},
            "Groups": [
                {
                    "Keys": ["AWS Service 1"],
                    "Metrics": {
                        "BlendedCost": {
                            "Amount": "100.00",
                            "Unit": "USD"
                        }
                    }
                }
            ]
        }
    ],
    "NextPageToken": "mock-token-123"
}

MOCK_RESPONSE_2 = {
    "ResultsByTime": [
        {
            "TimePeriod": {"Start": "2024-01-01"},
            "Groups": [
                {
                    "Keys": ["AWS Service 2"],
                    "Metrics": {
                        "BlendedCost": {
                            "Amount": "200.00",
                            "Unit": "USD"
                        }
                    }
                }
            ]
        }
    ]
}


@pytest.fixture
def mock_subprocess_run():
    with patch('subprocess.run') as mock_run:
        # First call returns response with NextPageToken
        first_response = MagicMock()
        first_response.stdout.decode.return_value = json.dumps(MOCK_RESPONSE_1)

        # Second call returns response without NextPageToken
        second_response = MagicMock()
        second_response.stdout.decode.return_value = json.dumps(
            MOCK_RESPONSE_2)

        mock_run.side_effect = [first_response, second_response]
        yield mock_run


def test_aws_costs_pagination(mock_subprocess_run, tmp_path):
    # Mock logger
    mock_logger = MagicMock()

    # Run the function
    output_file = runAws(
        targeted_account="123456789",
        start="2024-01-01",
        end="2024-01-31",
        path_to_output=str(tmp_path),
        log=mock_logger,
        profile="test-profile"
    )

    # Verify subprocess.run was called twice (pagination)
    assert mock_subprocess_run.call_count == 2

    # Verify the second call included the NextPageToken
    second_call_args = mock_subprocess_run.call_args_list[1][0][0]
    assert '--next-token="mock-token-123"' in second_call_args

    # Verify the output file exists and contains combined data
    assert os.path.exists(output_file)

    with open(output_file, 'r') as f:
        result = json.load(f)

    # Verify metadata
    assert result["metadata"]["provider"] == "aws"
    assert result["metadata"]["account"] == "123456789"

    # Verify combined data
    assert len(result["data"]) == 2
    assert result["data"][0]["Cost"] == "100.00"
    assert result["data"][1]["Cost"] == "200.00"
    assert result["data"][0]["Group"] == "AWS Service 1"
    assert result["data"][1]["Group"] == "AWS Service 2"


def test_aws_costs_no_pagination(mock_subprocess_run, tmp_path):
    # Override mock to return only one response without NextPageToken
    mock_subprocess_run.side_effect = None
    response = MagicMock()
    response.stdout.decode.return_value = json.dumps(MOCK_RESPONSE_2)
    mock_subprocess_run.return_value = response

    mock_logger = MagicMock()

    output_file = runAws(
        targeted_account="123456789",
        start="2024-01-01",
        end="2024-01-31",
        path_to_output=str(tmp_path),
        log=mock_logger,
        profile="test-profile"
    )

    # Verify subprocess.run was called only once (no pagination)
    assert mock_subprocess_run.call_count == 1

    # Verify the output file exists and contains correct data
    assert os.path.exists(output_file)

    with open(output_file, 'r') as f:
        result = json.load(f)

    # Verify data
    assert len(result["data"]) == 1
    assert result["data"][0]["Cost"] == "200.00"
    assert result["data"][0]["Group"] == "AWS Service 2"
