import os
import time

import requests

from voirol.utils.logger import get_logger

logger = get_logger("utils.download")

DOWNLOAD_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
}


def download_file(
    url: str,
    dest_path: str,
    filename: str,
    desc: str = "",
    mirrors: list[str] | None = None,
    timeout: int = DOWNLOAD_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> str:
    os.makedirs(dest_path, exist_ok=True)
    full_path = os.path.join(dest_path, filename)

    if os.path.exists(full_path):
        logger.info(f"Already exists: {full_path}")
        return full_path

    urls = [url] + (mirrors or [])

    for url_idx, curr_url in enumerate(urls):
        for attempt in range(retries):
            try:
                label = desc or filename
                if url_idx > 0:
                    label += f" (mirror {url_idx})"
                logger.info(f"Downloading {label}...")

                response = requests.get(
                    curr_url,
                    timeout=timeout,
                    stream=True,
                    headers=HEADERS,
                )
                response.raise_for_status()

                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                last_log = 0

                with open(full_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = downloaded / total * 100
                                if pct - last_log >= 5 or downloaded == total:
                                    logger.info(
                                        f"  {label}: {downloaded/1024/1024:.1f}/"
                                        f"{total/1024/1024:.1f} MB "
                                        f"({pct:.0f}%)"
                                    )
                                    last_log = pct

                size_mb = os.path.getsize(full_path) / 1024 / 1024
                logger.info(f"Downloaded {label}: {size_mb:.1f} MB")
                return full_path

            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        f"Download failed (attempt {attempt+1}/{retries}): "
                        f"{e}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    if url_idx < len(urls) - 1:
                        logger.warning(
                            f"All {retries} attempts failed for this URL, "
                            f"trying next mirror..."
                        )
                    else:
                        raise

    raise RuntimeError(
        f"Failed to download {filename} after "
        f"{len(urls)} URL(s) × {retries} retries"
    )
