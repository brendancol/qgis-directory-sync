"""QGIS-facing layer lifecycle management.

Loads, reloads and removes map layers in response to filesystem deltas. Only
layers that this manager loaded are ever touched -- the user's manually added
layers are left alone.

A single data file may expand into several map layers (e.g. a GeoPackage with
many tables), so layers are tracked per *sublayer URI* rather than per file.
"""

import os

from qgis.core import (
    QgsProject,
    QgsProviderRegistry,
    QgsProviderSublayerDetails,
    QgsMessageLog,
    Qgis,
)

LOG_TAG = "Directory Sync"


class LayerManager:
    def __init__(self, iface=None):
        self._iface = iface
        # path -> { sublayer_uri: layer_id }
        self._managed = {}

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _project():
        return QgsProject.instance()

    def _log(self, message, level=Qgis.Info):
        QgsMessageLog.logMessage(message, LOG_TAG, level)

    def _query_sublayers(self, path):
        """Return sublayer details for *path*, or [] if it is not spatial data."""
        registry = QgsProviderRegistry.instance()
        try:
            return registry.querySublayers(path)
        except Exception as exc:  # pragma: no cover - defensive
            self._log("querySublayers failed for %s: %s" % (path, exc),
                      Qgis.Warning)
            return []

    def _build_layer(self, details):
        """Turn QgsProviderSublayerDetails into a styled, valid map layer.

        Returns the layer, or None if it could not be built/validated yet.
        """
        options = QgsProviderSublayerDetails.LayerOptions(
            self._project().transformContext()
        )
        layer = details.toLayer(options)
        if layer is None or not layer.isValid():
            return None
        # Apply a sibling .qml/.sld default style if one exists.
        try:
            layer.loadDefaultStyle()
        except Exception:  # pragma: no cover - style is best-effort
            pass
        return layer

    # ------------------------------------------------------------------ public
    def load(self, path):
        """Load every sublayer of *path* and add it to the project."""
        if path in self._managed:
            # Already managed (e.g. duplicate event) -> treat as a reload.
            self.reload(path)
            return

        details_list = self._query_sublayers(path)
        if not details_list:
            return  # Not a recognised spatial file; ignore silently.

        added = {}
        for details in details_list:
            layer = self._build_layer(details)
            if layer is None:
                continue
            self._project().addMapLayer(layer)
            added[details.uri()] = layer.id()
            self._log("Loaded layer: %s" % details.uri())

        if added:
            self._managed[path] = added

    def reload(self, path):
        """Refresh layers for *path* in place, reconciling multi-layer files."""
        if path not in self._managed:
            # Not tracked yet (e.g. file became valid only now) -> load it.
            self.load(path)
            return

        current = self._query_sublayers(path)
        current_uris = {d.uri(): d for d in current}
        tracked = self._managed[path]

        # 1) Drop sublayers that no longer exist in the file.
        for uri in list(tracked):
            if uri not in current_uris:
                self._remove_layer_id(tracked.pop(uri))
                self._log("Removed vanished sublayer: %s" % uri)

        # 2) Reload survivors in place; add brand-new sublayers.
        for uri, details in current_uris.items():
            if uri in tracked:
                layer = self._project().mapLayer(tracked[uri])
                if layer is None:
                    # User deleted it from the tree; reload as new.
                    del tracked[uri]
                else:
                    self._reload_in_place(layer)
                    continue
            layer = self._build_layer(details)
            if layer is None:
                continue
            self._project().addMapLayer(layer)
            tracked[uri] = layer.id()
            self._log("Added new sublayer on reload: %s" % uri)

        if tracked:
            self._managed[path] = tracked
        else:
            self._managed.pop(path, None)

    @staticmethod
    def _reload_in_place(layer):
        """Refresh a layer's data while preserving its styling and tree slot."""
        try:
            layer.reload()
        except Exception:  # pragma: no cover - some providers lack reload
            layer.dataProvider().reloadData()
        layer.updateExtents()
        layer.triggerRepaint()

    def remove(self, path):
        """Remove all layers associated with *path* from the project."""
        tracked = self._managed.pop(path, None)
        if not tracked:
            return
        for layer_id in tracked.values():
            self._remove_layer_id(layer_id)
        self._log("Removed layers for: %s" % path)

    def _remove_layer_id(self, layer_id):
        project = self._project()
        if project.mapLayer(layer_id) is not None:
            project.removeMapLayer(layer_id)

    def clear(self):
        """Forget all managed layers WITHOUT removing them from the map.

        Used when the user stops watching: loaded layers stay on the map but are
        no longer tracked.
        """
        self._managed.clear()

    # --------------------------------------------------------------- bulk apply
    def apply_delta(self, added, removed, modified):
        """Apply a scanner delta. Order: remove, reload, add."""
        for path in removed:
            self.remove(os.path.normpath(path))
        for path in modified:
            self.reload(os.path.normpath(path))
        for path in added:
            self.load(os.path.normpath(path))
