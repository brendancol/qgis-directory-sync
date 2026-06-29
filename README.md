# Directory Sync (QGIS plugin)

Keep your QGIS map in sync with a directory on disk. While the plugin is
watching a folder:

- **New** spatial files are loaded automatically as layers.
- **Removed** files have their layers removed from the map.
- **Edited** files are reloaded **in place**, preserving styling and the layer's
  position in the layer tree.

Watching is **recursive**, uses a **live filesystem watcher**, supports **any
GDAL/OGR-readable format** (including multi-layer GeoPackages), and applies a
sibling `.qml` style automatically when present.

## How it works

| Module | Responsibility |
|---|---|
| `directory_scanner.py` | Pure Python: snapshot a tree, diff snapshots, list dirs. No QGIS deps — unit-tested. |
| `directory_watcher.py` | `QFileSystemWatcher` over every subdir + a 500 ms debounce → emits `(added, removed, modified)`. |
| `layer_manager.py` | Loads/reloads/removes layers via `QgsProviderRegistry.querySublayers`; tracks only its own layers. |
| `directory_sync_plugin.py` | Toolbar/menu toggle, folder picker, wiring. |

The directory choice is **session-only**: you pick it each time via a dialog and
nothing is persisted.

## Install (development)

Copy or symlink this folder into your QGIS profile's plugin directory.

**Linux / macOS:**

```bash
ln -s "$PWD" ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/directory_sync
```

**Windows:**

Create a directory junction (no admin rights required) from a `cmd` prompt,
pointing the QGIS plugins folder at this repo:

```bat
mklink /J "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\directory_sync" "C:\path\to\qgis-directory-sync"
```

Then enable **Directory Sync** in *Plugins → Manage and Install Plugins → Installed*.
Requires QGIS **3.22+**.

Click the toolbar button (or *Plugins → Directory Sync → Watch Directory…*),
choose a folder, and toggle it off again to stop watching (loaded layers stay on
the map).

## Tests

The pure scanning/diffing logic runs without QGIS:

```bash
python3 -m pytest test/test_directory_scanner.py -v
```
