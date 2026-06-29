"""Pure-Python directory snapshotting and diffing.

This module contains NO QGIS dependencies so its logic can be unit-tested with
plain pytest. It walks a directory tree, records a lightweight fingerprint of
every candidate data file, and computes the delta between two snapshots.
"""

import os

# Sidecar / companion files that are part of another dataset (shapefile
# components, projection files, style files, statistics, etc.). These must not
# be treated as standalone layers, otherwise a single shapefile would appear as
# several "files" and a .qml style would be loaded as a layer.
SIDECAR_EXTENSIONS = frozenset(
    {
        ".qml",   # QGIS style
        ".sld",   # OGC style
        ".prj",   # projection
        ".qpj",   # QGIS projection
        ".dbf",   # shapefile attributes
        ".shx",   # shapefile index
        ".cpg",   # shapefile codepage
        ".sbn",   # shapefile spatial index
        ".sbx",   # shapefile spatial index
        ".idx",   # generic index
        ".xml",   # metadata sidecars (.shp.xml etc.)
        ".aux",   # gdal aux
        ".ovr",   # raster overviews
        ".rrd",   # raster overviews
        ".lock",  # lock files
        ".tmp",   # temp files
    }
)

# Suffixes (possibly multi-part) that should be skipped regardless of the simple
# extension check above.
SIDECAR_SUFFIXES = (
    ".aux.xml",
    ".shp.xml",
    ".tif.aux.xml",
)


def _is_sidecar(filename):
    """Return True if *filename* is a companion/sidecar rather than a dataset."""
    lower = filename.lower()
    if lower.startswith("."):
        # Hidden files and editor swap files.
        return True
    for suffix in SIDECAR_SUFFIXES:
        if lower.endswith(suffix):
            return True
    ext = os.path.splitext(lower)[1]
    return ext in SIDECAR_EXTENSIONS


def snapshot(root):
    """Walk *root* recursively and return ``{path: (mtime, size)}``.

    Sidecar/companion files are excluded. ``path`` is an absolute, normalized
    path so snapshots taken at different times compare cleanly.
    """
    result = {}
    root = os.path.abspath(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if _is_sidecar(name):
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError:
                # File vanished between listing and stat; ignore it.
                continue
            result[os.path.normpath(full)] = (st.st_mtime, st.st_size)
    return result


def diff(old, new):
    """Compare two snapshots.

    Returns ``(added, removed, modified)`` as sets of paths where:

    * ``added``    – present in *new* but not *old*
    * ``removed``  – present in *old* but not *new*
    * ``modified`` – present in both but ``(mtime, size)`` changed
    """
    old_paths = set(old)
    new_paths = set(new)
    added = new_paths - old_paths
    removed = old_paths - new_paths
    modified = {p for p in old_paths & new_paths if old[p] != new[p]}
    return added, removed, modified


def list_dirs(root):
    """Return every directory under *root* (inclusive) as absolute paths.

    Used to register each directory with ``QFileSystemWatcher``, which does not
    watch recursively on its own.
    """
    root = os.path.abspath(root)
    dirs = [root]
    for dirpath, _dirnames, _filenames in os.walk(root):
        for d in _dirnames:
            dirs.append(os.path.normpath(os.path.join(dirpath, d)))
    return dirs
