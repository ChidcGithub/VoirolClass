"""教师声纹注册对话框。"""
import numpy as np
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from voirol.core.pipeline import VoicePipeline
from voirol.utils.i18n import t


def show_enroll_dialog(pipeline: VoicePipeline):
    """显示教师声纹注册对话框。"""
    dialog = QDialog()
    dialog.setWindowTitle(t("teacher.enroll_title"))
    dialog.setMinimumWidth(350)

    layout = QVBoxLayout(dialog)

    form = QFormLayout()
    name_input = QLineEdit()
    name_input.setPlaceholderText(t("teacher.enroll_name_placeholder"))
    form.addRow(t("teacher.enroll_name_label"), name_input)
    layout.addLayout(form)

    info_label = QLabel(t("teacher.enroll_instruction"))
    info_label.setWordWrap(True)
    layout.addWidget(info_label)

    sentences = [
        t("teacher.enroll_sentence_1"),
        t("teacher.enroll_sentence_2"),
        t("teacher.enroll_sentence_3"),
        t("teacher.enroll_sentence_4"),
        t("teacher.enroll_sentence_5"),
    ]

    sentence_list = QListWidget()
    for s in sentences:
        sentence_list.addItem(s)
    layout.addWidget(sentence_list)

    start_btn = QPushButton(t("teacher.enroll_start"))
    layout.addWidget(start_btn)
    result_label = QLabel("")
    layout.addWidget(result_label)

    def on_start():
        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(dialog, t("prompt.title"), t("teacher.enroll_enter_name"))
            return

        pipeline.pause()

        try:
            import sounddevice as sd

            sample_rate = pipeline.config.general["sample_rate"]
            duration = 3
            collected = []

            for i, sentence in enumerate(sentences):
                result_label.setText(
                    t("teacher.enroll_recording", idx=i + 1, total=len(sentences), sentence=sentence)
                )
                result_label.repaint()
                QApplication.processEvents()

                QMessageBox.information(
                    dialog, t("teacher.enroll_dialog_title"),
                    t("teacher.enroll_dialog_text", duration=duration, sentence=sentence),
                )

                audio = sd.rec(
                    int(sample_rate * duration),
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.float32,
                )
                sd.wait()

                audio = audio.flatten()
                if np.max(np.abs(audio)) > 0.01:
                    pipeline.enrollment.save_enrollment_audio(
                        name, i, audio, sample_rate
                    )
                    from voirol.audio.processor import preprocess
                    collected.append(preprocess(audio, sample_rate))
                    result_label.setText(t("teacher.enroll_recorded", idx=i + 1))
                else:
                    result_label.setText(t("teacher.enroll_skipped", idx=i + 1))
                QApplication.processEvents()

            if len(collected) < 2:
                QMessageBox.warning(
                    dialog, t("teacher.enroll_failed"), t("teacher.enroll_too_few")
                )
                return

            from voirol.voice.verifier import create_profile_from_audio
            profile = create_profile_from_audio(
                collected, name, sample_rate,
                model_path=pipeline.config.voice.get("model_path", "campplus-zh-en"),
            )
            pipeline.enrollment.save_profile(profile)

            result_label.setText(t("teacher.enroll_complete", name=name))
            QMessageBox.information(
                dialog, t("teacher.enroll_done"), t("teacher.enroll_success", name=name)
            )
        finally:
            pipeline.resume()

    start_btn.clicked.connect(on_start)
    dialog.exec()
