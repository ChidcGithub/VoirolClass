from dataclasses import dataclass
from PIL import Image
import pyautogui

from voirol.utils.logger import get_logger

logger = get_logger("agent.screen")

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
    _pytesseract_available = True

    try:
        _original_get_errors = pytesseract.pytesseract.get_errors

        def _patched_get_errors(error_string):
            try:
                return _original_get_errors(error_string)
            except UnicodeDecodeError:
                import locale
                enc = locale.getpreferredencoding()
                return " ".join(
                    line for line in error_string.decode(enc, errors="replace").splitlines()
                ).strip()

        pytesseract.pytesseract.get_errors = _patched_get_errors
    except AttributeError:
        pass
except ImportError:
    _pytesseract_available = False
    TesseractNotFoundError = Exception
    logger.error("pytesseract is not installed. OCR analysis unavailable.")

_auto_configured = False


@dataclass
class ScreenElement:
    element_id: int
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float
    cx: int
    cy: int

    def to_center(self) -> tuple[int, int]:
        return (self.cx, self.cy)


class ScreenAnalyzer:
    def __init__(self, ocr_lang: str = "chi_sim+eng", exclude_regions: list[tuple[int, int, int, int]] | None = None):
        self._ocr_lang = ocr_lang
        self._exclude_regions = exclude_regions or []

    def _ensure_configured(self):
        if _auto_configured:
            return
        try:
            pytesseract.get_tesseract_version()
        except TesseractNotFoundError:
            pass
        except Exception:
            self._auto_configure_tesseract()

    def _auto_configure_tesseract(self):
        global _auto_configured
        try:
            from voirol.utils.tesseract_download import get_tesseract_exe, setup_pytesseract_path
            exe_path = get_tesseract_exe()
            if exe_path:
                pytesseract.pytesseract.tesseract_cmd = exe_path
                setup_pytesseract_path()
                _auto_configured = True
                logger.info(f"Auto-configured Tesseract path: {exe_path}")
            else:
                logger.warning("Tesseract not found locally")
        except Exception as e:
            logger.warning(f"Failed to auto-configure Tesseract: {e}")

    def capture(self, region: tuple[int, int, int, int] | None = None) -> Image.Image:
        try:
            return pyautogui.screenshot(region=region)
        except Exception:
            logger.warning("Screen capture failed", exc_info=True)
            return Image.new("RGB", (256, 256))

    def analyze(self, image: Image.Image) -> list[ScreenElement]:
        if not _pytesseract_available:
            return []
        self._ensure_configured()
        try:
            data = pytesseract.image_to_data(
                image, lang=self._ocr_lang, output_type=pytesseract.Output.DICT
            )
        except TesseractNotFoundError:
            if not _auto_configured:
                self._auto_configure_tesseract()
                if _auto_configured:
                    try:
                        data = pytesseract.image_to_data(
                            image, lang=self._ocr_lang, output_type=pytesseract.Output.DICT
                        )
                    except Exception:
                        return []
                else:
                    return []
            else:
                return []
        except Exception:
            logger.warning("OCR analysis failed", exc_info=True)
            return []

        raw = []
        for i in range(len(data["text"])):
            try:
                conf = int(data["conf"][i])
            except (ValueError, TypeError):
                continue
            if conf <= 40:
                continue
            text = str(data["text"][i]).strip()
            if not text:
                continue
            tokens = text.split()
            if len(tokens) >= 3:
                single_char = sum(1 for t in tokens if len(t) <= 1)
                if single_char / len(tokens) >= 0.8:
                    continue
            raw.append({
                "text": text,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "conf": conf,
            })

        if not raw:
            return []

        raw.sort(key=lambda e: (e["top"], e["left"]))

        merged = [raw[0]]
        for elem in raw[1:]:
            last = merged[-1]
            last_bottom = last["top"] + last["height"]
            elem_bottom = elem["top"] + elem["height"]
            overlap_top = max(last["top"], elem["top"])
            overlap_bottom = min(last_bottom, elem_bottom)
            overlap_h = max(0, overlap_bottom - overlap_top)
            smaller_h = min(last["height"], elem["height"])
            if smaller_h > 0 and overlap_h / smaller_h > 0.5:
                last_right = last["left"] + last["width"]
                gap = elem["left"] - last_right
                if gap < 15:
                    left = min(last["left"], elem["left"])
                    top = min(last["top"], elem["top"])
                    right = max(last["left"] + last["width"], elem["left"] + elem["width"])
                    bottom = max(last["top"] + last["height"], elem["top"] + elem["height"])
                    merged[-1] = {
                        "text": last["text"] + " " + elem["text"],
                        "left": left,
                        "top": top,
                        "width": right - left,
                        "height": bottom - top,
                        "conf": max(last["conf"], elem["conf"]),
                    }
                    continue
            merged.append(elem)

        result = []
        for i, elem in enumerate(merged):
            cx = elem["left"] + elem["width"] // 2
            cy = elem["top"] + elem["height"] // 2
            w = elem["width"]
            h = elem["height"]

            if self._exclude_regions and any(
                rx <= cx <= rx + rw and ry <= cy <= ry + rh
                for rx, ry, rw, rh in self._exclude_regions
            ):
                continue

            result.append(ScreenElement(
                element_id=i,
                text=elem["text"],
                x=elem["left"],
                y=elem["top"],
                w=w,
                h=h,
                confidence=float(elem["conf"]),
                cx=cx,
                cy=cy,
            ))

        return result

    def format_observation(self, elements: list[ScreenElement], filter_text: str = "") -> str:
        lines = []
        for el in elements:
            if el.w < 200 and el.h < 40:
                etype = "btn"
            elif el.w > 300:
                etype = "panel"
            else:
                etype = "lbl"
            lines.append(
                f'[id={el.element_id}] {etype} "{el.text}" '
                f"({el.x}, {el.y}, {el.w}, {el.h}) center=({el.cx}, {el.cy})"
            )
        return "\n".join(lines)

    def get_element_by_id(self, elements: list[ScreenElement], element_id: int) -> ScreenElement | None:
        for el in elements:
            if el.element_id == element_id:
                return el
        return None

    def get_element_by_text(self, elements: list[ScreenElement], text: str) -> ScreenElement | None:
        text_lower = text.lower()
        for el in elements:
            if text_lower in el.text.lower():
                return el
        return None


__all__ = ["ScreenElement", "ScreenAnalyzer"]
