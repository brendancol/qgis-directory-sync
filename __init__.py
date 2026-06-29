"""Directory Sync QGIS plugin package."""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Entry point called by QGIS to instantiate the plugin."""
    from .directory_sync_plugin import DirectorySyncPlugin

    return DirectorySyncPlugin(iface)
