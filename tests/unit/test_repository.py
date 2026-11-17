from botocore.exceptions import ClientError

from hello_world import repository


class FakeTable:

    def __init__(self):
        self.items = []
        self.query_calls = []
        self.last_get_key = None
        self.last_update = None
        self.last_delete = None
        self.update_error = None
        self.delete_error = None
        self.query_pages = [
            {
                "Items": [{"user_id": "user-1", "task_id": "task-1"}],
                "LastEvaluatedKey": {
                    "user_id": "user-1",
                    "task_id": "task-1"
                }
            },
            {
                "Items": [{"user_id": "user-1", "task_id": "task-2"}]
            }
        ]

    def put_item(self, Item):
        self.items.append(Item)

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self.query_pages[len(self.query_calls) - 1]

    def get_item(self, Key):
        self.last_get_key = Key
        return {
            "Item": {
                "user_id": Key["user_id"],
                "task_id": Key["task_id"],
                "title": "Test task"
            }
        }

    def update_item(self, **kwargs):
        self.last_update = kwargs

        if self.update_error:
            raise self.update_error

        return {
            "Attributes": {
                "user_id": kwargs["Key"]["user_id"],
                "task_id": kwargs["Key"]["task_id"],
                "title": "Updated task"
            }
        }

    def delete_item(self, **kwargs):
        self.last_delete = kwargs

        if self.delete_error:
            raise self.delete_error

        return {
            "Attributes": {
                "user_id": kwargs["Key"]["user_id"],
                "task_id": kwargs["Key"]["task_id"],
                "title": "Deleted task"
            }
        }


def conditional_error(operation):
    return ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Task does not exist"
            }
        },
        operation
    )


def test_create_task(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(repository, "get_table", lambda: table)

    task = {
        "user_id": "user-1",
        "task_id": "task-1",
        "title": "Learn DynamoDB"
    }

    result = repository.create_task(task)

    assert result == task
    assert table.items == [task]


def test_list_tasks_pagination(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(repository, "get_table", lambda: table)

    result = repository.list_tasks("user-1")

    assert len(result) == 2
    assert result[0]["task_id"] == "task-1"
    assert result[1]["task_id"] == "task-2"
    assert len(table.query_calls) == 2
    assert "ExclusiveStartKey" not in table.query_calls[0]
    assert table.query_calls[1]["ExclusiveStartKey"] == {
        "user_id": "user-1",
        "task_id": "task-1"
    }


def test_get_task_uses_both_keys(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(repository, "get_table", lambda: table)

    result = repository.get_task("user-1", "task-1")

    assert result["title"] == "Test task"
    assert table.last_get_key == {
        "user_id": "user-1",
        "task_id": "task-1"
    }


def test_update_task_uses_both_keys(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(repository, "get_table", lambda: table)

    updates = {
        "title": "Updated task",
        "updated_at": "2026-11-13T12:00:00+00:00"
    }

    result = repository.update_task("user-1", "task-1", updates)

    assert result["title"] == "Updated task"
    assert table.last_update["Key"] == {
        "user_id": "user-1",
        "task_id": "task-1"
    }
    assert "updated_at" in table.last_update["UpdateExpression"]
    assert table.last_update["ConditionExpression"] is not None


def test_update_missing_task_returns_none(monkeypatch):
    table = FakeTable()
    table.update_error = conditional_error("UpdateItem")
    monkeypatch.setattr(repository, "get_table", lambda: table)

    result = repository.update_task(
        "user-1",
        "missing-task",
        {
            "title": "Updated task",
            "updated_at": "2026-11-13T12:00:00+00:00"
        }
    )

    assert result is None


def test_delete_task_uses_both_keys(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(repository, "get_table", lambda: table)

    result = repository.delete_task("user-1", "task-1")

    assert result["task_id"] == "task-1"
    assert table.last_delete["Key"] == {
        "user_id": "user-1",
        "task_id": "task-1"
    }
    assert table.last_delete["ConditionExpression"] is not None


def test_delete_missing_task_returns_none(monkeypatch):
    table = FakeTable()
    table.delete_error = conditional_error("DeleteItem")
    monkeypatch.setattr(repository, "get_table", lambda: table)

    result = repository.delete_task("user-1", "missing-task")

    assert result is None
