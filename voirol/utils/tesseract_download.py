import os
import sys
import shutil
import subprocess
import time

from voirol.utils.download import download_file
from voirol.utils.logger import get_logger

logger = get_logger("utils.tesseract_download")

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TESSEL_DIR = os.path.join(APP_DIR, "tools", "tesseract")
TESSDATA_DIR = os.path.join(TESSEL_DIR, "tessdata")
EXPECTED_EXE = os.path.join(TESSEL_DIR, "tesseract.exe")

_LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
JUNCTION_DIR = os.path.join(_LOCAL_APP_DATA, "VoirolClass", "tessdata")

TESSERACT_VERSION = "5.5.0"
TESSERACT_EXE_URLS = [
    "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe",
]
TESSDATA_URLS = {
    "eng": [
        "https://gitee.com/rwind/tessdata/raw/main/eng.traineddata",
        "https://gitee.com/mirrors_tesseract-ocr/tessdata_fast/raw/main/eng.traineddata",
        "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata",
    ],
    "chi_sim": [
        "https://gitee.com/rwind/tessdata/raw/main/chi_sim.traineddata",
        "https://gitee.com/mirrors_tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
        "https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata",
    ],
}

# Index of the GitHub URL within each list
_GITHUB_URL_INDEX = -1  # last element

SEVENZ_DIR = os.path.join(APP_DIR, "tools", "7z")
SEVENZ_EXE = os.path.join(SEVENZ_DIR, "7z.exe")
SEVENZR_URL = "https://www.7-zip.org/a/7zr.exe"
SEVENZ_INSTALLER_URL = "https://www.7-zip.org/a/7z2602-x64.exe"
SEVENZ_INSTALLER_NAME = "7z2602-x64.exe"


def get_tesseract_exe() -> str | None:
    if os.path.exists(EXPECTED_EXE):
        return EXPECTED_EXE
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            if sys.platform == "win32":
                where = subprocess.run(["where", "tesseract"], capture_output=True, text=True, timeout=5)
                if where.returncode == 0:
                    path = where.stdout.strip().split("\n")[0].strip()
                    if path:
                        return path
            return "tesseract"
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def check_tesseract_installed() -> bool:
    exe = get_tesseract_exe()
    if exe is None:
        return False
    try:
        result = subprocess.run([exe, "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_version() -> str:
    exe = get_tesseract_exe()
    if exe is None:
        return ""
    try:
        result = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            first_line = result.stdout.strip().split("\n")[0]
            for part in first_line.split():
                if part[0:1].isdigit():
                    return part
            return first_line
    except Exception:
        pass
    return ""


def get_language_packs() -> list[str]:
    if not os.path.isdir(TESSDATA_DIR):
        return []
    packs = []
    for f in os.listdir(TESSDATA_DIR):
        if f.endswith(".traineddata"):
            packs.append(f[:-len(".traineddata")])
    packs.sort()
    return packs


def is_language_pack_installed(lang: str) -> bool:
    return os.path.exists(os.path.join(TESSDATA_DIR, f"{lang}.traineddata"))


def _find_7z() -> str | None:
    if os.path.exists(SEVENZ_EXE):
        return SEVENZ_EXE
    for candidate in os.environ.get("PATH", "").split(os.pathsep):
        candidate = candidate.strip().strip('"')
        path = os.path.join(candidate, "7z.exe")
        if os.path.exists(path):
            return path
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    common = [
        os.path.join(program_files, "7-Zip", "7z.exe"),
        os.path.join(program_files, "7-Zip (portable)", "7z.exe"),
        os.path.join(os.environ.get("ProgramW6432", ""), "7-Zip", "7z.exe"),
        os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "Program Files", "7-Zip", "7z.exe"),
    ]
    for path in common:
        if os.path.exists(path):
            return path
    return None

def _ensure_7z(progress_callback=None) -> str | None:
    existing = _find_7z()
    if existing:
        return existing
    os.makedirs(SEVENZ_DIR, exist_ok=True)
    sevenzr_path = os.path.join(SEVENZ_DIR, "7zr.exe")
    if not os.path.exists(sevenzr_path):
        if progress_callback:
            progress_callback(0)
        logger.info("Downloading 7zr.exe...")
        download_file(
            url=SEVENZR_URL,
            dest_path=SEVENZ_DIR,
            filename="7zr.exe",
            desc="7zr standalone",
            timeout=60,
            retries=3,
            progress_callback=lambda p: progress_callback(p // 2) if progress_callback else None,
        )
        if progress_callback:
            progress_callback(50)

    if os.path.exists(SEVENZ_EXE):
        return SEVENZ_EXE

    installer_path = os.path.join(SEVENZ_DIR, SEVENZ_INSTALLER_NAME)
    if not os.path.exists(installer_path):
        logger.info("Downloading 7-Zip installer...")
        download_file(
            url=SEVENZ_INSTALLER_URL,
            dest_path=SEVENZ_DIR,
            filename=SEVENZ_INSTALLER_NAME,
            desc="7-Zip installer",
            timeout=120,
            retries=3,
            progress_callback=lambda p: progress_callback(50 + p // 4) if progress_callback else None,
        )
    if progress_callback:
        progress_callback(75)

    opener_dir = os.path.join(SEVENZ_DIR, "opener")
    if not os.path.exists(opener_dir):
        os.makedirs(opener_dir, exist_ok=True)
    logger.info("Extracting 7-Zip installer...")
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    result = subprocess.run(
        [sevenzr_path, "x", installer_path, f"-o{opener_dir}", "-y"],
        capture_output=True, timeout=60, startupinfo=startupinfo,
    )
    if result.returncode not in (0, 1):
        err = (result.stderr or "").strip()[:500]
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        logger.error(f"7zr extraction failed (code {result.returncode}): {err}")
        return None

    extracted = os.listdir(opener_dir)
    logger.info(f"Extracted files: {extracted}")

    for root, dirs, files in os.walk(opener_dir):
        if "7z.exe" in files:
            shutil.copy2(os.path.join(root, "7z.exe"), SEVENZ_EXE)
        if "7z.dll" in files:
            dll_target = os.path.join(SEVENZ_DIR, "7z.dll")
            if not os.path.exists(dll_target):
                shutil.copy2(os.path.join(root, "7z.dll"), dll_target)

    try:
        os.remove(installer_path)
    except Exception:
        pass
    try:
        os.remove(sevenzr_path)
    except Exception:
        pass
    try:
        shutil.rmtree(opener_dir)
    except Exception:
        pass

    if os.path.exists(SEVENZ_EXE):
        if progress_callback:
            progress_callback(100)
        return SEVENZ_EXE
    return None


def _extract_nsis_with_7z(exe_path: str, sevenz_path: str, progress_callback=None) -> bool:
    logger.info(f"Extracting NSIS with 7z: {sevenz_path} x {exe_path} -o{TESSEL_DIR}")
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        proc = subprocess.run(
            [sevenz_path, "x", exe_path, f"-o{TESSEL_DIR}", "-y", "-aoa"],
            capture_output=True, text=True, timeout=180, startupinfo=startupinfo,
        )
        if proc.returncode not in (0, 1):
            logger.error(f"7z extraction failed (code {proc.returncode}): {proc.stderr[:200]}")
            return False
        logger.info("7z extraction succeeded")
        return True
    except subprocess.TimeoutExpired:
        logger.error("7z extraction timed out")
        return False
    except Exception as e:
        logger.error(f"7z extraction error: {e}")
        return False


def download_tesseract_exe(progress_callback=None, mirror_url="") -> str:
    os.makedirs(TESSEL_DIR, exist_ok=True)
    filename = f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.exe"
    filepath = os.path.join(TESSEL_DIR, filename)

    if os.path.exists(filepath):
        return filepath

    url = TESSERACT_EXE_URLS[0]
    mirrors = []
    if mirror_url and any(domain in url for domain in ["github.com", "raw.githubusercontent.com"]):
        mirror = mirror_url.rstrip("/") + "/" + url.lstrip("/")
        mirrors.append(url)
        url = mirror
    download_file(
        url=url,
        dest_path=TESSEL_DIR,
        filename=filename,
        desc=f"Tesseract {TESSERACT_VERSION} installer",
        timeout=300,
        retries=3,
        mirrors=mirrors,
        progress_callback=progress_callback,
    )
    return filepath


def extract_and_setup(exe_path: str, progress_callback=None) -> bool:
    if progress_callback:
        progress_callback(-1)

    if not os.path.exists(exe_path):
        logger.error(f"Tesseract installer not found: {exe_path}")
        return False

    old_tessdata = os.path.join(TESSEL_DIR, "tessdata")
    temp_tessdata = None
    if os.path.isdir(old_tessdata):
        temp_tessdata = os.path.join(TESSEL_DIR, ".tessdata_bak")
        if os.path.exists(temp_tessdata):
            shutil.rmtree(temp_tessdata)
        shutil.copytree(old_tessdata, temp_tessdata)

    for item in os.listdir(TESSEL_DIR):
        item_path = os.path.join(TESSEL_DIR, item)
        if item == os.path.basename(exe_path):
            continue
        if item == ".tessdata_bak":
            continue
        if item == "tessdata":
            continue
        if os.path.isfile(item_path):
            os.remove(item_path)
        else:
            shutil.rmtree(item_path)

    if progress_callback:
        progress_callback(10)

    extract_ok = False
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        logger.info(f"Running NSIS installer: {exe_path} /S /D={TESSEL_DIR}")
        proc = subprocess.run(
            [exe_path, "/S", f"/D={TESSEL_DIR}"],
            capture_output=True,
            text=True,
            timeout=180,
            startupinfo=startupinfo,
        )
        if proc.returncode == 0:
            extract_ok = True
        else:
            logger.warning(f"Installer failed (code {proc.returncode}): {proc.stderr}")
    except subprocess.TimeoutExpired:
        logger.warning("Installer timed out after 180s")
    except OSError as e:
        logger.warning(f"Cannot run installer (may require admin): {e}")
    except Exception as e:
        logger.warning(f"Installer error: {e}")

    if not extract_ok:
        logger.info("Trying 7z extraction as fallback...")
        sevenz = _find_7z()
        if not sevenz:
            logger.info("7z not found on system, downloading...")
            sevenz = _ensure_7z(progress_callback=lambda p: (
                progress_callback(10 + int(p * 0.3)) if progress_callback else None
            ))
        if sevenz:
            if progress_callback:
                progress_callback(40)
            extract_ok = _extract_nsis_with_7z(exe_path, sevenz, progress_callback)
        else:
            logger.error("No 7z available and installer requires admin")
            return False

    if not extract_ok:
        logger.error("All extraction methods failed")
        return False

    if progress_callback:
        progress_callback(60)

    try:
        os.remove(exe_path)
    except Exception:
        pass

    if progress_callback:
        progress_callback(70)

    if temp_tessdata and os.path.isdir(temp_tessdata):
        if os.path.isdir(old_tessdata):
            shutil.rmtree(old_tessdata)
        shutil.copytree(temp_tessdata, old_tessdata, dirs_exist_ok=True)
        shutil.rmtree(temp_tessdata)

    if progress_callback:
        progress_callback(80)

    if not os.path.exists(EXPECTED_EXE):
        for root, dirs, files in os.walk(TESSEL_DIR):
            for f in files:
                if f.lower() == "tesseract.exe":
                    parent = os.path.dirname(os.path.join(root, f))
                    if parent != TESSEL_DIR:
                        for item in os.listdir(parent):
                            item_path = os.path.join(parent, item)
                            target = os.path.join(TESSEL_DIR, item)
                            if not os.path.exists(target):
                                shutil.move(item_path, target)
                            elif os.path.isdir(item_path):
                                shutil.copytree(item_path, target, dirs_exist_ok=True)
                                shutil.rmtree(item_path)
                        break

    if not os.path.exists(EXPECTED_EXE):
        logger.error("tesseract.exe not found after installation")
        return False

    if progress_callback:
        progress_callback(90)

    setup_pytesseract_path()

    if progress_callback:
        progress_callback(100)
    logger.info(f"Tesseract installed to: {TESSEL_DIR}")
    return True


def download_tessdata(lang: str, progress_callback=None, mirror_url="") -> bool:
    if is_language_pack_installed(lang):
        return True

    base_urls = TESSDATA_URLS.get(lang, [])
    if not base_urls:
        logger.warning(f"Unknown language pack: {lang}")
        return False

    os.makedirs(TESSDATA_DIR, exist_ok=True)

    urls = base_urls.copy()
    github_url = urls.pop(_GITHUB_URL_INDEX)

    if mirror_url:
        mirror_target = mirror_url.rstrip("/") + "/" + github_url.lstrip("/")
        urls.insert(0, mirror_target)

    urls.append(github_url)

    for url in urls:
        try:
            download_file(
                url=url,
                dest_path=TESSDATA_DIR,
                filename=f"{lang}.traineddata",
                desc=f"Tessdata {lang}",
                timeout=60,
                retries=3,
                progress_callback=progress_callback,
            )
            setup_pytesseract_path()
            return True
        except Exception as e:
            logger.warning(f"Tessdata download failed ({url}): {e}")

    logger.error(f"Failed to download tessdata ({lang}) from all sources")
    return False


def _ensure_tessdata_junction() -> str | None:
    if not os.path.isdir(TESSDATA_DIR):
        return None

    junction = JUNCTION_DIR
    parent = os.path.dirname(junction)
    os.makedirs(parent, exist_ok=True)

    if os.path.isdir(junction):
        return junction

    if os.path.exists(junction):
        subprocess.run(["cmd", "/c", "rmdir", f'"{junction}"'], capture_output=True, timeout=10)
        if os.path.exists(junction):
            return None

    try:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", f'"{junction}"', f'"{TESSDATA_DIR}"'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info(f"Tessdata junction: {junction} -> {TESSDATA_DIR}")
            return junction
        logger.warning(f"mklink failed: {result.stderr}")
    except Exception as e:
        logger.warning(f"mklink error: {e}")
    return None


def setup_pytesseract_path() -> bool:
    exe = get_tesseract_exe()
    if exe is None:
        return False
    if os.path.isdir(TESSDATA_DIR):
        junction = _ensure_tessdata_junction()
        data_dir = junction or TESSDATA_DIR
        os.environ["TESSDATA_PREFIX"] = data_dir
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = exe
        logger.info(f"pytesseract configured: {exe}")
        return True
    except ImportError:
        logger.warning("pytesseract not installed")
        return False


__all__ = [
    "APP_DIR", "TESSEL_DIR", "TESSDATA_DIR", "JUNCTION_DIR",
    "get_tesseract_exe", "check_tesseract_installed", "get_version",
    "get_language_packs", "is_language_pack_installed",
    "download_tesseract_exe", "extract_and_setup",
    "download_tessdata", "setup_pytesseract_path",
]
