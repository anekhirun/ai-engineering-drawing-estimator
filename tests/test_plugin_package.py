from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

from server import VERSION  # noqa: E402


class PluginPackageTests(unittest.TestCase):
    def test_plugin_versions_and_components_are_aligned(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        file_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(manifest["name"], "engineering-drawing-estimator")
        self.assertEqual(manifest["version"], file_version)
        self.assertEqual(VERSION, file_version)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")

    def test_mcp_runtime_is_relative_and_desktop_dependency_is_excluded(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["engineering-drawing-estimator"]
        launcher = (ROOT / "plugin-mcp.ps1").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-mcp.txt").read_text(encoding="utf-8")

        self.assertEqual(server["cwd"], ".")
        self.assertIn("./plugin-mcp.ps1", server["args"])
        self.assertNotIn("C:\\Users", launcher)
        self.assertIn("ENGINEERING_DRAWING_ESTIMATOR_PYTHON", launcher)
        self.assertNotIn("PySide6", requirements)
        self.assertIn("opencv-python-headless", requirements)

    def test_release_packager_uses_an_explicit_public_allowlist(self) -> None:
        packager = (ROOT / "scripts" / "build-plugin-package.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('foreach ($Directory in @(".codex-plugin", "mcp", "skills"))', packager)
        self.assertNotIn('Copy-Item -LiteralPath $Root', packager)
        self.assertIn("__pycache__", packager)
        self.assertIn("Plugin package is missing required file", packager)
        self.assertIn('path = "./plugins/$PluginName"', packager)


if __name__ == "__main__":
    unittest.main()
