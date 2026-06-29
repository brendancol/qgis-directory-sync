"""Directory Sync -- QGIS plugin entry point.

Adds a checkable toolbar/menu action. When toggled on, the user picks a folder
and the map stays in sync with it: new files load as layers, removed files have
their layers removed, and edited files are reloaded in place.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.PyQt.QtGui import QIcon
from qgis.core import Qgis

from .directory_watcher import DirectoryWatcher
from .layer_manager import LayerManager

MENU_TITLE = "&Directory Sync"
ACTION_TEXT = "Watch Directory…"


class DirectorySyncPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.watcher = DirectoryWatcher()
        self.manager = LayerManager(iface)
        self.watcher.changed.connect(self._on_changed)

    # --------------------------------------------------------------- QGIS hooks
    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.svg")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, ACTION_TEXT, self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip("Watch a directory and sync its layers into the map")
        self.action.toggled.connect(self._on_toggled)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU_TITLE, self.action)

    def unload(self):
        self.watcher.stop()
        self.manager.clear()
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(MENU_TITLE, self.action)
            self.action = None

    # ----------------------------------------------------------------- handlers
    def _on_toggled(self, checked):
        if checked:
            self._start()
        else:
            self._stop()

    def _start(self):
        folder = QFileDialog.getExistingDirectory(
            self.iface.mainWindow(), "Select directory to watch"
        )
        if not folder:
            # User cancelled -> revert the toggle without firing again.
            self.action.blockSignals(True)
            self.action.setChecked(False)
            self.action.blockSignals(False)
            return

        self.watcher.start(folder)
        # Load everything already present in the folder.
        for path in self.watcher.initial_paths():
            self.manager.load(os.path.normpath(path))
        self._notify("Watching %s" % folder)

    def _stop(self):
        self.watcher.stop()
        # Leave loaded layers on the map; just stop tracking/watching.
        self.manager.clear()
        self._notify("Stopped watching")

    def _on_changed(self, added, removed, modified):
        self.manager.apply_delta(added, removed, modified)
        self.iface.mapCanvas().refresh()

    # ------------------------------------------------------------------ utility
    def _notify(self, message):
        self.iface.messageBar().pushMessage(
            "Directory Sync", message, level=Qgis.Info, duration=4
        )
