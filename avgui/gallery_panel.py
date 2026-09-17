"""
Gallery panel: recent images, with a way to put any of them back on the
overlay. Thumbnails are cached by path so scrolling doesn't re-decode.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from . import theme
from .dialogs import ConfirmDelete, ConfirmPurge, RenameImage
from .filters import DATE_RANGES, SOURCES, Filters
from .viewer import ImageViewer
from .widgets import HoverCaption, TriStateFilter

EXTS = (".png", ".jpg", ".jpeg", ".webp")
COLS = 3
THUMB = QSize(210, 118)

# How many thumbnails to draw at once. Building one is not free, so a few
# hundred at a time would make the panel crawl - but every image on disk
# is still listed and reachable by paging.
PAGE_SIZES = [("12", 12), ("24", 24), ("48", 48), ("96", 96), ("All", 0)]


class Thumb(QWidget):
    def __init__(self, path, on_push, entry=None, on_changed=None,
                 engine=None, on_expand=None, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.engine = engine
        self.on_changed = on_changed or (lambda: None)
        self.on_expand = on_expand
        self.entry = entry or {}
        self.censored = bool(self.entry.get("censored"))
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self.image = HoverCaption(THUMB)
        pm = QPixmap(str(self.path))
        self.full = pm
        if not pm.isNull():
            shown = pm.scaled(THUMB, Qt.KeepAspectRatio,
                              Qt.SmoothTransformation)
            if self.censored:
                shown = self._blurred(shown)
            self.image.setPixmap(shown)
        self.image.set_favourite(bool(self.entry.get("favourite")))
        self.image.cog_clicked.connect(self._open_menu)
        self.image.expand_clicked.connect(self._expand)

        if entry and entry.get("prompt"):
            when = entry.get("at")
            stamp = (datetime.fromtimestamp(when).strftime("%d %b, %H:%M")
                     if when else "")
            source = entry.get("source") or ""
            detail = "   ".join(x for x in (
                "typed" if source == "manual" else "heard", stamp) if x)
            self.image.set_caption(entry["prompt"], detail)
            self.image.setToolTip(entry["prompt"])
        else:
            # Images made before the catalogue existed, or ones dropped
            # into the folder by hand. Saying so is better than an empty
            # hover that looks broken.
            self.image.set_caption("No prompt was recorded for this image.")

        col.addWidget(self.image)

        row = QHBoxLayout()
        row.setSpacing(4)
        name = QLabel()
        name.setObjectName("fieldLabel")
        name.setToolTip(str(self.path))
        # Elided in the middle: the start says what made it and the end
        # is the timestamp that tells one from another, so the middle is
        # the part worth losing.
        metrics = QFontMetrics(name.font())
        name.setText(metrics.elidedText(self.path.name, Qt.ElideMiddle,
                                        THUMB.width() - 56))
        row.addWidget(name, 1)
        push = QPushButton("Show")
        push.setToolTip("Put this image on the overlay")
        push.clicked.connect(lambda: on_push(self.path))
        row.addWidget(push)
        col.addLayout(row)
        # Without this the cell stretches to the grid column, which on a
        # wide window leaves each Show button stranded halfway to the next
        # thumbnail.
        self.setFixedWidth(THUMB.width())

    # ---- the cog menu --------------------------------------------------

    def _catalog(self):
        return getattr(self.engine, "catalog", None)

    def _open_menu(self):
        menu = QMenu(self)
        prompt = (self.entry or {}).get("prompt") or ""
        favourite = bool((self.entry or {}).get("favourite"))

        copy = menu.addAction("Copy prompt")
        copy.setEnabled(bool(prompt))
        if not prompt:
            copy.setToolTip("No prompt was recorded for this image")
        copy.triggered.connect(self._copy_prompt)

        fav = menu.addAction("Unfavourite photo" if favourite
                             else "Favourite photo")
        fav.triggered.connect(self._toggle_favourite)

        menu.addAction("Uncensor photo" if self.censored
                       else "Censor photo", self._toggle_censored)

        menu.addAction("Rename photo", self._rename)

        menu.addSeparator()
        delete = menu.addAction("Delete photo")
        # Styled directly rather than through the stylesheet: Qt does not
        # apply property selectors to menu items reliably across styles.
        delete.setIcon(self._dot(theme.DANGER))
        delete.triggered.connect(self._delete)

        # Hold the hover open, or the caption and cog vanish the moment
        # the pointer moves onto the menu.
        self.image.set_menu_open(True)
        menu.aboutToHide.connect(lambda: self.image.set_menu_open(False))
        menu.exec(self.image.mapToGlobal(
            self.image.cog.geometry().bottomLeft()))

    @staticmethod
    def _dot(colour):
        """A small colour swatch, used to mark the destructive action."""
        pm = QPixmap(10, 10)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(colour))
        p.setPen(Qt.NoPen)
        p.drawEllipse(1, 1, 8, 8)
        p.end()
        return QIcon(pm)

    def _copy_prompt(self):
        prompt = (self.entry or {}).get("prompt") or ""
        if prompt:
            QApplication.clipboard().setText(prompt)

    def _expand(self):
        """Ask the gallery to open this image, starting from here."""
        if callable(self.on_expand):
            self.on_expand(self.path, self.image)

    def _blurred(self, pixmap):
        """
        A heavily blurred copy of a thumbnail.

        Done by scaling right down and back up rather than with a blur
        filter: at thumbnail size the result is indistinguishable, it
        costs a fraction as much, and - the part that matters - shrinking
        to a dozen pixels genuinely discards the detail rather than
        hiding it behind something that could be undone.
        """
        if pixmap is None or pixmap.isNull():
            return pixmap
        small = pixmap.scaled(max(3, pixmap.width() // 26),
                             max(3, pixmap.height() // 26),
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        return small.scaled(pixmap.size(), Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation)

    def _toggle_censored(self):
        engine = self.engine
        if engine is None or not hasattr(engine, "set_censored"):
            return
        engine.set_censored(self.path, not self.censored)
        self.on_changed()

    def _toggle_favourite(self):
        catalog = self._catalog()
        if catalog is None:
            return
        now = not catalog.is_favourite(self.path)
        catalog.set_favourite(self.path, now)
        self.entry = catalog.lookup(self.path) or {}
        self.image.set_favourite(now)

    def _rename(self):
        """
        Ask for a new name, and keep asking if it is not usable.

        The dialog stays open on a clash or a bad character rather than
        closing and losing what was typed.
        """
        engine = self.engine
        if engine is None or not hasattr(engine, "rename_image"):
            return
        dialog = RenameImage(self.path, self.image.pixmap(), self)
        while dialog.exec() == QDialog.Accepted:
            ok, message = engine.rename_image(self.path, dialog.new_stem())
            if ok or not message:
                break
            dialog.show_error(message)
        else:
            return
        self.on_changed()

    def _delete(self):
        pixmap = self.image.pixmap()
        dialog = ConfirmDelete(self.path, pixmap, self)
        if dialog.exec() != QDialog.Accepted:
            return
        engine = self.engine
        if engine is not None and hasattr(engine, "delete_image"):
            engine.delete_image(self.path)
        else:
            try:
                self.path.unlink()
            except OSError:
                pass
        self.on_changed()


class GalleryPanel(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._all = []         # every image found, newest first
        self._visible = []     # what the filters allow
        self.filters = Filters()
        self.viewer = None
        self._cols = COLS      # recomputed from the panel width
        self._page = 0
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(46)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 12, 0)
        self.count = QLabel("No images yet")
        row.addWidget(self.count)
        row.addStretch(1)

        folder_btn = QPushButton("Open folder")
        folder_btn.clicked.connect(self._open_folder)
        row.addWidget(folder_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(refresh_btn)

        # Destructive, so it wears the same red as Delete and Deny, and
        # sits apart from the two harmless buttons beside it.
        self.purge_btn = QPushButton("Purge")
        self.purge_btn.setObjectName("denyButton")
        self.purge_btn.clicked.connect(self._purge)
        row.addWidget(self.purge_btn)
        outer.addWidget(bar)
        outer.addWidget(self._filter_bar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.grid = QGridLayout(holder)
        self.grid.setContentsMargins(14, 14, 14, 14)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignTop)
        # Pack the columns to the left rather than spreading them across
        # a wide window, which would leave gaps between thumbnails.
        self.grid.setColumnStretch(40, 1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.empty = QLabel(
            "Images will appear here once something has been generated.")
        self.empty.setObjectName("previewEmpty")
        self.empty.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty)
        self.empty.hide()

        # --- paging -----------------------------------------------------
        # Everything on disk is listed; this decides how much of it is
        # drawn at once. Building a thumbnail is not free, so a few
        # hundred images at once would make the panel crawl.
        pager = QWidget()
        pager.setObjectName("statusBar")
        pager.setFixedHeight(44)
        prow = QHBoxLayout(pager)
        prow.setContentsMargins(14, 0, 12, 0)
        prow.setSpacing(8)

        prow.addWidget(QLabel("Show"))
        self.per_page = QComboBox()
        for label, value in PAGE_SIZES:
            self.per_page.addItem(label, value)
        saved = self.engine.s.get("ui.gallery_page_size", 24)
        idx = self.per_page.findData(saved)
        self.per_page.setCurrentIndex(idx if idx >= 0 else 1)
        self.per_page.currentIndexChanged.connect(self._pick_page_size)
        prow.addWidget(self.per_page)
        prow.addWidget(QLabel("per page"))

        prow.addStretch(1)

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(lambda: self._turn_page(-1))
        prow.addWidget(self.prev_btn)

        self.page_label = QLabel("")
        self.page_label.setObjectName("fieldLabel")
        prow.addWidget(self.page_label)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(lambda: self._turn_page(1))
        prow.addWidget(self.next_btn)
        outer.addWidget(pager)

    # ---- paging --------------------------------------------------------

    def _page_size(self):
        value = self.per_page.currentData()
        return None if value in (None, 0) else int(value)

    def _page_count(self):
        size = self._page_size()
        if not size:
            return 1
        return max(1, (len(self._visible) + size - 1) // size)

    def _pick_page_size(self, _i):
        self.engine.s.set("ui.gallery_page_size", self.per_page.currentData())
        self.engine.s.save()
        self._page = 0
        self._rebuild()

    def _turn_page(self, delta):
        self._page = max(0, min(self._page_count() - 1, self._page + delta))
        self._rebuild()

    # ---- data ----------------------------------------------------------

    def _folders(self):
        out = []
        for key, fallback in (("paths.overlay_dir", "output"),
                              ("paths.manual_dir", "")):
            try:
                if key == "paths.manual_dir" and not self.engine.s.get(key):
                    # Blank means the Desktop; the engine owns that default.
                    from avcore.engine import _desktop
                    p = _desktop()
                else:
                    p = self.engine.s.dir_for(key, fallback)
            except OSError:
                continue
            if p.exists() and p not in out:
                out.append(p)
        return out

    def _find_images(self):
        """
        Every image worth showing, newest first, listed once each.

        No cap. There used to be a hard limit of 60 here, unrelated to
        anything the user had set, so with "keep last" above that the
        extra images - favourites among them - simply could not be
        reached. How many appear at once is a paging question, not a
        question of which images exist.

        A manual image exists twice on disk: where it was saved, and as a
        mirror in the overlay folder so the web server can serve it
        without exposing the whole save directory. Both are real files,
        but they are one picture, so the gallery lists them once.

        The saved copy wins, because the mirror is subject to pruning -
        showing the mirror would make an entry disappear from the gallery
        while the user still has the file.
        """
        folders = self._folders()
        overlay = folders[0] if folders else None

        found = {}
        for folder in folders:
            is_mirror = overlay is not None and folder == overlay
            for f in folder.iterdir():
                if f.suffix.lower() not in EXTS or f.name.startswith("_"):
                    continue
                existing = found.get(f.name)
                if existing is None or (existing[1] and not is_mirror):
                    found[f.name] = (f, is_mirror)

        images = [entry[0] for entry in found.values()]
        images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return images

    def refresh(self):
        """Re-read the folders, then redraw if anything changed."""
        images = self._find_images()

        # Rebuilding only when the set actually changed keeps this cheap
        # enough to call on every engine update.
        if images == self._all:
            return
        self._all = images
        self._apply_filters()
        self._page = min(self._page, self._page_count() - 1)
        self._rebuild()

    def _rebuild(self):
        """Draw the current page of whatever the filters allow."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        size = self._page_size()
        if size:
            start = self._page * size
            page = self._visible[start:start + size]
        else:
            start, page = 0, self._visible

        cols = self._columns()
        self._cols = cols
        catalog = getattr(self.engine, "catalog", None)
        for i, path in enumerate(page):
            entry = catalog.lookup(path) if catalog is not None else None
            self.grid.addWidget(
                Thumb(path, self._push, entry, on_changed=self._rebuild_all,
                      engine=self.engine, on_expand=self._open_viewer),
                i // cols, i % cols)

        total = len(self._visible)
        known = 0
        if catalog is not None:
            known = sum(1 for p in self._visible if catalog.lookup(p))

        if self.filters.active():
            count = f"{total} of {len(self._all)} images"
        else:
            count = (f"{total} image{'s' if total != 1 else ''}"
                     if total else "No images yet")
        if total and known < total:
            # Say why some have no caption, rather than leaving it to be
            # discovered by hovering over them.
            count += f"   ({total - known} without a recorded prompt)"
        if size and total > size:
            count += f"   showing {start + 1}-{start + len(page)}"
        self.count.setText(count)

        if not total and self.filters.active():
            self.empty.setText("Nothing matches those filters.")
        else:
            self.empty.setText(
                "Images will appear here once something has been generated.")
        self.empty.setVisible(not total)

        pages = self._page_count()
        self.page_label.setText(f"Page {self._page + 1} of {pages}"
                                if pages > 1 else "")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < pages - 1)
        self.prev_btn.setVisible(pages > 1)
        self.next_btn.setVisible(pages > 1)
        self._sync_purge()
        viewer = getattr(self, "viewer", None)
        if viewer is not None and viewer.isVisible():
            viewer.setGeometry(self._viewer_bounds())

    def _rebuild_all(self):
        """Force a full re-read, after something changed on disk."""
        self._all = []
        self.refresh()

    def _columns(self):
        """
        How many thumbnails fit across right now.

        Fixed columns either waste most of a maximised window or overflow
        a narrow one, and this panel is the same width as whatever layout
        it happens to be in.
        """
        width = self.width() - 40          # grid margins
        step = THUMB.width() + 12          # thumbnail plus spacing
        return max(1, width // step)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._columns() != self._cols:
            # Force a rebuild; refresh() skips when the file list is
            # unchanged, which it is here.
            self._rebuild()

    def _push(self, path):
        self.engine.publish_overlay(path, source="manual")

    def _open_folder(self):
        folders = self._folders()
        if folders:
            os.startfile(str(folders[0]))

    def on_state(self, snapshot):
        # Only rescan when the image count moved; refresh() no-ops if the
        # file list is unchanged anyway.
        if snapshot.get("generated") != getattr(self, "_last_count", None):
            self._last_count = snapshot.get("generated")
            self.refresh()

    # ---- filtering -----------------------------------------------------

    def _filter_bar(self):
        """
        The row of filters above the grid.

        Text boxes react as you type rather than needing Enter, since the
        list is already in memory and narrowing it is instant.
        """
        bar = QWidget()
        bar.setObjectName("filterBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 12, 8)
        row.setSpacing(8)

        self.date_pick = QComboBox()
        for label, value in DATE_RANGES:
            self.date_pick.addItem(label, value)
        self.date_pick.currentIndexChanged.connect(self._read_filters)
        row.addWidget(self.date_pick)

        self.name_box = QLineEdit()
        self.name_box.setPlaceholderText("Name contains")
        self.name_box.setClearButtonEnabled(True)
        self.name_box.textChanged.connect(self._read_filters)
        row.addWidget(self.name_box, 1)

        self.prompt_box = QLineEdit()
        self.prompt_box.setPlaceholderText("Prompt contains")
        self.prompt_box.setClearButtonEnabled(True)
        self.prompt_box.textChanged.connect(self._read_filters)
        row.addWidget(self.prompt_box, 2)

        self.source_pick = QComboBox()
        for label, value in SOURCES:
            self.source_pick.addItem(label, value)
        self.source_pick.currentIndexChanged.connect(self._read_filters)
        row.addWidget(self.source_pick)

        self.kind_pick = QComboBox()
        self.kind_pick.addItem("Any type", "any")
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            self.kind_pick.addItem(ext.lstrip(".").upper(), ext)
        self.kind_pick.currentIndexChanged.connect(self._read_filters)
        row.addWidget(self.kind_pick)

        # Three states rather than two: left click shows only favourites,
        # right click hides them, and either button returns it to neutral
        # from the state it put it in.
        self.fav_only = TriStateFilter("Favourites")
        self.fav_only.state_changed.connect(lambda _s: self._read_filters())
        row.addWidget(self.fav_only)

        self.censor_only = TriStateFilter("Censored", noun="censored images")
        self.censor_only.state_changed.connect(
            lambda _s: self._read_filters())
        row.addWidget(self.censor_only)

        self.clear_filters_btn = QPushButton("Clear")
        self.clear_filters_btn.setToolTip("Remove all filters")
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        self.clear_filters_btn.hide()
        row.addWidget(self.clear_filters_btn)
        return bar

    def _read_filters(self, *_args):
        self.filters.date = self.date_pick.currentData()
        self.filters.name = self.name_box.text()
        self.filters.prompt = self.prompt_box.text()
        self.filters.source = self.source_pick.currentData() or "any"
        self.filters.kind = self.kind_pick.currentData() or "any"
        # neutral / include / exclude maps to any / only / hide.
        states = {'neutral': 'any', 'include': 'only', 'exclude': 'hide'}
        self.filters.favourites = states[self.fav_only.state()]
        self.filters.censored = states[self.censor_only.state()]
        self.clear_filters_btn.setVisible(self.filters.active())
        # Narrowing the list can leave the current page past the end.
        self._page = 0
        self._apply_filters()
        self._rebuild()

    def _clear_filters(self):
        for widget in (self.date_pick, self.source_pick, self.kind_pick):
            widget.blockSignals(True)
            widget.setCurrentIndex(0)
            widget.blockSignals(False)
        for widget in (self.name_box, self.prompt_box):
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        for toggle in (self.fav_only, self.censor_only):
            toggle.blockSignals(True)
            toggle.set_state(TriStateFilter.NEUTRAL)
            toggle.blockSignals(False)
        self._read_filters()

    def _apply_filters(self):
        """Narrow the full list down to what the filters allow."""
        catalog = getattr(self.engine, "catalog", None)
        if not self.filters.active():
            self._visible = list(self._all)
            return
        favourites = catalog.favourites() if catalog is not None else set()
        hidden = catalog.censored() if catalog is not None else set()
        keep = []
        for path in self._all:
            entry = catalog.lookup(path) if catalog is not None else None
            if self.filters.matches(path, entry, path.name in favourites,
                                    path.name in hidden):
                keep.append(path)
        self._visible = keep


    def _viewer_bounds(self):
        """The gallery's own area, expressed in the window."""
        window = self.window()
        return QRect(self.mapTo(window, QPoint(0, 0)), self.size())

    def _open_viewer(self, path, thumb_widget):
        """
        Expand an image, growing out of the thumbnail that asked.

        The list handed over is what is currently visible, not everything
        on disk: arrowing through a filtered gallery should walk the
        images the filter chose, or the filter would mean nothing as soon
        as the picture got bigger.
        """
        if getattr(self, "viewer", None) is None:
            # Parented to the window rather than to the gallery, so it
            # can sit above the decoration layer - which is itself a
            # child of the window. A child of the gallery can never rise
            # above one of the window's own children, whatever it does
            # with raise_.
            self.viewer = ImageViewer(self.window())
            self.viewer.closed.connect(self._viewer_closed)

        shown = list(self._visible)
        if path not in shown:
            shown = [path]
        index = shown.index(path)

        # Where the thumbnail sits, in the window's coordinates now that
        # the viewer lives there.
        window = self.window()
        top_left = thumb_widget.mapTo(window, QPoint(0, 0))
        home = QRect(top_left, thumb_widget.size())

        catalog = getattr(self.engine, "catalog", None)
        censored = catalog.censored() if catalog is not None else set()
        captions = {}
        if catalog is not None:
            for item in shown:
                entry = catalog.lookup(item)
                if entry and entry.get("prompt"):
                    captions[item.name] = entry["prompt"]

        self.viewer.setGeometry(self._viewer_bounds())
        self.viewer.open_at(shown, index, home, censored, captions)
        # Above the decoration, and above everything else the window
        # stacks over its panels.
        self.viewer.raise_()

    def _viewer_closed(self):
        # The censor marks may have changed while it was open.
        self._rebuild_all()

    def _purge(self):
        """
        Empty the gallery of everything not favourited.

        The count is taken from the engine rather than from what is on
        screen: filters and paging mean the grid often shows a fraction
        of what exists, and purging more than the user can see would be a
        nasty surprise.
        """
        engine = self.engine
        if engine is None or not hasattr(engine, "purgeable"):
            return
        doomed = engine.purgeable()
        if not doomed:
            return

        catalog = getattr(engine, "catalog", None)
        favourites = len(catalog.favourites()) if catalog else 0
        if ConfirmPurge(len(doomed), favourites,
                        self).exec() != QDialog.Accepted:
            return

        removed, failed = engine.purge_images()
        self._rebuild_all()
        if failed:
            self.count.setText(
                f"Removed {removed}; {failed} could not be deleted")

    def _sync_purge(self):
        """Nothing to purge means nothing to press."""
        button = getattr(self, "purge_btn", None)
        if button is None:
            return
        engine = self.engine
        count = len(engine.purgeable()) if hasattr(engine, "purgeable") else 0
        button.setEnabled(count > 0)
        button.setToolTip(
            f"Delete {count} image{'s' if count != 1 else ''} that are not "
            f"favourited" if count
            else "Nothing to purge - every image is a favourite")
