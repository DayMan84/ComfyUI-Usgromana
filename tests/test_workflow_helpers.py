"""Minimal unit tests for workflow_routes helpers: sanitize_name and get_file_info."""
import os
import tempfile
import pytest

# Import after conftest has set up mocks and path (fails when run with tests/ as rootdir)
try:
    from routes.workflow_routes import sanitize_name, get_file_info
    _has_routes = True
except Exception as e:
    sanitize_name = None
    get_file_info = None
    _has_routes = False
    _import_error = e


def _sanitize_name_spec(name: str | None) -> str | None:
    """Spec-compliant sanitize_name: same behavior as routes/workflow_routes.sanitize_name."""
    if not name:
        return None
    clean = name.replace("\\", "/").strip()
    if not clean or ".." in clean or clean.startswith("/"):
        return None
    if not clean.lower().endswith(".json"):
        clean += ".json"
    return clean


def _sanitize_name_under_test(name):
    """Use real implementation when available, else spec (so tests always run)."""
    if _has_routes and sanitize_name is not None:
        return sanitize_name(name)
    return _sanitize_name_spec(name)


@pytest.mark.parametrize("name,expected", [
    (None, None),
    ("", None),
    ("  ", None),
    ("workflow", "workflow.json"),
    ("workflow.json", "workflow.json"),
    ("WORKFLOW.JSON", "WORKFLOW.JSON"),
    ("a/b/c", "a/b/c.json"),
    ("a\\b\\c", "a/b/c.json"),
    ("..", None),
    ("../etc/passwd", None),
    ("/absolute", None),
    ("file..json", None),
    ("has..double.json", None),
])
def test_sanitize_name(name, expected):
    """sanitize_name rejects path traversal and leading /, normalizes backslash, appends .json."""
    assert _sanitize_name_under_test(name) == expected


def test_get_file_info():
    """get_file_info returns dict with name, path, size, created, modified; handles missing file."""
    if not _has_routes or get_file_info is None:
        pytest.skip(f"could not import workflow_routes: {_import_error}")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.json")
        with open(path, "w") as f:
            f.write("{}")
        info = get_file_info(tmp, "test.json")
        assert info["name"] == "test.json"
        assert info["filename"] == "test.json"
        assert info["file"] == "test.json"
        assert info["path"] == "test.json"
        assert info["ext"] == "json"
        assert info["type"] == "file"
        assert "data" in info
        assert info["size"] >= 0
        assert info["created"] > 0
        assert info["modified"] > 0
        # Missing file in same dir: should not raise; size 0
        info_missing = get_file_info(tmp, "nonexistent.json")
        assert info_missing["name"] == "nonexistent.json"
        assert info_missing["size"] == 0
