import base64
import hashlib
import hmac
import json
import time
from datetime import datetime

import numpy as np
import requests

from voirol.asr.engine import ASREngine
from voirol.utils.logger import get_logger

logger = get_logger("asr.tencent")

HOST = "asr.tencentcloudapi.com"
ENDPOINT = "https://" + HOST
SERVICE = "asr"
VERSION = "2019-06-14"
ACTION = "SentenceRecognition"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


class TencentEngine(ASREngine):
    def __init__(self, secret_id: str, secret_key: str, language: str = "zh"):
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._eng_service_type = "16k_zh" if language.startswith("zh") else "16k_en"
        self._ready = False

    def _build_authorization(self, payload: dict) -> tuple[dict, dict]:
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        body = json.dumps(payload)

        canonical_headers = (
            f"content-type:{ct}\n"
            f"host:{HOST}\n"
            f"x-tc-action:{ACTION.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()

        canonical_request = (
            f"{http_request_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_request_payload}"
        )

        credential_scope = f"{date}/{SERVICE}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()

        algorithm = "TC3-HMAC-SHA256"
        string_to_sign = (
            f"{algorithm}\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical_request}"
        )

        secret_date = _sign(("TC3" + self._secret_key).encode("utf-8"), date)
        secret_service = _sign(secret_date, SERVICE)
        secret_signing = _sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"{algorithm} "
            f"Credential={self._secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers = {
            "Host": HOST,
            "Content-Type": ct,
            "X-TC-Action": ACTION,
            "X-TC-Version": VERSION,
            "X-TC-Timestamp": str(timestamp),
            "Authorization": authorization,
        }
        return headers, payload

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if audio.dtype != np.int16:
            audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        else:
            audio_int16 = audio

        pcm_bytes = audio_int16.tobytes()
        data_b64 = base64.b64encode(pcm_bytes).decode("utf-8")

        payload = {
            "SourceType": 1,
            "VoiceFormat": "pcm",
            "EngSerViceType": self._eng_service_type,
            "Data": data_b64,
            "DataLen": len(pcm_bytes),
            "SubServiceType": 2,
        }

        headers, body = self._build_authorization(payload)

        try:
            resp = requests.post(ENDPOINT, json=body, headers=headers, timeout=30)
            data = resp.json()
            result = data.get("Result", "")
            if result:
                return result.strip()

            error_msg = data.get("Error", {}).get("Message", "")
            if error_msg:
                logger.warning(f"Tencent ASR error: {error_msg}")
            return ""
        except Exception as e:
            logger.warning(f"Tencent ASR request failed: {e}")
            return ""

    def load(self):
        self._ready = True

    def unload(self):
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready
