import json

from hello_world import app


def test_lambda_handler_health_check():
    event = {
        "httpMethod": "GET",
        "path": "/health",
        "headers": {},
        "body": None
    }

    result = app.lambda_handler(event, None)
    data = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert data["status"] == "healthy"
    assert data["service"] == "CloudTask API"
