import logging
import configparser
from pathlib import Path
from src.config import CONTEXTS, SYSTEM_ICONS_DIR

logger = logging.getLogger(__name__)

def scan_installed_apps(desktop_dirs: list[Path] | None = None) -> set[str]:
    logger.debug("scan_installed_apps_start")
    if desktop_dirs is None:
        desktop_dirs = [
            Path("/usr/share/applications/"),
            Path("~/.local/share/applications/").expanduser(),
        ]

    icon_names = set()

    for dir in desktop_dirs:
        if not dir.exists():
            logger.debug(f"scan_installed_apps_dir_not_found: {dir}")
            continue

        for file in dir.glob("**/*.desktop"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("Icon="):
                            icon_name = line.split("=")[1].strip()
                            if not icon_name.startswith("/"):
                                icon_names.add(icon_name)
                            break

            except (PermissionError, UnicodeDecodeError) as e:
                logger.warning(f"scan_installed_apps_error: {file} -> {e}")
                continue

    logger.debug(f"scan_installed_apps_done: found={len(icon_names)}")
    return icon_names

def scan_system_icons(theme_name: str = "Adwaita", base_icons_dir: Path = SYSTEM_ICONS_DIR) -> dict[str, set[str]]:
    logger.debug(f"scan_system_icons_start: theme={theme_name}")
    theme_dir = base_icons_dir / theme_name
    icon_db = {context: set() for context in CONTEXTS if context != "apps"}

    if not theme_dir.exists():
        logger.warning(f"scan_system_icons_theme_not_found: {theme_dir}")
        return icon_db

    for context in icon_db.keys():
        # Znak '*' zastępuje katalog z rozmiarem (np. 'scalable', '48x48')
        # Znak '**' zagląda do wszystkich ewentualnych podkatalogów wewnątrz kontekstu

        for icon_file in theme_dir.glob(f"*/{context}/**/*.png"):
            icon_db[context].add(icon_file.stem)

        for icon_file in theme_dir.glob(f"*/{context}/**/*.svg"):
            icon_db[context].add(icon_file.stem)

    logger.debug(f"scan_system_icons_done: theme={theme_name}")
    return icon_db

def scan_available_themes(icons_dirs: list[Path] | None = None) -> list[str]:
    """Skanuje katalogi systemowe w poszukiwaniu zainstalowanych motywów ikon."""
    logger.debug("scan_available_themes_start")
    if icons_dirs is None:
        icons_dirs = [SYSTEM_ICONS_DIR]

    themes: set[str] = set()
    for base_dir in icons_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            logger.debug(f"scan_available_themes_dir_not_found: {base_dir}")
            continue

        for entry in base_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            index_file = entry / "index.theme"
            if not index_file.is_file():
                continue

            config = configparser.ConfigParser()
            config.optionxform = str
            try:
                config.read(index_file, encoding="utf-8")
            except (configparser.Error, OSError) as err:
                logger.warning(f"scan_available_themes_error: {index_file} -> {err}")
                continue

            if "Icon Theme" not in config:
                continue

            theme_section = config["Icon Theme"]
            if (entry / "cursors").is_dir() and not theme_section.get("Directories", "").strip():
                continue

            themes.add(entry.name)

    sorted_themes = sorted(themes, key=str.casefold)
    logger.debug(f"scan_available_themes_done: found={len(sorted_themes)}")
    return sorted_themes

if __name__ == "__main__":
    print(scan_installed_apps())
    print(scan_system_icons())