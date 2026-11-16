import unittest
from unittest.mock import patch

from src.config import CONTEXTS
from src.core.icon_database import IconDatabase


class TestIconDatabase(unittest.TestCase):
    def test_initial_state(self):
        db = IconDatabase()
        self.assertEqual(db.fallback_theme, "Adwaita")
        self.assertFalse(db._is_loaded)
        self.assertEqual(set(db._database.keys()), set(CONTEXTS.keys()))
        for ctx in CONTEXTS:
            self.assertEqual(db._database[ctx], [])

    def test_custom_fallback_theme_stored(self):
        db = IconDatabase(fallback_theme="Papirus")
        self.assertEqual(db.fallback_theme, "Papirus")

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_build_database_aggregates_and_sorts_icons(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"org.gnome.Terminal", "firefox", "alacritty"}
        mock_scan_system.return_value = {
            "places": {"folder-videos", "folder"},
            "status": {"battery-low", "audio-volume-high"},
        }

        db = IconDatabase(fallback_theme="Adwaita")
        db.build_database()

        mock_scan_apps.assert_called_once_with()
        mock_scan_system.assert_called_once_with("Adwaita")
        self.assertTrue(db._is_loaded)

        self.assertEqual(
            db.get_suggestions("apps"),
            ["alacritty", "firefox", "org.gnome.Terminal"],
        )
        self.assertEqual(db.get_suggestions("places"), ["folder", "folder-videos"])
        self.assertEqual(db.get_suggestions("status"), ["audio-volume-high", "battery-low"])

        for ctx in CONTEXTS:
            if ctx not in {"apps", "places", "status"}:
                self.assertEqual(db.get_suggestions(ctx), [])

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_build_database_ignores_apps_from_system_icons(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"calculator"}
        mock_scan_system.return_value = {
            "apps": {"should-be-ignored"},
            "actions": {"document-save"},
        }

        db = IconDatabase()
        db.build_database()

        self.assertEqual(db.get_suggestions("apps"), ["calculator"])
        self.assertEqual(db.get_suggestions("actions"), ["document-save"])

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_lazy_loading_in_get_suggestions_caches_results(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"firefox"}
        mock_scan_system.return_value = {"places": {"folder"}}

        db = IconDatabase()
        mock_scan_apps.assert_not_called()
        mock_scan_system.assert_not_called()

        self.assertEqual(db.get_suggestions("apps"), ["firefox"])
        mock_scan_apps.assert_called_once()
        mock_scan_system.assert_called_once()

        self.assertEqual(db.get_suggestions("places"), ["folder"])
        mock_scan_apps.assert_called_once()
        mock_scan_system.assert_called_once()

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_get_suggestions_returns_defensive_copy(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"firefox", "gimp"}
        mock_scan_system.return_value = {"places": {"folder"}}

        db = IconDatabase()
        suggestions = db.get_suggestions("apps")
        self.assertIsNot(suggestions, db._database["apps"])

        suggestions.append("mutated-icon")
        suggestions.clear()

        self.assertEqual(db.get_suggestions("apps"), ["firefox", "gimp"])

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_unknown_context_returns_empty_list(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"firefox"}
        mock_scan_system.return_value = {}

        db = IconDatabase()
        self.assertEqual(db.get_suggestions("nonexistent_context"), [])
        mock_scan_apps.assert_called_once()

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_reload_database_refreshes_cached_data(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.side_effect = [{"firefox"}, {"firefox", "gimp"}]
        mock_scan_system.side_effect = [
            {"places": {"folder"}},
            {"places": {"folder", "user-home"}},
        ]

        db = IconDatabase()
        db.build_database()
        self.assertEqual(db.get_suggestions("apps"), ["firefox"])
        self.assertEqual(db.get_suggestions("places"), ["folder"])

        db.reload_database()
        self.assertEqual(mock_scan_apps.call_count, 2)
        self.assertEqual(mock_scan_system.call_count, 2)
        self.assertEqual(db.get_suggestions("apps"), ["firefox", "gimp"])
        self.assertEqual(db.get_suggestions("places"), ["folder", "user-home"])

    @patch("src.core.icon_database.scan_system_icons")
    @patch("src.core.icon_database.scan_installed_apps")
    def test_scanner_failure_leaves_database_unloaded(self, mock_scan_apps, mock_scan_system):
        mock_scan_apps.return_value = {"firefox"}
        mock_scan_system.side_effect = OSError("Brak dostępu do /usr/share/icons")

        db = IconDatabase()
        with self.assertRaises(OSError):
            db.build_database()

        self.assertFalse(db._is_loaded)


if __name__ == "__main__":
    unittest.main()