from dataclasses import dataclass
from PIL import Image, ImageOps
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
    logger.error("pytesseract is not installed. OCR analysis unavailable.")
    class TesseractNotFoundError(Exception): pass

_auto_configured = False

_BTN_KEYWORDS = {"按钮", "确定", "取消", "保存", "删除", "取消", "打开", "关闭", "应用",
                 "ok", "yes", "no", "save", "cancel", "open", "close", "apply",
                 "submit", "reset", "next", "back", "retry", "继续", "下一步", "返回",
                 "confirm", "browse", "选择文件", "浏览", "下载", "安装"}


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
    block_num: int = 0

    def to_center(self) -> tuple[int, int]:
        return (self.cx, self.cy)


class ScreenAnalyzer:
    def __init__(
        self,
        ocr_lang: str = "chi_sim+eng",
        exclude_regions: list[tuple[int, int, int, int]] | None = None,
        min_confidence: int = 0,
        psm_mode: int = 6,
    ):
        self._ocr_lang = ocr_lang
        self._exclude_regions = exclude_regions or []
        self._psm_mode = psm_mode
        if min_confidence > 0:
            self._min_confidence = min_confidence
        else:
            self._min_confidence = 50 if "chi" in ocr_lang else 40

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

    def _preprocess(self, image: Image.Image) -> Image.Image:
        if image.mode != "L":
            image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image, cutoff=5)
        w, h = image.size
        if w >= 3840 or h >= 2160:
            return image
        if w >= 1920 and h >= 1080:
            image = image.resize((w * 2, h * 2), Image.LANCZOS)
            logger.debug(f"Upscaled screenshot 2x for OCR ({w}x{h} -> {w*2}x{h*2})")
        return image

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
        orig_w, orig_h = image.size
        image = self._preprocess(image)
        tesseract_config = f"--psm {self._psm_mode}"
        try:
            data = pytesseract.image_to_data(
                image, lang=self._ocr_lang, output_type=pytesseract.Output.DICT,
                config=tesseract_config,
            )
        except TesseractNotFoundError:
            if not _auto_configured:
                self._auto_configure_tesseract()
                if _auto_configured:
                    try:
                        data = pytesseract.image_to_data(
                            image, lang=self._ocr_lang, output_type=pytesseract.Output.DICT,
                            config=tesseract_config,
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

        w_factor = image.width / orig_w if orig_w > 0 else 1
        raw = []
        for i in range(len(data["text"])):
            try:
                conf = int(data["conf"][i])
            except (ValueError, TypeError):
                continue
            if conf <= self._min_confidence:
                continue
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            ew = data["width"][i]
            eh = data["height"][i]
            if ew < 5 / w_factor or eh < 5 / w_factor:
                continue
            tokens = text.split()
            if len(tokens) >= 3:
                single_char = sum(1 for t in tokens if len(t) <= 1)
                if single_char / len(tokens) >= 0.8:
                    continue
            raw.append({
                "text": text,
                "left": int(data["left"][i] / w_factor),
                "top": int(data["top"][i] / w_factor),
                "width": max(1, int(ew / w_factor)),
                "height": max(1, int(eh / w_factor)),
                "conf": conf,
                "block": data.get("block_num", [0])[i] if len(data.get("block_num", [0])) > i else 0,
                "line": data.get("line_num", [0])[i] if len(data.get("line_num", [0])) > i else 0,
            })

        if not raw:
            return []

        raw.sort(key=lambda e: (e["block"], e["line"], e["top"], e["left"]))

        merged = []
        current_group = [raw[0]]
        for elem in raw[1:]:
            last = current_group[-1]
            last_right = last["left"] + last["width"]
            gap = elem["left"] - last_right
            row_gap = elem["top"] - (last["top"] + last["height"])
            same_row = row_gap < max(4, min(last["height"], elem["height"]) * 0.3)
            vertical_overlap = (
                elem["top"] < last["top"] + last["height"]
                and elem["top"] + elem["height"] > last["top"]
            )
            small_gap = gap < max(2, min(last["width"], elem["width"]) * 0.5)
            if (same_row or vertical_overlap) and small_gap:
                left = min(last["left"], elem["left"])
                top = min(last["top"], elem["top"])
                right = max(last["left"] + last["width"], elem["left"] + elem["width"])
                bottom = max(last["top"] + last["height"], elem["top"] + elem["height"])
                current_group[-1] = {
                    "text": last["text"] + " " + elem["text"],
                    "left": left,
                    "top": top,
                    "width": right - left,
                    "height": bottom - top,
                    "conf": max(last["conf"], elem["conf"]),
                    "block": last["block"],
                    "line": last["line"],
                }
            else:
                current_group.append(elem)
        merged.extend(current_group)

        result = []
        sw, sh = pyautogui.size()
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
                block_num=elem["block"],
            ))

        result.sort(key=self._interaction_score, reverse=True)
        for i, el in enumerate(result):
            el.element_id = i
        return result

    @staticmethod
    def _interaction_score(el: ScreenElement) -> float:
        btn_likely = 0
        if el.w < 250 and el.h < 50:
            btn_likely += 1
        if any(kw in el.text.lower() for kw in _BTN_KEYWORDS):
            btn_likely += 2
        is_short = len(el.text) <= 6
        if is_short and btn_likely:
            btn_likely += 1
        score = btn_likely * 100 + el.confidence
        return score

    def _deduplicate(self, elements: list[ScreenElement]) -> list[ScreenElement]:
        kept = []
        for el in elements:
            dup = False
            for existing in kept:
                iou = self._iou(el, existing)
                if iou > 0.8 and el.text == existing.text:
                    dup = True
                    break
            if not dup:
                kept.append(el)
        return kept

    @staticmethod
    def _iou(a: ScreenElement, b: ScreenElement) -> float:
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x + a.w, b.x + b.w)
        y2 = min(a.y + a.h, b.y + b.h)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = a.w * a.h
        area_b = b.w * b.h
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0

    def format_observation(self, elements: list[ScreenElement], screen_size: tuple[int, int] | None = None) -> str:
        if screen_size is None:
            img = self.capture()
            screen_size = img.size
        lines = [f"SCREEN: {screen_size[0]}x{screen_size[1]}"]
        for el in elements:
            etype = self._classify_element(el)
            lines.append(
                f'[id={el.element_id}] {etype} "{el.text}" '
                f"({el.x}, {el.y}, {el.w}, {el.h}) "
                f"center=({el.cx}, {el.cy}) conf={el.confidence:.0f}"
            )
        return "\n".join(lines)

    def _classify_element(self, el: ScreenElement) -> str:
        if any(kw in el.text.lower() for kw in _BTN_KEYWORDS):
            return "btn"
        if el.w < 250 and el.h < 50:
            return "btn"
        if el.w > 400:
            return "panel"
        if el.h > 80:
            return "panel"
        return "lbl"

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

    def set_exclude_regions(self, regions: list[tuple[int, int, int, int]]) -> None:
        self._exclude_regions = regions

    def track_elements(self, prev: list[ScreenElement], curr: list[ScreenElement]) -> list[ScreenElement]:
        if not prev:
            return curr
        tracked = []
        for c in curr:
            best_match = None
            best_score = 0.0
            for p in prev:
                text_sim = self._text_similarity(c.text, p.text)
                iou = self._iou(c, p)
                score = text_sim * 0.6 + iou * 0.4
                if score > best_score and score > 0.4:
                    best_score = score
                    best_match = p
            if best_match is not None:
                c.element_id = best_match.element_id
            tracked.append(c)
        return tracked

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        a = a.lower()
        b = b.lower()
        if a == b:
            return 1.0
        longer = max(len(a), len(b))
        if longer == 0:
            return 1.0
        edits = sum(1 for ca, cb in zip(a, b) if ca != cb) + abs(len(a) - len(b))
        return max(0.0, 1.0 - edits / longer)


__all__ = ["ScreenElement", "ScreenAnalyzer"]
