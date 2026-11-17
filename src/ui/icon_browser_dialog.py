import logging
from typing import Callable
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from src.config import CONTEXTS
from src.i18n import t

logger = logging.getLogger(__name__)

class IconTile(Gtk.FlowBoxChild):
    """Pojedynczy kafelek ikony w siatce"""

    def __init__(self, context: str, icon_name: str) -> None:
        super().__init__()
        self.context = context
        self.icon_name = icon_name

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_size_request(84, 84)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        image = Gtk.Image.new_from_icon_name(icon_name)
        image.set_pixel_size(48)
        image.set_valign(Gtk.Align.CENTER)
        box.append(image)

        label = Gtk.Label(label=icon_name)
        label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        label.set_max_width_chars(11)
        label.set_width_chars(11)
        label.set_halign(Gtk.Align.CENTER)
        label.add_css_class("caption")
        box.append(label)

        self.set_child(box)
        self.set_tooltip_text(f"{icon_name}\n({context})")

class IconBrowserDialog(Gtk.Window):
    """Okno siatki ikon ze skanera z wyszukiwarką i filtrowaniem"""

    def __init__(
            self,
            parent: Gtk.Window,
            suggestions_map: dict[str, list[str]],
            initial_context: str | None = None,
            on_icon_selected: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(720, 520)
        self.set_title(t("browser.title"))

        self.suggestions_map = suggestions_map
        self.on_icon_selected = on_icon_selected
        self._current_tiles: list[IconTile] = []

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        self.set_child(main_box)

        # --- GÓRNY PASEK NARZĘDZIOWY ---
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # 1. Wybór kontekstu
        self.context_options = [t("browser.context.all")] + list(CONTEXTS)
        self.context_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(self.context_options)
        )
        self.context_dropdown.connect("notify::selected", self._on_filter_changed)
        toolbar.append(self.context_dropdown)

        # 2. Wyszukiwarka ikon
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(t("browser.search.placeholder"))
        self.search_entry.set_tooltip_text(t("browser.search.tooltip"))
        self.search_entry.connect("search-changed", self._on_filter_changed)
        toolbar.append(self.search_entry)

        # 3. Sortowanie
        self.sort_options = [t("browser.sort.asc"), t("browser.sort.desc")]
        self.sort_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(self.sort_options)
        )
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        toolbar.append(self.sort_dropdown)

        main_box.append(toolbar)

        # --- SIATKA IKON (Gtk.FlowBox w ScrolledWindow) ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_filter_func(self._filter_tile)
        self.flowbox.set_sort_func(self._sort_tile)
        self.flowbox.connect("selected-children-changed", self._on_selection_changed)
        self.flowbox.connect("child-activated", self._on_child_activated)

        scrolled.set_child(self.flowbox)
        main_box.append(scrolled)

        # --- DOLNY PASEK AKCJI ---
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_bar.set_margin_top(6)

        self.count_label = Gtk.Label()
        self.count_label.set_hexpand(True)
        self.count_label.set_halign(Gtk.Align.START)
        self.count_label.add_css_class("dim-label")
        bottom_bar.append(self.count_label)

        self.btn_cancel = Gtk.Button(label=t("browser.btn.cancel"))
        self.btn_cancel.connect("clicked", lambda b: self.close())
        bottom_bar.append(self.btn_cancel)

        self.btn_select = Gtk.Button(label=t("browser.btn.select"))
        self.btn_select.add_css_class("suggested-action")
        self.btn_select.set_sensitive(False)
        self.btn_select.connect("clicked", self._on_select_clicked)
        bottom_bar.append(self.btn_select)

        main_box.append(bottom_bar)

        # Załaduj kafelki do siatki
        self._populate_tiles()

        # Ustaw początkowy kontekst, jeśli został przekazany z wiersza
        if initial_context and initial_context in CONTEXTS:
            idx = self.context_options.index(initial_context)
            self.context_dropdown.set_selected(idx)

        self._update_count()

    def _populate_tiles(self) -> None:
        """Wypełnia siatkę kafelkami na podstawie bazy ikon."""
        for ctx, icons in self.suggestions_map.items():
            for name in icons:
                tile = IconTile(context=ctx, icon_name=name)
                self.flowbox.append(tile)

    def _on_filter_changed(self, *args) -> None:
        self.flowbox.invalidate_filter()
        self._update_count()

    def _on_sort_changed(self, *args) -> None:
        self.flowbox.invalidate_sort()

    def _filter_tile(self, child: Gtk.FlowBoxChild, *args) -> bool:
        if not isinstance(child, IconTile):
            return True

        # Filtr kontekstu
        sel_idx = self.context_dropdown.get_selected()
        if 0 < sel_idx < len(self.context_options):
            chosen_ctx = self.context_options[sel_idx]
            if child.context != chosen_ctx:
                return False

        # Filtr wyszukiwarki
        query = self.search_entry.get_text().strip().lower()
        if query and query not in child.icon_name.lower():
            return False

        return True

    def _sort_tile(self, child1: Gtk.FlowBoxChild, child2: Gtk.FlowBoxChild, *args) -> int:
        if not isinstance(child1, IconTile) or not isinstance(child2, IconTile):
            return 0

        is_desc = self.sort_dropdown.get_selected() == 1
        name1 = child1.icon_name.lower()
        name2 = child2.icon_name.lower()

        if name1 < name2:
            return 1 if is_desc else -1
        elif name1 > name2:
            return -1 if is_desc else 1
        return 0

    def _on_selection_changed(self, flowbox: Gtk.FlowBox) -> None:
        selected = flowbox.get_selected_children()
        self.btn_select.set_sensitive(len(selected) > 0)

    def _on_child_activated(self, flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild) -> None:
        """Dwuklik lub wciśnięcie Enter na kafelku natychmiast zatwierdza wybór."""
        if isinstance(child, IconTile):
            self._confirm_selection(child)

    def _on_select_clicked(self, button: Gtk.Button) -> None:
        selected = self.flowbox.get_selected_children()
        if selected and isinstance(selected[0], IconTile):
            self._confirm_selection(selected[0])

    def _confirm_selection(self, tile: IconTile) -> None:
        if self.on_icon_selected:
            self.on_icon_selected(tile.context, tile.icon_name)
        self.close()

    def _update_count(self) -> None:
        # Przelicz widoczne kafelki po filtracji
        visible_count = 0
        child = self.flowbox.get_first_child()
        while child is not None:
            if isinstance(child, IconTile) and child.get_child_visible():
                visible_count += 1
            child = child.get_next_sibling()

        self.count_label.set_text(t("browser.count_label", count=visible_count))
