import os
import threading

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from voirol.core.config import save_config
from voirol.gui.m3 import M3Button, M3LinearProgress, M3Switch, M3TextField
from voirol.gui.settings.base_tab import SettingsTab
from voirol.utils.i18n import t


class TTSTab(SettingsTab):
    _tts_install_status = pyqtSignal(str)
    _tts_install_done = pyqtSignal()
    _tts_progress = pyqtSignal(int)
    _tts_refresh_ui = pyqtSignal()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        tts_cfg = self.pipeline.config.tts

        tts_enabled_layout = QHBoxLayout()
        self._tts_enabled_cb = M3Switch(checked=tts_cfg.get("enabled", False))
        self._tts_enabled_cb.toggled.connect(self._on_tts_config_changed)
        tts_enabled_layout.addWidget(self._tts_enabled_cb)
        self._tts_enable_label = QLabel(t("tts.enable"))
        tts_enabled_layout.addWidget(self._tts_enable_label)
        tts_enabled_layout.addStretch()
        layout.addLayout(tts_enabled_layout)

        self._tts_voice_label = QLabel(t("tts.voice"))
        layout.addWidget(self._tts_voice_label)

        self._tts_voice_combo = QComboBox()
        from voirol.tts.moss_api import MossApiEngine
        for v in MossApiEngine.list_voices():
            self._tts_voice_combo.addItem(v, v)
        current = tts_cfg.get("voice", "Xiaoyu")
        idx = self._tts_voice_combo.findData(current)
        if idx >= 0:
            self._tts_voice_combo.setCurrentIndex(idx)
        self._tts_voice_combo.currentIndexChanged.connect(self._on_tts_config_changed)
        layout.addWidget(self._tts_voice_combo)

        self._tts_port_label = QLabel(t("tts.port"))
        layout.addWidget(self._tts_port_label)

        self._tts_port_spin = QSpinBox()
        self._tts_port_spin.setRange(1024, 65535)
        self._tts_port_spin.setValue(tts_cfg.get("port", 8080))
        self._tts_port_spin.valueChanged.connect(self._on_tts_config_changed)
        layout.addWidget(self._tts_port_spin)

        self._tts_model_path_label = QLabel(t("tts.model_path"))
        layout.addWidget(self._tts_model_path_label)

        self._tts_model_path = M3TextField()
        self._tts_model_path.setText(tts_cfg.get("model_path", "models/moss-tts-nano"))
        self._tts_model_path.textChanged.connect(self._on_tts_config_changed)
        layout.addWidget(self._tts_model_path)

        self._tts_tok_path_label = QLabel(t("tts.audio_tokenizer_path"))
        layout.addWidget(self._tts_tok_path_label)

        self._tts_tok_path = M3TextField()
        self._tts_tok_path.setText(tts_cfg.get("audio_tokenizer_path", "models/moss-audio-tokenizer-nano"))
        self._tts_tok_path.textChanged.connect(self._on_tts_config_changed)
        layout.addWidget(self._tts_tok_path)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self._tts_mirror_label = QLabel(t("model.mirror_url"))
        layout.addWidget(self._tts_mirror_label)

        mirror_layout = QHBoxLayout()
        self._tts_mirror_input = M3TextField(placeholder="https://ghproxy.com")
        self._tts_mirror_input.setText(self.pipeline.config.download.get("mirror_url", ""))
        self._tts_mirror_input.textChanged.connect(self._on_tts_mirror_changed)
        mirror_layout.addWidget(self._tts_mirror_input)
        self._tts_mirror_status = QLabel("")
        mirror_layout.addWidget(self._tts_mirror_status)
        layout.addLayout(mirror_layout)

        self._tts_hf_label = QLabel(t("model.hf_mirror_url"))
        layout.addWidget(self._tts_hf_label)

        hf_layout = QHBoxLayout()
        self._tts_hf_mirror_input = M3TextField(placeholder="https://hf-mirror.com")
        self._tts_hf_mirror_input.setText(self.pipeline.config.download.get("hf_mirror_url", ""))
        self._tts_hf_mirror_input.textChanged.connect(self._on_tts_hf_mirror_changed)
        hf_layout.addWidget(self._tts_hf_mirror_input)
        self._tts_hf_mirror_status = QLabel("")
        hf_layout.addWidget(self._tts_hf_mirror_status)
        layout.addLayout(hf_layout)

        py_layout = QHBoxLayout()
        self._tts_py_btn = M3Button(t("tts.dl_python"), variant=M3Button.Variant.FILLED)
        self._tts_py_btn.clicked.connect(self._on_dl_portable_python)
        py_layout.addWidget(self._tts_py_btn)
        self._tts_py_status = QLabel(t("tts.python_missing"))
        py_layout.addWidget(self._tts_py_status)
        layout.addLayout(py_layout)

        btn_layout = QHBoxLayout()
        self._tts_pip_btn = M3Button(t("tts.pip_install"), variant=M3Button.Variant.FILLED)
        self._tts_pip_btn.clicked.connect(self._on_tts_pip_install)
        btn_layout.addWidget(self._tts_pip_btn)

        self._tts_dl_btn = M3Button(t("tts.download_weights"), variant=M3Button.Variant.FILLED)
        self._tts_dl_btn.clicked.connect(self._on_tts_download_weights)
        btn_layout.addWidget(self._tts_dl_btn)
        layout.addLayout(btn_layout)

        self._tts_dl_ready_label = QLabel("")
        layout.addWidget(self._tts_dl_ready_label)

        self._tts_progress_bar = M3LinearProgress()
        self._tts_progress_bar.setVisible(False)
        layout.addWidget(self._tts_progress_bar)

        self._tts_status_label = QLabel("")
        self._tts_status_label.setWordWrap(True)
        layout.addWidget(self._tts_status_label)

        self._tts_install_status.connect(self._tts_status_label.setText)
        self._tts_install_done.connect(lambda: self._tts_pip_btn.setEnabled(True))
        self._tts_progress.connect(self._on_tts_progress)
        self._tts_refresh_ui.connect(self._update_tts_button_states)

        layout.addStretch()

        self._update_tts_button_states()

    def retranslate_ui(self):
        self._tts_enable_label.setText(t("tts.enable"))
        self._tts_voice_label.setText(t("tts.voice"))
        self._tts_port_label.setText(t("tts.port"))
        self._tts_model_path_label.setText(t("tts.model_path"))
        self._tts_tok_path_label.setText(t("tts.audio_tokenizer_path"))
        self._tts_mirror_label.setText(t("model.mirror_url"))
        self._tts_mirror_input.setPlaceholderText("https://ghproxy.com")
        self._tts_hf_label.setText(t("model.hf_mirror_url"))
        self._tts_hf_mirror_input.setPlaceholderText("https://hf-mirror.com")
        self._tts_py_btn.setText(t("tts.dl_python"))
        self._tts_pip_btn.setText(t("tts.pip_install"))
        self._tts_dl_btn.setText(t("tts.download_weights"))
        self._update_tts_button_states()

    def title(self) -> str:
        return t("tts.tab")

    def _on_tts_config_changed(self):
        self.pipeline.config.tts["enabled"] = self._tts_enabled_cb.isChecked()
        self.pipeline.config.tts["voice"] = self._tts_voice_combo.currentData()
        self.pipeline.config.tts["port"] = self._tts_port_spin.value()
        self.pipeline.config.tts["model_path"] = self._tts_model_path.text().strip()
        self.pipeline.config.tts["audio_tokenizer_path"] = self._tts_tok_path.text().strip()
        save_config(self.pipeline.config)

    def _on_tts_mirror_changed(self):
        self.pipeline.config.download["mirror_url"] = self._tts_mirror_input.text().strip()
        save_config(self.pipeline.config)

    def _on_tts_hf_mirror_changed(self):
        self.pipeline.config.download["hf_mirror_url"] = self._tts_hf_mirror_input.text().strip()
        save_config(self.pipeline.config)

    def _on_tts_pip_install(self):
        python_path = self._get_tts_python()
        if not python_path:
            self._tts_install_status.emit(t("tts.python_missing"))
            return
        self._tts_install_status.emit(t("tts.installing"))
        self._tts_pip_btn.setEnabled(False)
        self._tts_progress_bar.setVisible(True)
        self._tts_progress_bar._determinate = False
        threading.Thread(target=self._tts_pip_install_worker, args=(python_path,), daemon=True).start()

    def _tts_pip_install_worker(self, python_path: str):
        import io
        import shutil
        import tempfile
        import zipfile

        import requests
        import subprocess

        repo_url = "git+https://github.com/OpenMOSS/MOSS-TTS-Nano.git"
        archive_url = "https://github.com/OpenMOSS/MOSS-TTS-Nano/archive/refs/heads/main.zip"
        installed = False

        try:
            result = subprocess.run(
                [python_path, "-m", "pip", "install", repo_url],
                capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                installed = True
            else:
                self._tts_install_status.emit("git install failed, trying zip fallback...")
        except subprocess.TimeoutExpired:
            self._tts_install_status.emit("git install timed out, trying zip fallback...")
        except Exception:
            self._tts_install_status.emit("git install error, trying zip fallback...")

        if not installed:
            try:
                r = requests.get(archive_url, timeout=60)
                r.raise_for_status()
                z = zipfile.ZipFile(io.BytesIO(r.content))
                tmp = tempfile.mkdtemp()
                z.extractall(tmp)
                dirs = os.listdir(tmp)
                if dirs:
                    pkg_dir = os.path.join(tmp, dirs[0])
                    result = subprocess.run(
                        [python_path, "-m", "pip", "install", pkg_dir],
                        capture_output=True, text=True, timeout=300,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    if result.returncode == 0:
                        installed = True
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception as e:
                self._tts_install_status.emit(f"Zip install failed: {e}")

        self._tts_progress.emit(100 if installed else 0)
        if installed:
            self._tts_install_status.emit(t("tts.install_done"))
        else:
            self._tts_install_status.emit("Install failed. Try: pip install git+https://github.com/OpenMOSS/MOSS-TTS-Nano.git")
        self._tts_install_done.emit()
        self._tts_refresh_ui.emit()

    def _on_tts_download_weights(self):
        from voirol.utils.download import download_file

        model_path = os.path.abspath(self._tts_model_path.text().strip() or "models/moss-tts-nano")
        tok_path = os.path.abspath(self._tts_tok_path.text().strip() or "models/moss-audio-tokenizer-nano")

        self._tts_dl_btn.setEnabled(False)
        self._tts_progress_bar.setVisible(True)
        self._tts_progress_bar.set_value(0)
        self._tts_status_label.setText("Downloading weights...")

        file_progress = [0]
        file_total = 7

        def _progress(pct: int):
            nonlocal file_progress
            overall = (file_progress[0] * 100 + pct) // file_total
            self._tts_progress.emit(overall)

        def _download():
            from voirol.voice.model_download import _apply_mirror
            gh_mirror = self.pipeline.config.download.get("mirror_url", "")
            hf_mirror = self.pipeline.config.download.get("hf_mirror_url", "")
            os.makedirs(model_path, exist_ok=True)
            os.makedirs(tok_path, exist_ok=True)
            urls = [
                _apply_mirror(f"https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M/resolve/main/{f}", gh_mirror, hf_mirror)
                for f in ["pytorch_model.bin", "config.json", "tokenizer.model",
                          "tokenizer_config.json", "special_tokens_map.json"]
            ]
            tok_urls = [
                _apply_mirror(f"https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano/resolve/main/{f}", gh_mirror, hf_mirror)
                for f in ["model-00001-of-00001.safetensors", "config.json"]
            ]
            success = True
            all_urls = [(u, model_path) for u in urls] + [(u, tok_path) for u in tok_urls]
            for url, dest in all_urls:
                filename = os.path.basename(url)
                if os.path.exists(os.path.join(dest, filename)):
                    file_progress[0] += 1
                    continue
                try:
                    download_file(url, dest, filename, progress_callback=_progress)
                except Exception as e:
                    self._tts_install_status.emit(f"Download failed: {e}")
                    success = False
                    break
                file_progress[0] += 1
            self._tts_progress.emit(100 if success else 0)
            if success:
                self._tts_install_status.emit("Weights downloaded. Restart to use TTS.")
            self._tts_refresh_ui.emit()

        threading.Thread(target=_download, daemon=True).start()

    def _get_tts_python(self) -> str | None:
        p = os.path.join("runtime", "python", "python.exe")
        return os.path.abspath(p) if os.path.exists(p) else None

    def _check_moss_installed(self, python_path: str) -> bool:
        site_pkg = os.path.join(os.path.dirname(python_path), "Lib", "site-packages", "moss_tts_nano")
        if os.path.isdir(site_pkg):
            return True
        try:
            import subprocess

            r = subprocess.run(
                [python_path, "-c", "import moss_tts_nano; print('ok')"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _check_weights_downloaded(self) -> bool:
        model_path = self._tts_model_path.text().strip() or "models/moss-tts-nano"
        tok_path = self._tts_tok_path.text().strip() or "models/moss-audio-tokenizer-nano"
        model_files = ["pytorch_model.bin", "config.json"]
        for f in model_files:
            if not os.path.exists(os.path.join(model_path, f)):
                return False
        if not os.path.exists(os.path.join(tok_path, "model-00001-of-00001.safetensors")):
            return False
        return True

    def _update_tts_button_states(self):
        python_path = self._get_tts_python()
        py_ready = python_path is not None

        if py_ready:
            self._tts_py_btn.setEnabled(False)
            self._tts_py_btn.setText(t("tts.installed"))
            self._tts_py_status.setText(t("tts.python_ready"))
        else:
            self._tts_py_btn.setEnabled(True)
            self._tts_py_btn.setText(t("tts.dl_python"))
            self._tts_py_status.setText(t("tts.python_missing"))

        if not py_ready:
            self._tts_pip_btn.setEnabled(False)
            self._tts_dl_btn.setEnabled(False)
            return

        moss_ok = self._check_moss_installed(python_path)
        if moss_ok:
            self._tts_pip_btn.setEnabled(False)
            self._tts_pip_btn.setText(t("tts.installed"))
        else:
            self._tts_pip_btn.setEnabled(True)
            self._tts_pip_btn.setText(t("tts.pip_install"))

        if not moss_ok:
            self._tts_dl_btn.setEnabled(False)
            self._tts_dl_btn.setText(t("tts.download_weights"))
            return

        if self._check_weights_downloaded():
            self._tts_dl_btn.setEnabled(False)
            self._tts_dl_btn.setText(t("tts.installed"))
            self._tts_dl_ready_label.setText(t("tts.weights_ready"))
        else:
            self._tts_dl_btn.setEnabled(True)
            self._tts_dl_btn.setText(t("tts.download_weights"))
            self._tts_dl_ready_label.setText("")

    def _on_dl_portable_python(self):
        self._tts_py_btn.setEnabled(False)
        self._tts_progress_bar.setVisible(True)
        self._tts_progress_bar.set_value(0)
        self._tts_status_label.setText("Downloading Portable Python...")
        threading.Thread(target=self._dl_portable_python_worker, daemon=True).start()

    def _dl_portable_python_worker(self):
        from voirol.voice.model_download import download_model
        mirror = self.pipeline.config.download.get("mirror_url", "")
        hf_mirror = self.pipeline.config.download.get("hf_mirror_url", "")
        try:
            ok = download_model("portable_python", mirror, hf_mirror, progress_callback=lambda p: self._tts_progress.emit(p))
            if ok:
                self._tts_progress.emit(100)
                self._tts_install_status.emit(t("tts.python_ready"))
            else:
                self._tts_install_status.emit("Download failed")
        except Exception as e:
            self._tts_install_status.emit(f"Error: {e}")
        self._tts_refresh_ui.emit()

    def _on_tts_progress(self, pct: int):
        if pct == -1:
            self._tts_progress_bar.set_value(0)
            self._tts_status_label.setText(t("tts.extracting"))
        else:
            self._tts_progress_bar.set_value(pct)
