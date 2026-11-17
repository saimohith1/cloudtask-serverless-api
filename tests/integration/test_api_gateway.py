import os

import boto3
import pytest
import requests


@pytest.fixture
def api_gateway_url():
    stack_name = os.environ.get("AWS_SAM_STACK_NAME")

    if not stack_name:
        pytest.skip("AWS integration test skipped: no deployed SAM stack configured")

    client = boto3.client("cloudformation")

    response = client.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]

    api_outputs = [
        output["OutputValue"]
        for output in outputs
        if output["OutputKey"] == "CloudTaskApi"
    ]

    if not api_outputs:
        pytest.fail(f"CloudTaskApi output not found in stack: {stack_name}")

    return api_outputs[0].rstrip("/")


class TestApiGateway:

    def test_health_endpoint(self, api_gateway_url):
        response = requests.get(
            f"{api_gateway_url}/health",
            timeout=10
        )

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "CloudTask API"
