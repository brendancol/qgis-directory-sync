"""Unit tests for the pure directory_scanner core (no QGIS required)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import directory_scanner as ds  # noqa: E402


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)


# --------------------------------------------------------------------- snapshot
def test_snapshot_includes_data_files(tmp_path):
    _write(str(tmp_path / "a.shp"))
    _write(str(tmp_path / "b.tif"))
    snap = ds.snapshot(str(tmp_path))
    names = {os.path.basename(p) for p in snap}
    assert names == {"a.shp", "b.tif"}


def test_snapshot_excludes_sidecars(tmp_path):
    _write(str(tmp_path / "a.shp"))
    for ext in (".dbf", ".shx", ".prj", ".cpg", ".qml"):
        _write(str(tmp_path / ("a" + ext)))
    _write(str(tmp_path / "a.shp.xml"))
    _write(str(tmp_path / "a.tif.aux.xml"))
    snap = ds.snapshot(str(tmp_path))
    names = {os.path.basename(p) for p in snap}
    assert names == {"a.shp"}


def test_snapshot_excludes_hidden_files(tmp_path):
    _write(str(tmp_path / ".hidden.tif"))
    _write(str(tmp_path / "visible.tif"))
    snap = ds.snapshot(str(tmp_path))
    names = {os.path.basename(p) for p in snap}
    assert names == {"visible.tif"}


def test_snapshot_is_recursive(tmp_path):
    _write(str(tmp_path / "top.tif"))
    _write(str(tmp_path / "sub" / "nested" / "deep.shp"))
    snap = ds.snapshot(str(tmp_path))
    names = {os.path.basename(p) for p in snap}
    assert names == {"top.tif", "deep.shp"}


# ------------------------------------------------------------------------- diff
def test_diff_detects_added(tmp_path):
    _write(str(tmp_path / "a.tif"))
    old = ds.snapshot(str(tmp_path))
    _write(str(tmp_path / "b.tif"))
    new = ds.snapshot(str(tmp_path))
    added, removed, modified = ds.diff(old, new)
    assert {os.path.basename(p) for p in added} == {"b.tif"}
    assert removed == set()
    assert modified == set()


def test_diff_detects_removed(tmp_path):
    _write(str(tmp_path / "a.tif"))
    _write(str(tmp_path / "b.tif"))
    old = ds.snapshot(str(tmp_path))
    os.remove(str(tmp_path / "b.tif"))
    new = ds.snapshot(str(tmp_path))
    added, removed, modified = ds.diff(old, new)
    assert added == set()
    assert {os.path.basename(p) for p in removed} == {"b.tif"}
    assert modified == set()


def test_diff_detects_modified_by_size(tmp_path):
    target = str(tmp_path / "a.tif")
    _write(target, "short")
    old = ds.snapshot(str(tmp_path))
    _write(target, "a much longer content string")  # size changes
    new = ds.snapshot(str(tmp_path))
    added, removed, modified = ds.diff(old, new)
    assert added == set()
    assert removed == set()
    assert {os.path.basename(p) for p in modified} == {"a.tif"}


def test_diff_detects_modified_by_mtime(tmp_path):
    target = str(tmp_path / "a.tif")
    _write(target, "same-size")
    old = ds.snapshot(str(tmp_path))
    # Same size, newer mtime.
    future = os.stat(target).st_mtime + 100
    os.utime(target, (future, future))
    new = ds.snapshot(str(tmp_path))
    _added, _removed, modified = ds.diff(old, new)
    assert {os.path.basename(p) for p in modified} == {"a.tif"}


def test_diff_no_change(tmp_path):
    _write(str(tmp_path / "a.tif"))
    snap = ds.snapshot(str(tmp_path))
    added, removed, modified = ds.diff(snap, dict(snap))
    assert (added, removed, modified) == (set(), set(), set())


# -------------------------------------------------------------------- list_dirs
def test_list_dirs_recursive(tmp_path):
    os.makedirs(str(tmp_path / "sub" / "nested"))
    os.makedirs(str(tmp_path / "other"))
    dirs = set(ds.list_dirs(str(tmp_path)))
    expected = {
        os.path.normpath(str(tmp_path)),
        os.path.normpath(str(tmp_path / "sub")),
        os.path.normpath(str(tmp_path / "sub" / "nested")),
        os.path.normpath(str(tmp_path / "other")),
    }
    assert dirs == expected


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
