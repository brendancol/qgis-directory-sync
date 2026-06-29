"""Live directory watcher built on Qt's QFileSystemWatcher.

QFileSystemWatcher does not watch recursively, so every subdirectory is
registered explicitly and the watch list is re-synced whenever the tree shape
changes. Raw filesystem signals are noisy and bursty (an editor may write a file
in several chunks), so signals are coalesced through a single-shot debounce
timer before a full rescan + diff is performed.
"""

from qgis.PyQt.QtCore import QObject, QFileSystemWatcher, QTimer, pyqtSignal

from . import directory_scanner

DEBOUNCE_MS = 500


class DirectoryWatcher(QObject):
    """Emits :pyattr:`changed` with ``(added, removed, modified)`` path sets."""

    changed = pyqtSignal(set, set, set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = None
        self._snapshot = {}
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._on_fs_event)
        self._fs_watcher.fileChanged.connect(self._on_fs_event)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._process)

    # ------------------------------------------------------------------ public
    @property
    def root(self):
        return self._root

    def is_watching(self):
        return self._root is not None

    def start(self, root):
        """Begin watching *root*. Records the baseline snapshot (no events fired
        for files already present -- the caller loads the initial set itself).
        """
        self.stop()
        self._root = root
        self._snapshot = directory_scanner.snapshot(root)
        self._sync_watched_dirs()

    def initial_paths(self):
        """Paths present at ``start`` time, for the caller's initial load."""
        return set(self._snapshot)

    def stop(self):
        self._debounce.stop()
        self._clear_watched()
        self._root = None
        self._snapshot = {}

    # --------------------------------------------------------------- internals
    def _on_fs_event(self, _path):
        if self._root is None:
            return
        # Restart the debounce; many events collapse into one rescan.
        self._debounce.start()

    def _process(self):
        if self._root is None:
            return
        new_snapshot = directory_scanner.snapshot(self._root)
        added, removed, modified = directory_scanner.diff(
            self._snapshot, new_snapshot
        )
        self._snapshot = new_snapshot
        # Tree shape may have changed -> re-register directories.
        self._sync_watched_dirs()
        if added or removed or modified:
            self.changed.emit(added, removed, modified)

    def _sync_watched_dirs(self):
        """Make the watcher track exactly the current set of directories."""
        desired = set(directory_scanner.list_dirs(self._root))
        current = set(self._fs_watcher.directories())
        stale = current - desired
        fresh = desired - current
        if stale:
            self._fs_watcher.removePaths(list(stale))
        if fresh:
            self._fs_watcher.addPaths(list(fresh))

    def _clear_watched(self):
        dirs = self._fs_watcher.directories()
        files = self._fs_watcher.files()
        if dirs:
            self._fs_watcher.removePaths(dirs)
        if files:
            self._fs_watcher.removePaths(files)
