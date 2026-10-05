"""Regression tests for issue #26: later users' images saved into the first user's folder.

The tests mirror ComfyUI's node-object cache and SaveImage.output_dir, plus the
process-wide user fallback that Generated-tab polling used to overwrite.
"""
import asyncio
import contextvars
import heapq
import os
import sys
import threading
import types

import folder_paths
import pytest

USER_A = "ca169df5-cb3e-4b13-ab12-0032e8475d8f"
USER_B = "11111111-2222-4333-8444-555555555555"
USER_C = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


class _Users:
    def __init__(self):
        self.users = {
            USER_A: {"username": "alice", "groups": ["user"]},
            USER_B: {"username": "bob", "groups": ["user"]},
            USER_C: {"username": "cara", "groups": ["user"]},
        }

    def get_user(self, username="", user_id=""):
        if user_id and user_id in self.users:
            return user_id, self.users[user_id]
        for uid, rec in self.users.items():
            if rec.get("username") == username:
                return uid, rec
        return None, {}


class _Queue:
    def __init__(self):
        self.not_empty = threading.Condition()
        self.mutex = threading.Lock()
        self.queue = []
        self.currently_running = {}
        self.task_counter = 1
        self.history = {}

    def put(self, item):
        heapq.heappush(self.queue, item)


class _Server:
    def __init__(self):
        self.prompt_queue = _Queue()

    def queue_updated(self):
        pass

    def add_on_prompt_handler(self, fn):
        self.prompt_handler = fn


def _poll_as(ac, user_id):
    """Simulate another browser's request updating the process-wide fallback."""

    def poll():
        ac.set_current_user_id(user_id, set_fallback=True)

    contextvars.Context().run(poll)


def _load_access_control():
    from utils.access_control import AccessControl

    return AccessControl


@pytest.fixture
def roots(tmp_path):
    output = tmp_path / "output"
    temp = tmp_path / "temp"
    input_dir = tmp_path / "input"
    for path in (output, temp, input_dir):
        path.mkdir()
    folder_paths.get_output_directory = lambda: str(output)
    folder_paths.get_temp_directory = lambda: str(temp)
    folder_paths.get_input_directory = lambda: str(input_dir)
    return output, temp, input_dir


@pytest.fixture
def ac(roots):
    AccessControl = _load_access_control()
    return AccessControl(_Users(), _Server(), groups_config_file=str(roots[0] / "missing-groups.json"))


def _install_fake_nodes(custom_export_dir):
    """SaveImage / PreviewImage / SaveLatent shaped like ComfyUI core nodes."""

    class SaveImage:
        def __init__(self):
            self.output_dir = folder_paths.get_output_directory()
            self.type = "output"

    class PreviewImage(SaveImage):
        def __init__(self):
            self.output_dir = folder_paths.get_temp_directory()
            self.type = "temp"

    class SaveLatent:
        def __init__(self):
            self.output_dir = folder_paths.get_output_directory()

    class CustomCached:
        """Custom node that stores the directory itself during __init__."""

        def __init__(self):
            self.saved = folder_paths.get_output_directory()

    class CustomExport(SaveImage):
        def __init__(self):
            self.output_dir = custom_export_dir

    module = types.ModuleType("nodes")
    module.SaveImage = SaveImage
    module.PreviewImage = PreviewImage
    module.SaveLatent = SaveLatent
    module.CustomCached = CustomCached
    module.CustomExport = CustomExport
    sys.modules["nodes"] = module
    return module


def _install_fake_executor(nodes_mod):
    class PromptExecutor:
        def __init__(self):
            self.caches = types.SimpleNamespace(
                objects=types.SimpleNamespace(cache={}, subcaches={"stale": object()}),
                outputs=types.SimpleNamespace(
                    cache={"user-a-file": {"filename": "a.png"}},
                    subcaches={},
                    used_generation={"user-a-file": 1},
                ),
            )

        async def execute_async(self, prompt=None, prompt_id=None, extra_data=None, execute_outputs=None):
            cache = self.caches.objects.cache
            if "9" not in cache:
                cache["9"] = nodes_mod.SaveImage()
            if "custom" not in cache:
                cache["custom"] = nodes_mod.CustomCached()
            return cache["9"], cache["custom"]

    execution = sys.modules["execution"]
    execution.PromptExecutor = PromptExecutor
    return PromptExecutor


def test_reused_save_nodes_follow_the_executing_user(ac, roots):
    """A SaveImage built for user A must write into user B's folder once B is executing."""
    output, temp, _input = roots
    ac.patch_folder_paths()
    nodes_mod = _install_fake_nodes(str(output.parent / "custom_exports"))
    ac._install_dynamic_output_dirs()

    ac._bind_executing_user(USER_A)
    image = nodes_mod.SaveImage()
    preview = nodes_mod.PreviewImage()
    latent = nodes_mod.SaveLatent()
    assert image.output_dir == str(output / USER_A)
    assert preview.output_dir == str(temp / USER_A)
    assert latent.output_dir == str(output / USER_A)

    # Generated-tab polling from another browser overwrites the global fallback.
    _poll_as(ac, USER_C)
    ac._bind_executing_user(USER_B)

    assert image.output_dir == str(output / USER_B)
    assert preview.output_dir == str(temp / USER_B)
    assert latent.output_dir == str(output / USER_B)
    assert os.path.isdir(output / USER_B)
    assert os.path.isdir(temp / USER_B)


def test_custom_absolute_output_dir_is_preserved(ac, roots):
    output, _temp, _input = roots
    custom = os.path.abspath(str(output.parent / "custom_exports"))
    ac.patch_folder_paths()
    nodes_mod = _install_fake_nodes(custom)
    ac._install_dynamic_output_dirs()

    ac._bind_executing_user(USER_A)
    export = nodes_mod.CustomExport()
    assert export.output_dir == custom

    ac._bind_executing_user(USER_B)
    assert export.output_dir == custom


def test_rebase_strips_user_segment_and_keeps_extra_folders(ac, roots):
    output, temp, _input = roots
    ac._bind_executing_user(USER_B)
    stored = os.path.join(str(output), USER_A, "extras")
    assert ac.rebase_cached_directory(stored) == str(output / USER_B / "extras")

    plain = os.path.join(str(output), "extras")
    assert ac.rebase_cached_directory(plain) == str(output / USER_B / "extras")

    temp_stored = os.path.join(str(temp), USER_A)
    assert ac.rebase_cached_directory(temp_stored) == str(temp / USER_B)

    outside = os.path.abspath(os.path.join(str(output), "..", "not-comfy"))
    assert ac.rebase_cached_directory(outside) == outside


def test_executor_clears_node_cache_only_when_user_changes(ac, roots):
    ac.patch_folder_paths()
    nodes_mod = _install_fake_nodes(str(roots[0].parent / "custom_exports"))
    ac._install_dynamic_output_dirs()
    PromptExecutor = _install_fake_executor(nodes_mod)
    ac._install_executor_user_switch_reset()
    wrapped = PromptExecutor.execute_async
    ac._install_executor_user_switch_reset()
    assert PromptExecutor.execute_async is wrapped

    executor = PromptExecutor()
    ac._bind_executing_user(USER_A)
    image_a, custom_a = asyncio.run(executor.execute_async())
    assert image_a.output_dir.endswith(USER_A)
    assert custom_a.saved.endswith(USER_A)
    assert "stale" in executor.caches.objects.subcaches

    ac._bind_executing_user(USER_A)
    image_same, custom_same = asyncio.run(executor.execute_async())
    assert image_same is image_a
    assert custom_same is custom_a
    assert "user-a-file" in executor.caches.outputs.cache

    _poll_as(ac, USER_A)
    ac._bind_executing_user(USER_B)
    image_b, custom_b = asyncio.run(executor.execute_async())
    assert image_b is not image_a
    assert custom_b is not custom_a
    assert image_b.output_dir == str(roots[0] / USER_B)
    assert custom_b.saved == str(roots[0] / USER_B)
    assert executor.caches.objects.subcaches == {}
    assert executor.caches.outputs.cache == {}
    assert executor.caches.outputs.used_generation == {}
    assert executor._usgromana_cache_user_id == USER_B


def test_queue_get_binds_owner_ahead_of_poll_fallback(ac):
    """user_queue_get runs on the worker and must beat the global fallback."""
    _poll_as(ac, USER_A)
    heapq.heappush(
        ac.server.prompt_queue.queue,
        (0, "prompt-b", {}, {}, [], {"user_id": USER_B}),
    )

    def dequeue():
        return ac.user_queue_get()

    worker = contextvars.Context()
    entry, task_id = worker.run(dequeue)
    assert task_id == 1
    assert entry[-1]["user_id"] == USER_B
    assert worker.run(ac.get_current_user_id) == USER_B

    # A thread with no request context (node helper) still sees the prompt owner,
    # even though polling stored someone else in the process-wide fallback.
    _poll_as(ac, USER_C)
    seen = {}

    def helper():
        seen["user"] = ac.get_current_user_id()
        seen["output"] = ac.get_user_output_directory()

    thread = threading.Thread(target=helper)
    thread.start()
    thread.join()
    assert seen["user"] == USER_B
    assert seen["output"].endswith(USER_B)


def test_directory_override_does_not_leak_to_another_context(ac, roots):
    """Gallery / asset classification must not retarget the worker's folders."""
    output, _temp, _input = roots
    ac.patch_folder_paths()
    ac.set_current_user_id(USER_A)
    worker = contextvars.copy_context()
    getter = folder_paths.get_output_directory
    global_out = str(output)

    with ac.directory_override(output=lambda: global_out):
        assert folder_paths.get_output_directory is getter
        assert folder_paths.get_output_directory() == global_out
        assert worker.run(folder_paths.get_output_directory) == str(output / USER_A)

    assert folder_paths.get_output_directory() == str(output / USER_A)


def test_get_current_user_id_priority(ac):
    ac.set_current_user_id(USER_A)
    ac._executing_user_id = USER_B
    _poll_as(ac, USER_C)
    assert ac.get_current_user_id() == USER_A

    def without_request_context():
        return ac.get_current_user_id()

    assert contextvars.Context().run(without_request_context) == USER_B
    ac._executing_user_id = None
    assert contextvars.Context().run(without_request_context) == USER_C
