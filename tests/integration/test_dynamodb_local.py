from datetime import datetime, timezone
from uuid import uuid4

from hello_world import repository


def make_task(user_id, title="Integration test task"):
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "user_id": user_id,
        "task_id": str(uuid4()),
        "title": title,
        "description": "Created by Pytest against DynamoDB Local",
        "status": "PENDING",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_create_task_persists_record(dynamodb_table, test_user_id):
    task = make_task(test_user_id)
    repository.create_task(task)

    stored = dynamodb_table.get_item(
        Key={"user_id": test_user_id, "task_id": task["task_id"]}
    ).get("Item")

    assert stored is not None
    assert stored["title"] == task["title"]


def test_get_task_returns_existing_record(dynamodb_table, test_user_id):
    task = make_task(test_user_id)
    repository.create_task(task)

    result = repository.get_task(test_user_id, task["task_id"])

    assert result is not None
    assert result["title"] == task["title"]


def test_get_missing_task_returns_none(test_user_id):
    assert repository.get_task(test_user_id, "non-existent-task") is None


def test_list_tasks_is_scoped_to_user(dynamodb_table, test_user_id):
    own_task = make_task(test_user_id, "My task")
    other_user_id = f"pytest-other-{uuid4()}"
    other_task = make_task(other_user_id, "Another user's task")

    repository.create_task(own_task)
    repository.create_task(other_task)

    try:
        results = repository.list_tasks(test_user_id)

        assert len(results) == 1
        assert results[0]["task_id"] == own_task["task_id"]
        assert all(task["user_id"] == test_user_id for task in results)
    finally:
        repository.delete_task(other_user_id, other_task["task_id"])


def test_update_task_persists_changes(dynamodb_table, test_user_id):
    task = make_task(test_user_id)
    repository.create_task(task)

    new_timestamp = datetime.now(timezone.utc).isoformat()

    result = repository.update_task(
        test_user_id,
        task["task_id"],
        {
            "title": "Updated integration task",
            "status": "IN_PROGRESS",
            "updated_at": new_timestamp,
        },
    )

    stored = dynamodb_table.get_item(
        Key={"user_id": test_user_id, "task_id": task["task_id"]}
    ).get("Item")

    assert result is not None
    assert stored["title"] == "Updated integration task"
    assert stored["status"] == "IN_PROGRESS"


def test_update_missing_task_returns_none(test_user_id):
    result = repository.update_task(
        test_user_id,
        "non-existent-task",
        {
            "title": "Should not exist",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert result is None


def test_delete_task_removes_record(dynamodb_table, test_user_id):
    task = make_task(test_user_id)
    repository.create_task(task)

    deleted = repository.delete_task(test_user_id, task["task_id"])

    remaining = dynamodb_table.get_item(
        Key={"user_id": test_user_id, "task_id": task["task_id"]}
    ).get("Item")

    assert deleted is not None
    assert deleted["task_id"] == task["task_id"]
    assert remaining is None


def test_delete_missing_task_returns_none(test_user_id):
    assert repository.delete_task(test_user_id, "non-existent-task") is None
