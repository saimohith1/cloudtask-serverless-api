import os
from uuid import uuid4
from urllib.parse import urlparse

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


@pytest.fixture
def dynamodb_table(monkeypatch):
    """Connect exclusively to DynamoDB Local."""

    endpoint = "http://localhost:8000"
    parsed = urlparse(endpoint)

    # Safety guard: never allow integration tests to access AWS.
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        pytest.fail("Integration tests must use local DynamoDB.")

    monkeypatch.setenv("TASKS_TABLE", "CloudTaskTasks")
    monkeypatch.setenv("DYNAMODB_ENDPOINT_URL", endpoint)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "local")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="ap-south-1",
        aws_access_key_id="local",
        aws_secret_access_key="local"
    )

    table = dynamodb.Table("CloudTaskTasks")

    try:
        table.load()
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            pytest.fail(
                "CloudTaskTasks table does not exist in DynamoDB Local. "
                "Run scripts/create_local_table.py first."
            )
        raise

    yield table


@pytest.fixture
def test_user_id(dynamodb_table):
    """Generate a unique test user and clean up their records."""

    user_id = f"pytest-{uuid4()}"

    yield user_id

    response = dynamodb_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id)
    )

    for item in response.get("Items", []):
        dynamodb_table.delete_item(
            Key={
                "user_id": item["user_id"],
                "task_id": item["task_id"]
            }
        )
