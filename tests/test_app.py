import json
import pytest
from hello_world import app


@pytest.fixture
def fake_repository(monkeypatch):
    """Provide isolated fake DynamoDB operations."""
    store = {}

    def create_task(task):
        store[(task["user_id"], task["task_id"])] = dict(task)
        return task

    def list_tasks(user_id):
        return [
            dict(task)
            for (uid, _), task in store.items()
            if uid == user_id
        ]

    def get_task(user_id, task_id):
        task = store.get((user_id, task_id))
        return dict(task) if task else None

    def update_task(user_id, task_id, updates):
        key = (user_id, task_id)

        if key not in store:
            return None

        store[key].update(updates)
        return dict(store[key])

    def delete_task(user_id, task_id):
        return store.pop((user_id, task_id), None)

    monkeypatch.setattr(app.repository, "create_task", create_task)
    monkeypatch.setattr(app.repository, "list_tasks", list_tasks)
    monkeypatch.setattr(app.repository, "get_task", get_task)
    monkeypatch.setattr(app.repository, "update_task", update_task)
    monkeypatch.setattr(app.repository, "delete_task", delete_task)

    return store


def make_event(method, path, body=None, user_id="user-123"):
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": {},
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id} if user_id else {}
            }
        }
    }


def test_health_check():
    event = make_event("GET", "/health", user_id=None)
    result = app.lambda_handler(event, None)

    data = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert data["status"] == "healthy"


def test_hello_endpoint_is_public():
    event = make_event("GET", "/hello", user_id=None)
    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200


def test_missing_identity_returns_401():
    event = make_event("GET", "/tasks", user_id=None)
    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 401


def test_create_task(fake_repository):
    event = make_event("POST", "/tasks", {
        "title": "Learn AWS Lambda",
        "description": "Build CloudTask",
        "status": "PENDING"
    })

    result = app.lambda_handler(event, None)
    data = json.loads(result["body"])

    assert result["statusCode"] == 201
    assert data["task"]["title"] == "Learn AWS Lambda"
    assert data["task"]["status"] == "PENDING"
    assert data["task"]["user_id"] == "user-123"
    assert "task_id" in data["task"]


def test_list_tasks(fake_repository):
    create_event = make_event(
        "POST",
        "/tasks",
        {"title": "Learn DynamoDB"}
    )
    app.lambda_handler(create_event, None)

    result = app.lambda_handler(
        make_event("GET", "/tasks"),
        None
    )
    data = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert data["count"] == 1


def test_user_isolation(fake_repository):
    app.lambda_handler(
        make_event("POST", "/tasks", {"title": "User A task"}, "user-A"),
        None
    )
    app.lambda_handler(
        make_event("POST", "/tasks", {"title": "User B task"}, "user-B"),
        None
    )

    result_a = app.lambda_handler(
        make_event("GET", "/tasks", user_id="user-A"),
        None
    )
    result_b = app.lambda_handler(
        make_event("GET", "/tasks", user_id="user-B"),
        None
    )

    tasks_a = json.loads(result_a["body"])["tasks"]
    tasks_b = json.loads(result_b["body"])["tasks"]

    assert len(tasks_a) == 1
    assert len(tasks_b) == 1
    assert tasks_a[0]["title"] == "User A task"
    assert tasks_b[0]["title"] == "User B task"


def test_get_task(fake_repository):
    created = app.lambda_handler(
        make_event("POST", "/tasks", {"title": "Get me"}),
        None
    )
    task_id = json.loads(created["body"])["task"]["task_id"]

    event = make_event("GET", f"/tasks/{task_id}")
    event["pathParameters"] = {"task_id": task_id}

    result = app.lambda_handler(event, None)
    data = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert data["task"]["title"] == "Get me"


def test_user_cannot_get_another_users_task(fake_repository):
    created = app.lambda_handler(
        make_event("POST", "/tasks", {"title": "Private task"}, "user-A"),
        None
    )
    task_id = json.loads(created["body"])["task"]["task_id"]

    event = make_event("GET", f"/tasks/{task_id}", user_id="user-B")
    event["pathParameters"] = {"task_id": task_id}

    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 404


def test_update_task(fake_repository):
    created = app.lambda_handler(
        make_event("POST", "/tasks", {"title": "Original"}),
        None
    )
    task_id = json.loads(created["body"])["task"]["task_id"]

    event = make_event(
        "PUT",
        f"/tasks/{task_id}",
        {"title": "Updated", "status": "IN_PROGRESS"}
    )
    event["pathParameters"] = {"task_id": task_id}

    result = app.lambda_handler(event, None)
    data = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert data["task"]["title"] == "Updated"
    assert data["task"]["status"] == "IN_PROGRESS"


def test_delete_task(fake_repository):
    created = app.lambda_handler(
        make_event("POST", "/tasks", {"title": "Delete me"}),
        None
    )
    task_id = json.loads(created["body"])["task"]["task_id"]

    event = make_event("DELETE", f"/tasks/{task_id}")
    event["pathParameters"] = {"task_id": task_id}

    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert ( "user-123", task_id) not in fake_repository


def test_missing_title(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {"description": "No title"}),
        None
    )

    assert result["statusCode"] == 400


def test_invalid_json(fake_repository):
    event = make_event("POST", "/tasks")
    event["body"] = "{invalid json"

    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 400


def test_json_array_rejected(fake_repository):
    event = make_event("POST", "/tasks")
    event["body"] = '["task1", "task2"]'

    result = app.lambda_handler(event, None)

    assert result["statusCode"] == 400


def test_invalid_status(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {
            "title": "Test task",
            "status": "INVALID"
        }),
        None
    )

    assert result["statusCode"] == 400


def test_non_string_status(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {
            "title": "Test task",
            "status": ["PENDING"]
        }),
        None
    )

    assert result["statusCode"] == 400


def test_invalid_description_type(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {
            "title": "Test task",
            "description": 123
        }),
        None
    )

    assert result["statusCode"] == 400


def test_title_too_long(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {
            "title": "A" * 121
        }),
        None
    )

    assert result["statusCode"] == 400


def test_unknown_route(fake_repository):
    result = app.lambda_handler(
        make_event("GET", "/unknown"),
        None
    )

    assert result["statusCode"] == 404


def test_lowercase_status_normalized(fake_repository):
    result = app.lambda_handler(
        make_event("POST", "/tasks", {
            "title": "Test task",
            "status": "pending"
        }),
        None
    )

    data = json.loads(result["body"])

    assert result["statusCode"] == 201
    assert data["task"]["status"] == "PENDING"


def test_http_api_jwt_claims_supported():
    event = {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "jwt-user-456"}
                }
            }
        }
    }

    assert app.get_user_id(event) == "jwt-user-456"


def test_missing_sub_returns_none():
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {}
            }
        }
    }

    assert app.get_user_id(event) is None
