"""Share records stay inside the owner's output folder and can be revoked."""

import os
import uuid

from utils.image_shares import (
    ImageShareStore,
    normalize_relpath,
    parse_shared_relpath,
    shared_relpath,
)


OWNER = str(uuid.uuid4())
OTHER = str(uuid.uuid4())


def _png(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 1x1 PNG
    payload = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with open(path, "wb") as handle:
        handle.write(payload)


def test_normalize_relpath_rejects_escape():
    assert normalize_relpath("folder/shot.png") == "folder/shot.png"
    assert normalize_relpath("..\\shot.png") is None
    # A leading slash is dropped, so the remainder stays under the owner folder.
    assert normalize_relpath("/etc/passwd") == "etc/passwd"
    assert normalize_relpath("shared/abc/shot.png") is None
    assert normalize_relpath("") is None
    assert normalize_relpath(None) is None


def test_parse_shared_relpath():
    rel = shared_relpath(OWNER, "album/shot.png")
    assert parse_shared_relpath(rel) == (OWNER, "album/shot.png")
    assert parse_shared_relpath("shared/not-a-uuid/shot.png") is None
    assert parse_shared_relpath(f"shared/{OWNER}/../shot.png") is None


def test_share_revoke_and_visibility(tmp_path):
    output = tmp_path / "output"
    _png(str(output / OWNER / "album" / "shot.png"))
    _png(str(output / OTHER / "secret.png"))
    store = ImageShareStore(str(tmp_path / "image_shares.json"), str(output))

    assert store.resolve_owned_file(OWNER, "album/shot.png")
    assert store.resolve_owned_file(OWNER, "../" + OTHER + "/secret.png") is None
    assert store.resolve_owned_file(OTHER, "secret.png")

    granted = store.share(
        OWNER,
        ["album/shot.png", "album/shot.png"],
        ["viewer", "guest", "viewer"],
        {"viewer", "guest", "owner"},
    )
    assert granted["shares"] == [{"relpath": "album/shot.png", "viewers": ["viewer"]}]
    assert store.can_view(OTHER, "viewer", OWNER, "album/shot.png")
    assert not store.can_view(OTHER, "stranger", OWNER, "album/shot.png")
    assert store.can_view(OWNER, "owner", OWNER, "album/shot.png")
    assert not store.can_view(None, None, OWNER, "album/shot.png")

    visible = store.shares_for_viewer("viewer")
    assert [item["shared_relpath"] for item in visible] == [
        shared_relpath(OWNER, "album/shot.png")
    ]
    assert store.shares_for_viewer("guest") == []

    revoked = store.revoke(OWNER, ["album/shot.png"], ["viewer"])
    assert revoked["shares"] == [{"relpath": "album/shot.png", "viewers": []}]
    assert not store.can_view(OTHER, "viewer", OWNER, "album/shot.png")
    assert store.shares_for_viewer("viewer") == []
    assert store.visibility(OWNER, ["album/shot.png"]) == [
        {"relpath": "album/shot.png", "viewers": []}
    ]


def test_share_rejects_unknown_account_and_missing_file(tmp_path):
    output = tmp_path / "output"
    _png(str(output / OWNER / "shot.png"))
    store = ImageShareStore(str(tmp_path / "image_shares.json"), str(output))
    try:
        store.share(OWNER, ["shot.png"], ["nobody"], {"viewer"})
        raise AssertionError("unknown account should fail")
    except ValueError as exc:
        assert "nobody" in str(exc)
    try:
        store.share(OWNER, ["missing.png"], ["viewer"], {"viewer"})
        raise AssertionError("missing file should fail")
    except ValueError as exc:
        assert "missing.png" in str(exc)


def test_symlink_outside_owner_folder_is_not_readable(tmp_path):
    output = tmp_path / "output"
    outside = tmp_path / "outside.png"
    _png(str(outside))
    owner_dir = output / OWNER
    owner_dir.mkdir(parents=True)
    os.symlink(outside, owner_dir / "linked.png")
    store = ImageShareStore(str(tmp_path / "image_shares.json"), str(output))
    assert store.resolve_owned_file(OWNER, "linked.png") is None
    assert not store.can_view(OWNER, "owner", OWNER, "linked.png")
