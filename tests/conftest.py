"""Pytest conftest: add project root to path and mock ComfyUI deps so extension modules can be imported."""
import sys
import os

# Project root (parent of tests/)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Mock server before any extension code imports it
class _MockInstance:
    app = object()
    routes = object()

class _MockPromptServer:
    instance = _MockInstance()

if "server" not in sys.modules:
    _server = type(sys)("server")
    _server.PromptServer = _MockPromptServer
    sys.modules["server"] = _server

# Mock folder_paths so workflow_routes can be imported
if "folder_paths" not in sys.modules:
    _fp = type(sys)("folder_paths")
    _fp.base_path = os.path.join(_root, "fake_comfy_root")
    sys.modules["folder_paths"] = _fp
