import base64

import numpy as np
import requests

from voirol.asr.engine import ASREngine
from voirol.utils.logger import get_logger

logger = get_logger("asr.baidu")

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
ASR_URL = "https://vop.baidu.com/server_api"


class BaiduEngine(ASREngine):
    def __init__(self, api_key: str, secret_key: str, language: str = "zh"):
        self.api_key = api_key
        self.secret_key = secret_key
        self._token = None
        self._dev_pid = 1537 if language.startswith("zh") else 1737

    def _get_token(self) -> str:
        resp = requests.post(TOKEN_URL, params={
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }, timeout=10)
        data = resp.json()
        if "access_token" in data:
            self._token = data["access_token"]
            logger.info("Baidu ASR token acquired")
        else:
            logger.error(f"Baidu token error: {data}")
        return self._token

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if audio.dtype != np.int16:
            audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        else:
            audio_int16 = audio

        pcm_bytes = audio_int16.tobytes()
        speech_b64 = base64.b64encode(pcm_bytes).decode("utf-8")
        length = len(pcm_bytes)

        for attempt in range(2):
            if not self._token:
                self._get_token()
            if not self._token:
                return ""

            resp = requests.post(ASR_URL, json={
                "format": "pcm",
                "rate": sample_rate,
                "channel": 1,
                "cuid": "voirolclass",
                "token": self._token,
                "dev_pid": self._dev_pid,
                "speech": speech_b64,
                "len": length,
            }, timeout=30)

            data = resp.json()
            err_no = data.get("err_no", -1)
            if err_no == 0:
                result = data.get("result", [""])
                text = result[0].strip() if result else ""
                if text:
                    return text
                return ""
            elif err_no == 110:
                self._token = None
                logger.warning("Baidu token expired, refreshing...")
                continue
            else:
                logger.warning(f"Baidu ASR err_no={err_no}: {data.get('err_msg', '')}")
                return ""

        return ""

    def load(self):
        self._get_token()

    def unload(self):
        self._token = None

    def is_ready(self) -> bool:
        return self._token is not None
