from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from voirol.core.config import save_config
from voirol.gui.m3 import M3Button, M3ElevatedCard, M3LinearProgress, M3TextField
from voirol.gui.settings.base_tab import SettingsTab
from voirol.gui.settings.workers import TesseractInstallThread
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger
from voirol.voice import model_download as md

logger = get_logger("gui.settings.model_tab")


class ModelTab(SettingsTab):
    def _build_ui(self):
        self._dl_thread = None
        self._dl_worker = None
        self._tesseract_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._mirror_label = QLabel(t("model.mirror_url"))
        layout.addWidget(self._mirror_label)

        mirror_layout = QHBoxLayout()
        self._mirror_input = M3TextField(placeholder="https://ghproxy.com")
        self._mirror_input.setText(self.pipeline.config.download.get("mirror_url", ""))
        self._mirror_input.textChanged.connect(self._on_mirror_changed)
        mirror_layout.addWidget(self._mirror_input)

        self._test_mirror_btn = M3Button(t("model.test_mirror"), variant=M3Button.Variant.OUTLINED)
        self._test_mirror_btn.clicked.connect(self._on_test_mirror)
        mirror_layout.addWidget(self._test_mirror_btn)

        self._mirror_status = QLabel("")
        mirror_layout.addWidget(self._mirror_status)
        layout.addLayout(mirror_layout)

        self._hf_label = QLabel(t("model.hf_mirror_url"))
        layout.addWidget(self._hf_label)

        hf_layout = QHBoxLayout()
        self._hf_mirror_input = M3TextField(placeholder="https://hf-mirror.com")
        self._hf_mirror_input.setText(self.pipeline.config.download.get("hf_mirror_url", ""))
        self._hf_mirror_input.textChanged.connect(self._on_hf_mirror_changed)
        hf_layout.addWidget(self._hf_mirror_input)
        self._hf_mirror_status = QLabel("")
        hf_layout.addWidget(self._hf_mirror_status)
        layout.addLayout(hf_layout)

        layout.addSpacing(8)

        self._model_table = QTableWidget()
        self._model_table.setColumnCount(3)
        self._model_table.setHorizontalHeaderLabels([
            t("model.name"), t("model.size"), t("model.status")
        ])
        self._model_table.horizontalHeader().setStretchLastSection(True)
        self._model_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._model_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._model_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._model_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._model_table)

        btn_layout = QHBoxLayout()
        self._download_btn = M3Button(t("model.download_selected"), variant=M3Button.Variant.FILLED)
        self._download_btn.clicked.connect(self._on_download_selected)
        btn_layout.addWidget(self._download_btn)

        self._download_all_btn = M3Button(t("model.download_all"), variant=M3Button.Variant.FILLED)
        self._download_all_btn.clicked.connect(self._on_download_all)
        btn_layout.addWidget(self._download_all_btn)
        layout.addLayout(btn_layout)

        self._progress_group = M3ElevatedCard(title=t("model.progress_panel"))
        self._progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_group)
        progress_layout.setContentsMargins(16, 16, 16, 16)
        progress_layout.setSpacing(4)
        self._progress_card_title = QLabel(t("model.progress_panel"))
        progress_layout.addWidget(self._progress_card_title)
        self._dl_rows: dict[str, tuple[M3LinearProgress, QLabel]] = {}
        for mid in md.DOWNLOAD_ORDER:
            row_layout = QHBoxLayout()
            name_label = QLabel(md.MODELS[mid].name)
            name_label.setFixedWidth(120)
            row_layout.addWidget(name_label)
            bar = M3LinearProgress(determinate=True)
            bar.set_value(0)
            row_layout.addWidget(bar, stretch=1)
            status_label = QLabel("")
            status_label.setFixedWidth(80)
            row_layout.addWidget(status_label)
            progress_layout.addLayout(row_layout)
            self._dl_rows[mid] = (bar, status_label)
        layout.addWidget(self._progress_group)

        layout.addSpacing(16)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        tesseract_group = M3ElevatedCard(title=t("tesseract.title"))
        tesseract_layout = QVBoxLayout(tesseract_group)
        tesseract_layout.setContentsMargins(16, 16, 16, 16)
        tesseract_layout.setSpacing(6)

        self._tesseract_card_title = QLabel(t("tesseract.title"))
        tesseract_layout.addWidget(self._tesseract_card_title)

        self._tesseract_status = QLabel("")
        tesseract_layout.addWidget(self._tesseract_status)

        path_layout = QHBoxLayout()
        path_label = QLabel(t("tesseract.command_path").format(path=""))
        path_label.setObjectName("tesseract_path_label")
        path_layout.addWidget(path_label)
        path_layout.addStretch()
        tesseract_layout.addLayout(path_layout)

        self._tesseract_lang_label = QLabel(t("tesseract.language_packs"))
        tesseract_layout.addWidget(self._tesseract_lang_label)

        self._tesseract_lang_eng = QLabel()
        tesseract_layout.addWidget(self._tesseract_lang_eng)
        self._tesseract_lang_chi = QLabel()
        tesseract_layout.addWidget(self._tesseract_lang_chi)

        btn_layout2 = QHBoxLayout()
        self._tesseract_check_btn = M3Button(t("tesseract.check"), variant=M3Button.Variant.OUTLINED)
        self._tesseract_check_btn.clicked.connect(self._on_tesseract_check)
        btn_layout2.addWidget(self._tesseract_check_btn)

        self._tesseract_install_btn = M3Button(t("tesseract.download_install"), variant=M3Button.Variant.FILLED)
        self._tesseract_install_btn.clicked.connect(self._on_tesseract_install)
        btn_layout2.addWidget(self._tesseract_install_btn)
        tesseract_layout.addLayout(btn_layout2)

        self._tesseract_progress = M3LinearProgress(determinate=True)
        self._tesseract_progress.set_value(0)
        self._tesseract_progress.setVisible(False)
        tesseract_layout.addWidget(self._tesseract_progress)

        self._tesseract_progress_label = QLabel("")
        tesseract_layout.addWidget(self._tesseract_progress_label)

        layout.addWidget(tesseract_group)
        layout.addStretch()

        self._refresh_model_table()
        self._check_resume_queue()
        self._refresh_tesseract_status()

    def retranslate_ui(self):
        self._mirror_label.setText(t("model.mirror_url"))
        self._mirror_input.setPlaceholderText("https://ghproxy.com")
        self._test_mirror_btn.setText(t("model.test_mirror"))
        self._hf_label.setText(t("model.hf_mirror_url"))
        self._hf_mirror_input.setPlaceholderText("https://hf-mirror.com")
        self._model_table.setHorizontalHeaderLabels([
            t("model.name"), t("model.size"), t("model.status")
        ])
        self._download_btn.setText(t("model.download_selected"))
        self._download_all_btn.setText(t("model.download_all"))
        self._progress_card_title.setText(t("model.progress_panel"))
        self._refresh_model_table()
        self._tesseract_card_title.setText(t("tesseract.title"))
        self._tesseract_lang_label.setText(t("tesseract.language_packs"))
        self._tesseract_check_btn.setText(t("tesseract.check"))
        self._tesseract_install_btn.setText(t("tesseract.download_install"))
        self._refresh_tesseract_status()

    def title(self) -> str:
        return t("model.tab")

    def _on_mirror_changed(self):
        self.pipeline.config.download["mirror_url"] = self._mirror_input.text().strip()
        save_config(self.pipeline.config)

    def _on_hf_mirror_changed(self):
        self.pipeline.config.download["hf_mirror_url"] = self._hf_mirror_input.text().strip()
        save_config(self.pipeline.config)

    def _on_test_mirror(self):
        url = self._mirror_input.text().strip()
        if not url:
            self._mirror_status.setText(t("model.test_fail", error="no input"))
            return
        self._test_mirror_btn.setEnabled(False)
        self._mirror_status.setText("...")
        QApplication.processEvents()
        ok, msg = md.test_mirror(url)
        self._mirror_status.setText(
            t("model.test_success", status=msg) if ok
            else t("model.test_fail", error=msg)
        )
        self._test_mirror_btn.setEnabled(True)

    def _refresh_model_table(self):
        self._model_table.setRowCount(0)
        model_ids = ["silero_vad", "sensevoice", "campplus"]
        for mid in model_ids:
            entry = md.MODELS.get(mid)
            if not entry:
                continue
            status = md.check_model_status(mid)
            row = self._model_table.rowCount()
            self._model_table.insertRow(row)
            self._model_table.setItem(row, 0, QTableWidgetItem(entry.name))
            self._model_table.setItem(row, 1, QTableWidgetItem(entry.size))
            if status == md.DownloadState.DOWNLOADED:
                status_text = t("model.status_downloaded")
            elif status == md.DownloadState.AUTO:
                status_text = t("model.status_auto")
            else:
                status_text = t("model.status_missing")
            item = QTableWidgetItem(status_text)
            self._model_table.setItem(row, 2, item)
            name_item = self._model_table.item(row, 0)
            name_item.setData(256, mid)
            if status == md.DownloadState.AUTO:
                from voirol.gui.theme import get_theme_manager
                grey = QColor(get_theme_manager().current_scheme().on_surface_variant)
                for col in range(3):
                    self._model_table.item(row, col).setForeground(grey)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

    def _get_selected_model_id(self) -> str | None:
        row = self._model_table.currentRow()
        if row < 0:
            return None
        return self._model_table.item(row, 0).data(256)

    def _check_resume_queue(self):
        pending = md.load_queue()
        if not pending:
            return
        reply = QMessageBox.question(
            self, t("model.resume_title"),
            t("model.resume_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_queue(pending)

    def _on_download_selected(self):
        mid = self._get_selected_model_id()
        if not mid:
            QMessageBox.warning(self, t("prompt.title"), t("model.select_hint"))
            return
        entry = md.MODELS.get(mid)
        if entry and entry.auto:
            QMessageBox.information(self, t("prompt.title"), t("model.status_auto"))
            return
        self._start_queue([mid])

    def _on_download_all(self):
        pending = [mid for mid in md.DOWNLOAD_ORDER
                   if md.check_model_status(mid) == md.DownloadState.MISSING]
        if not pending:
            return
        self._start_queue(pending)

    def _start_queue(self, model_ids: list[str]):
        mirror = self._mirror_input.text().strip()
        hf_mirror = self._hf_mirror_input.text().strip()
        md.save_queue(model_ids)

        self._progress_group.setVisible(True)
        for mid in md.DOWNLOAD_ORDER:
            bar, status = self._dl_rows[mid]
            st = md.check_model_status(mid)
            if mid in model_ids:
                if mid == model_ids[0]:
                    bar.set_value(0)
                    status.setText("0%")
                else:
                    bar.set_value(0)
                    status.setText(t("model.waiting"))
            elif st == md.DownloadState.DOWNLOADED:
                bar.set_value(100)
                status.setText(t("model.status_downloaded"))
            elif st == md.DownloadState.AUTO:
                bar.set_value(100)
                status.setText(t("model.status_auto"))
            else:
                bar.set_value(0)
                status.setText("—")
        self._download_btn.setEnabled(False)
        self._download_all_btn.setEnabled(False)

        self._dl_thread = QThread()
        self._dl_worker = md.DownloadWorker(model_ids, mirror, hf_mirror)
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.model_finished.connect(self._on_dl_model_finished)
        self._dl_worker.all_finished.connect(self._on_dl_all_finished)
        self._dl_worker.all_finished.connect(self._dl_thread.quit)
        self._dl_worker.all_finished.connect(self._dl_worker.deleteLater)
        self._dl_thread.finished.connect(self._dl_thread.deleteLater)
        self._dl_thread.start()

    def _on_dl_progress(self, model_id: str, pct: int):
        if model_id in self._dl_rows:
            bar, status = self._dl_rows[model_id]
            if pct == -1:
                bar.set_value(0)
                status.setText(t("model.extracting"))
            else:
                bar.set_value(pct)
                status.setText(t("model.progress", pct=pct))

    def _on_dl_model_finished(self, model_id: str, success: bool):
        if model_id in self._dl_rows:
            bar, status = self._dl_rows[model_id]
            ok = success and md.check_model_status(model_id) == md.DownloadState.DOWNLOADED
            bar.set_value(100 if ok else 0)
            status.setText(t("model.done") if ok else t("model.failed"))
        queue = md.load_queue()
        if model_id in queue:
            queue.remove(model_id)
            if queue:
                md.save_queue(queue)
            else:
                md.clear_queue()
        self._refresh_model_table()

    def _on_dl_all_finished(self):
        self._download_btn.setEnabled(True)
        self._download_all_btn.setEnabled(True)
        md.clear_queue()

    def _refresh_tesseract_status(self):
        try:
            from voirol.utils.tesseract_download import (
                check_tesseract_installed, get_tesseract_exe,
                get_version, get_language_packs, TESSEL_DIR,
            )
            installed = check_tesseract_installed()
            if installed:
                ver = get_version()
                exe_path = get_tesseract_exe()
                self._tesseract_status.setText(t("tesseract.installed", version=ver))
                path_label = self.findChild(QLabel, "tesseract_path_label")
                if path_label:
                    path_label.setText(t("tesseract.command_path", path=exe_path or TESSEL_DIR))
                packs = get_language_packs()
                self._tesseract_lang_eng.setText(
                    f"  eng: {t('tesseract.language_pack_found') if 'eng' in packs else t('tesseract.language_pack_missing')}"
                )
                self._tesseract_lang_chi.setText(
                    f"  chi_sim: {t('tesseract.language_pack_found') if 'chi_sim' in packs else t('tesseract.language_pack_missing')}"
                )
            else:
                self._tesseract_status.setText(t("tesseract.not_installed"))
                path_label = self.findChild(QLabel, "tesseract_path_label")
                if path_label:
                    path_label.setText(t("tesseract.no_path"))
                self._tesseract_lang_eng.setText("")
                self._tesseract_lang_chi.setText("")
            self._tesseract_install_btn.setEnabled(not installed)
        except Exception as e:
            logger.warning(f"Tesseract status refresh failed: {e}")

    def _on_tesseract_check(self):
        self._refresh_tesseract_status()

    def _on_tesseract_install(self):
        try:
            self._tesseract_install_btn.setEnabled(False)
            self._tesseract_check_btn.setEnabled(False)
            self._tesseract_progress.setVisible(True)
            self._tesseract_progress.set_value(0)
            self._tesseract_progress_label.setText(t("tesseract.downloading"))
            QApplication.processEvents()

            mirror_url = self.pipeline.config.download.get("mirror_url", "")
            self._tesseract_thread = TesseractInstallThread(mirror_url=mirror_url)
            self._tesseract_thread.progress.connect(self._on_tesseract_progress)
            self._tesseract_thread.status.connect(self._on_tesseract_status)
            self._tesseract_thread.finished.connect(self._on_tesseract_finished)
            self._tesseract_thread.finished.connect(self._tesseract_thread.deleteLater)
            self._tesseract_thread.start()
        except Exception as e:
            logger.error(f"Tesseract install failed to start: {e}")
            self._tesseract_install_btn.setEnabled(True)
            self._tesseract_check_btn.setEnabled(True)
            self._tesseract_progress.setVisible(False)

    def _on_tesseract_progress(self, pct: int):
        if pct == -1:
            self._tesseract_progress_label.setText(t("tesseract.extracting"))
            self._tesseract_progress.set_value(0)
        else:
            self._tesseract_progress.set_value(pct)
            if pct < 100:
                self._tesseract_progress_label.setText(f"{pct}%")

    def _on_tesseract_status(self, text: str):
        self._tesseract_progress_label.setText(text)

    def _on_tesseract_finished(self, success: bool):
        self._tesseract_install_btn.setEnabled(True)
        self._tesseract_check_btn.setEnabled(True)
        if success:
            self._tesseract_progress.set_value(100)
            self._tesseract_progress_label.setText(t("tesseract.ready"))
        else:
            self._tesseract_progress.set_value(0)
            self._tesseract_progress_label.setText(t("tesseract.fail", error=""))
        self._refresh_tesseract_status()

    def cleanup(self):
        for attr in ("_dl_thread", "_tesseract_thread"):
            thread = getattr(self, attr, None)
            if thread is not None and thread.isRunning():
                try:
                    thread.quit()
                    thread.wait(2000)
                except Exception:
                    pass
