"""
First-run setup panel.

Downloads happen on a worker thread and report back through Qt signals, so
the window stays responsive through an 8 GB transfer and the Cancel button
actually works.
"""

import threading

from PySide6.QtCore import QTimer, Qt, QObject, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QRadioButton,
    QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from avcore import setup as avsetup
from avcore.comfy_launcher import ComfyLauncher


class SetupWorker(QObject):
    progress = Signal(dict)
    step = Signal(str, str)
    finished = Signal(bool, str)

    def __init__(self, settings, root):
        super().__init__()
        self.s = settings
        self.root = root
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        inst = avsetup.Installer(
            self.s,
            on_progress=lambda **kw: self.progress.emit(kw),
            on_step=lambda key, text: self.step.emit(key, text),
            cancel=self._cancel.is_set,
        )
        try:
            inst.run(root=self.root)
        except avsetup.SetupCancelled:
            self.finished.emit(False, "Stopped. Anything downloaded so far "
                                      "is kept, so it will carry on from "
                                      "there next time.")
            return
        except Exception as exc:
            self.finished.emit(False, str(exc))
            return
        self.finished.emit(True, "Everything is installed.")


class CheckRow(QWidget):
    """One requirement, with a status mark and a line of explanation."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(10)

        self.mark = QLabel("\u2022")
        self.mark.setFixedWidth(16)
        self.mark.setAlignment(Qt.AlignCenter)
        self.title = QLabel(title)
        self.title.setMinimumWidth(150)
        self.detail = QLabel("checking...")
        self.detail.setObjectName("fieldLabel")
        self.detail.setWordWrap(True)

        row.addWidget(self.mark)
        row.addWidget(self.title)
        row.addWidget(self.detail, 1)

    def set_state(self, ok, detail):
        from . import theme
        if ok is None:
            self.mark.setText("\u2022")
            colour = theme.MUTED
        elif ok:
            self.mark.setText("\u2713")
            colour = theme.OK
        else:
            self.mark.setText("\u2715")
            colour = theme.WORKING
        self.mark.setStyleSheet(f"color: {colour}; font-weight: 600;")
        self.detail.setText(detail)


class ConfirmInstall(QDialog):
    """Asks before a download measured in gigabytes."""

    def __init__(self, label, size, where, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install model")
        self.setModal(True)
        self.setMinimumWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        title = QLabel(f"Install {label}?")
        title.setObjectName("dialogTitle")
        outer.addWidget(title)

        body = QLabel(
            f"This downloads about {size} into\n{where}\n\n"
            f"ComfyUI is installed alongside it if it is not already "
            f"there. The download can be stopped and picked up later.")
        body.setWordWrap(True)
        body.setObjectName("fieldLabel")
        outer.addWidget(body)

        row = QHBoxLayout()
        row.addStretch(1)
        deny = QPushButton("Not now")
        deny.setObjectName("denyButton")
        deny.clicked.connect(self.reject)
        row.addWidget(deny)
        go = QPushButton(f"Install {size}")
        go.setObjectName("confirmButton")
        go.clicked.connect(self.accept)
        row.addWidget(go)
        outer.addLayout(row)
        deny.setDefault(True)
        deny.setFocus()


class ConfirmUninstall(QDialog):
    """Asks before deleting a model, and says what it costs to undo."""

    def __init__(self, label, size, in_use, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove model")
        self.setModal(True)
        self.setMinimumWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        title = QLabel(f"Remove {label}?")
        title.setObjectName("dialogTitle")
        outer.addWidget(title)

        words = [f"This frees {size}. Getting it back means downloading "
                 f"it again."]
        if in_use:
            words.append(
                "It is the model in use, so generating will fall back to "
                "whatever else is installed, or to Pollinations if "
                "nothing is.")
        body = QLabel("\n\n".join(words))
        body.setWordWrap(True)
        body.setObjectName("fieldLabel")
        outer.addWidget(body)

        row = QHBoxLayout()
        row.addStretch(1)
        deny = QPushButton("Keep it")
        deny.setObjectName("denyButton")
        deny.clicked.connect(self.reject)
        row.addWidget(deny)
        go = QPushButton(f"Remove and free {size}")
        go.setObjectName("confirmButton")
        go.clicked.connect(self.accept)
        row.addWidget(go)
        outer.addLayout(row)
        deny.setDefault(True)
        deny.setFocus()


class SetupPanel(QWidget):
    ready_changed = Signal(bool)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.s = engine.s
        self.worker = None
        self.thread = None
        self.launcher = ComfyLauncher(self.s)
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        title = QLabel("Setup")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        outer.addWidget(title)

        blurb = QLabel(
            "Images can be generated on this computer, or online without "
            "installing anything. Generating here is private, unlimited "
            "and unwatermarked, but it needs ComfyUI and a model - "
            "several gigabytes, fetched below."
        )
        blurb.setObjectName("fieldLabel")
        blurb.setWordWrap(True)
        outer.addWidget(blurb)

        outer.addWidget(self._how_section())

        self.rows = {
            "gpu": CheckRow("Graphics card"),
            "space": CheckRow("Disk space"),
            "comfy": CheckRow("ComfyUI"),
            "model": CheckRow("Image model"),
        }
        for row in self.rows.values():
            outer.addWidget(row)

        loc = QHBoxLayout()
        loc.setSpacing(8)
        loc.addWidget(QLabel("Install to"))
        self.where = QLabel("")
        self.where.setObjectName("fieldLabel")
        self.where.setWordWrap(True)
        loc.addWidget(self.where, 1)
        self.browse = QPushButton("Change")
        self.browse.clicked.connect(self._pick_folder)
        loc.addWidget(self.browse)
        outer.addLayout(loc)

        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        self.bar.setRange(0, 1000)
        self.bar.hide()
        outer.addWidget(self.bar)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.install_btn = QPushButton("Install everything")
        self.install_btn.setObjectName("primaryButton")
        self.install_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Stop")
        self.cancel_btn.clicked.connect(self._stop)
        self.cancel_btn.hide()
        self.recheck_btn = QPushButton("Check again")
        self.recheck_btn.clicked.connect(self.refresh)

        buttons.addWidget(self.install_btn)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.recheck_btn)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        outer.addStretch(1)

    # ---- state ---------------------------------------------------------

    def _how_section(self):
        """
        How images get made, and what is on disk to make them with.

        One row per option, each carrying its own buttons, because the
        two questions people actually have - "have I got this?" and "can
        I use it now?" - are about a particular model rather than about
        the list.
        """
        from avcore.setup import TIERS

        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 4, 0, 4)
        column.setSpacing(6)

        self.how = QButtonGroup(self)
        self.tier_rows = {}

        online = QRadioButton(
            "Online - nothing to download (Pollinations.ai)")
        online.setToolTip(
            "Images are made by Pollinations.ai. No install, no graphics "
            "card needed. They come back watermarked and it can be slow "
            "when busy.")
        self.how.addButton(online, 0)
        column.addWidget(online)
        self._tier_keys = [""]

        for index, (key, spec) in enumerate(TIERS.items(), start=1):
            row = QHBoxLayout()
            row.setSpacing(8)

            button = QRadioButton(f"On this computer - {spec['label']}")
            button.setToolTip(spec["note"])
            self.how.addButton(button, index)
            row.addWidget(button, 1)

            install = QPushButton("Install")
            install.clicked.connect(
                lambda _c=False, k=key: self._install_tier(k))
            row.addWidget(install)

            use = QPushButton("Use")
            use.setToolTip(
                "Switch to this model without going to Settings")
            use.clicked.connect(lambda _c=False, k=key: self._use_tier(k))
            row.addWidget(use)

            column.addLayout(row)

            note = QLabel("      " + spec["note"])
            note.setObjectName("fieldLabel")
            note.setWordWrap(True)
            column.addWidget(note)

            self._tier_keys.append(key)
            self.tier_rows[key] = {
                "radio": button, "install": install, "use": use,
                "note": note,
            }

        self.how.idClicked.connect(self._pick_how)
        return box

    def _sync_tiers(self):
        """
        Make the buttons say what they will do.

        Called on every refresh rather than only when something changes,
        because a model can arrive or vanish through the browser, the
        Settings panel, or Explorer.
        """
        from avcore.setup import TIERS, models_for_tier, tier_file

        current = (self.s.get("comfyui.checkpoint") or "").strip()
        online = (self.s.get("image.backend", "comfyui") or "") != "comfyui"
        here = []

        for key, row in self.tier_rows.items():
            spec = TIERS[key]
            models = models_for_tier(key, self.s)
            have = bool(models)
            if have:
                here.append(key)

            # Only what setup fetched is offered for removal. A model the
            # user found themselves also satisfies this option, but
            # deleting it from a button marked "Uninstall Stable
            # Diffusion XL" would be a nasty surprise - that belongs in
            # the model manager, where it is named.
            official = tier_file(key, self.s)
            ours = official.exists()
            row["install"].setText("Uninstall" if ours else "Install")
            row["install"].setEnabled(ours or not have)
            row["install"].setToolTip(
                "" if ours or not have else
                "Already covered by a model you installed yourself. "
                "Remove that one from Settings, Get more models.")
            row["install"].setObjectName("denyButton" if ours else "")
            # Qt only restyles on a change of name, so the widget has to
            # be told to look again.
            row["install"].style().unpolish(row["install"])
            row["install"].style().polish(row["install"])

            in_use = (not online
                      and any(current == m.name for m in models))
            row["use"].setEnabled(have and not in_use)
            row["use"].setText("In use" if in_use else "Use")

            size = f"{spec['bytes'] / 1_073_741_824:.1f} GB"
            if ours:
                detail = "   Installed."
            elif have:
                names = ", ".join(m.name for m in models[:2])
                extra = "" if len(models) <= 2 else f" and {len(models) - 2} more"
                detail = f"   Installed already: {names}{extra}"
            else:
                detail = f"   Not installed, {size} to download."
            row["note"].setText("      " + spec["note"] + detail)

        # Nothing is written here. This runs on a timer while the page
        # is visible, and a refresh that saves settings will fight the
        # person using it: the old version flipped anyone with no models
        # over to Pollinations every two seconds, including while they
        # were part way through installing one.
        if online:
            wanted = 0
        else:
            wanted = self._row_for_current(here)

        button = self.how.button(wanted)
        if button is not None and not button.isChecked():
            self.how.blockSignals(True)
            button.setChecked(True)
            self.how.blockSignals(False)

    def _row_for_current(self, here):
        """
        Which row matches the model in use.

        Matched against the models that actually satisfy each option,
        not against the official filename. Comparing filenames meant a
        checkpoint the user had found themselves matched nothing, so
        this fell back to the first installed option and dragged the tick
        back to Stable Diffusion 1.5 every couple of seconds however
        many times they clicked the other one.
        """
        from avcore.setup import models_for_tier

        current = (self.s.get("comfyui.checkpoint") or "").strip()
        if current:
            for index, key in enumerate(self._tier_keys):
                if not key:
                    continue
                if any(m.name == current for m in models_for_tier(key, self.s)):
                    return index

        # No particular model chosen: fall back to the remembered
        # choice, then to whatever is installed.
        remembered = (self.s.get("models.tier") or "").strip()
        if remembered in self._tier_keys and remembered in here:
            return self._tier_keys.index(remembered)
        if here:
            return self._tier_keys.index(here[0])
        return 0

    def _pick_how(self, index):
        """
        Record the choice straight away.

        There is no Apply on this screen, and this is the first thing
        someone does in a new install.

        Picking a model that is not installed offers to install it.
        Before, the choice was accepted, found to be unusable, and
        silently snapped back to Online - which looks like the click did
        not register rather than like a decision being asked for.
        """
        from avcore.setup import tier_installed

        key = self._tier_keys[index] if index < len(self._tier_keys) else ""
        if index == 0:
            self.s.set("image.backend", "pollinations")
            self.s.save()
            self.refresh()
            return

        if not tier_installed(key, self.s):
            # _install_tier asks first; if the answer is no, the refresh
            # at the end puts the tick back where it was.
            self._install_tier(key)
            self.refresh()
            return

        self.s.set("image.backend", "comfyui")
        self.s.set("models.tier", key)
        self._use_tier(key, quiet=True)
        self.s.save()
        self.refresh()

    def refresh(self):
        rep = avsetup.check(self.s)
        self.report = rep
        self.where.setText(str(rep["root"]))

        self.rows["gpu"].set_state(
            rep["gpu_ok"],
            rep["gpu_name"] if rep["gpu_ok"] else
            "No NVIDIA GPU detected. Image generation needs one.")

        self.rows["space"].set_state(
            rep["space_ok"],
            f"{avsetup.human(rep['free_bytes'])} free"
            + ("" if rep["space_ok"] else
               f", and about {avsetup.human(avsetup.REQUIRED_FREE_BYTES)} "
               f"is needed"))

        self.rows["comfy"].set_state(
            rep["comfy_ok"],
            "Installed" if rep["comfy_ok"] else "Not installed yet")

        if rep["model_ok"]:
            names = ", ".join(p.name for p in rep["models"][:3])
            self.rows["model"].set_state(True, names)
        else:
            self.rows["model"].set_state(False, "No model yet")

        if rep["ready"]:
            self.status.setText(
                "Everything is in place. You can start listening.")
            self.install_btn.setText("Reinstall")
            self.install_btn.setObjectName("")
        else:
            self.install_btn.setText("Install everything")
            self.install_btn.setObjectName("primaryButton")
            if not rep["gpu_ok"]:
                self.status.setText(
                    "Without an NVIDIA GPU the rest will install but images "
                    "will not generate.")
            else:
                self.status.setText("")

        # Re-apply the stylesheet so the object name change takes effect.
        self.install_btn.style().unpolish(self.install_btn)
        self.install_btn.style().polish(self.install_btn)
        # The per-model rows read the same report, so they are brought
        # up to date in the same pass rather than on their own timer.
        self._sync_tiers()
        self.ready_changed.emit(rep["ready"])
        return rep

    def _pick_folder(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Where should ComfyUI and the model go?",
            str(self.report["root"]))
        if chosen:
            self.s.set("comfyui.path", chosen)
            self.s.save()
            self.refresh()

    # ---- one model at a time ---------------------------------------------

    def _use_tier(self, key, quiet=False):
        """
        Switch generation to this model.

        A shortcut for what Settings does, put here because someone
        standing in front of the list of models should not have to go
        and find another screen to pick one.
        """
        from avcore.setup import TIERS, models_for_tier

        spec = TIERS.get(key)
        if spec is None:
            return
        models = models_for_tier(key, self.s)
        if not models:
            if not quiet:
                self.status.setText(
                    f"{spec['label']} is not installed yet.")
            return

        # Whichever model actually satisfies this option - the official
        # one if setup fetched it, otherwise the user's own.
        self.s.set("image.backend", "comfyui")
        self.s.set("comfyui.checkpoint", models[0].name)
        self.s.set("models.tier", key)
        self.s.save()
        if not quiet:
            self.status.setText(f"Now generating with {spec['label']}.")
        self.refresh()

    def _install_tier(self, key):
        """Install or remove one model, depending on what is there."""
        from avcore.setup import TIERS, tier_file, tier_installed

        spec = TIERS.get(key)
        if spec is None:
            return

        if tier_file(key, self.s).exists():
            self._uninstall_tier(key)
            return

        size = f"{spec['bytes'] / 1_073_741_824:.1f} GB"
        where = tier_file(key, self.s).parent
        if ConfirmInstall(spec["label"], size, where,
                          self).exec() != QDialog.Accepted:
            return

        # ComfyUI comes with it if it is not there yet, which is what the
        # existing installer already does - only the model it fetches
        # depends on the choice.
        self.s.set("models.tier", key)
        self.s.save()
        self._start()

    def _uninstall_tier(self, key):
        from avcore.setup import TIERS, tier_file

        spec = TIERS[key]
        path = tier_file(key, self.s)
        size = f"{path.stat().st_size / 1_073_741_824:.1f} GB"
        in_use = (self.s.get("comfyui.checkpoint") or "") == spec["name"]

        if ConfirmUninstall(spec["label"], size, in_use,
                            self).exec() != QDialog.Accepted:
            return

        try:
            path.unlink()
        except OSError as exc:
            # Almost always ComfyUI holding the file open.
            self.status.setText(
                f"Could not remove {spec['label']}: "
                f"{exc.strerror or exc}. If ComfyUI is running with this "
                f"model loaded, stop it and try again.")
            return

        if in_use:
            self.s.set("comfyui.checkpoint", "")
        self.s.save()
        self.status.setText(f"Removed {spec['label']}, freeing {size}.")
        self.refresh()

    # ---- installing ----------------------------------------------------

    def _start(self):
        if self.thread and self.thread.is_alive():
            return
        root = self.report["root"]

        self.worker = SetupWorker(self.s, root)
        self.worker.progress.connect(self._on_progress)
        self.worker.step.connect(self._on_step)
        self.worker.finished.connect(self._on_finished)

        self.install_btn.hide()
        self.recheck_btn.hide()
        self.browse.setEnabled(False)
        self.cancel_btn.show()
        self.bar.show()
        self.bar.setValue(0)
        self.status.setText("Starting...")

        self.thread = threading.Thread(
            target=self.worker.run, name="av-setup", daemon=True)
        self.thread.start()

    def _stop(self):
        if self.worker:
            self.worker.cancel()
        self.status.setText("Stopping...")

    def _on_step(self, _key, text):
        self.status.setText(text)

    def _on_progress(self, info):
        label = info.get("label", "")
        done = info.get("done", 0)
        total = info.get("total", 0) or 0
        note = info.get("note", "")

        if total:
            self.bar.setValue(int(1000 * done / total))
            pct = 100 * done / total
        else:
            pct = 0

        if note == "already here":
            self.status.setText(f"{label}: already downloaded")
            return

        speed = info.get("speed") or 0
        bits = [f"{label}: {pct:.0f}%"]
        if label == "Unpacking":
            bits = [f"Unpacking: {pct:.0f}%"]
        else:
            bits.append(
                f"{avsetup.human(done)} of {avsetup.human(total)}"
                if total else avsetup.human(done))
            if speed > 0:
                bits.append(f"{avsetup.human(speed)}/s")
                if total and done < total:
                    left = (total - done) / speed
                    bits.append(f"{int(left // 60)}m {int(left % 60)}s left")
        self.status.setText("   ".join(bits))

    def _on_finished(self, ok, message):
        self.bar.hide()
        self.cancel_btn.hide()
        self.install_btn.show()
        self.recheck_btn.show()
        self.browse.setEnabled(True)
        self.status.setText(message)
        self.refresh()

    def showEvent(self, event):
        """
        Re-check on arrival, and keep checking while visible.

        A model can appear or vanish from the browser, from Settings, or
        from Explorer, and this page is the one claiming to say what is
        installed. Polling only while it is on screen keeps it honest
        without costing anything the rest of the time - the check reads
        cached headers and takes about a hundredth of a second.
        """
        super().showEvent(event)
        self._default_to_online_once()
        self.refresh()
        if not hasattr(self, "_watch"):
            self._watch = QTimer(self)
            self._watch.setInterval(2000)
            self._watch.timeout.connect(self._recheck_models)
        self._watch.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        watch = getattr(self, "_watch", None)
        if watch is not None:
            watch.stop()

    def _default_to_online_once(self):
        """
        Start a fresh install on the online option.

        Only when nothing is installed and nothing has ever been chosen,
        and only once - this is a helpful starting point, not a rule to
        enforce against someone who has picked ComfyUI and is about to
        install a model.
        """
        from avcore.setup import installed_tiers

        if getattr(self, "_defaulted", False):
            return
        self._defaulted = True

        chosen_before = bool((self.s.get("models.tier") or "").strip()
                             or (self.s.get("comfyui.checkpoint") or "").strip())
        if chosen_before or installed_tiers(self.s):
            return
        if (self.s.get("image.backend", "comfyui") or "") == "comfyui":
            self.s.set("image.backend", "pollinations")
            self.s.save()

    def _recheck_models(self):
        """
        Refresh only when what is installed has actually changed.

        A full refresh every two seconds would fight with anything the
        user is doing, so the cheap question is asked first.
        """
        from avcore.setup import installed_tiers

        if self.thread and self.thread.is_alive():
            return
        here = tuple(installed_tiers(self.s))
        if here != getattr(self, "_last_seen_models", None):
            self._last_seen_models = here
            self.refresh()

    def on_state(self, _snapshot):
        # Setup reflects the filesystem, not the engine.
        pass
