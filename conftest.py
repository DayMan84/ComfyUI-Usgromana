"""Root conftest: prevent pytest from collecting the extension's __init__.py as a test module."""
def pytest_ignore_collect(collection_path, config):
    """Ignore the project root's __init__.py so it is not loaded as a test module."""
    try:
        from pathlib import Path
        p = Path(collection_path).resolve()
        root = config.rootpath.resolve()
        if p.name == "__init__.py" and p.parent == root:
            return True
    except Exception:
        pass
    return False
