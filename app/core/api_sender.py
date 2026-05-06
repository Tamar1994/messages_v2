"""Webex Connect API sender — SMS, MMS, RCS, and RCS capability check."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# Locate .env and log file relative to the executable (works both in dev and as .exe)
if getattr(sys, "frozen", False):          # running as PyInstaller bundle
    _base_dir = Path(sys.executable).parent
else:
    _base_dir = Path(__file__).parent.parent.parent  # repo root

load_dotenv(_base_dir / ".env")

# ------------------------------------------------------------------
# File logger — writes to webex_sender.log next to the .exe / repo root
# ------------------------------------------------------------------
_log_path = _base_dir / "webex_sender.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path, encoding="utf-8"),
    ],
)
_log = logging.getLogger("api_sender")

_TIMEOUT = 30  # seconds


class APISender:
    """Handles HTTP requests to the Webex Connect messaging API."""

    def __init__(self) -> None:
        self._api_key: str = os.getenv("WEBEX_API_KEY", "")
        self._base_url: str = os.getenv(
            "WEBEX_BASE_URL", "https://api.imiconnect.io"
        ).rstrip("/")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single message payload.

        Returns a dict with keys:
            success (bool), messageId (str|None), status (str), error (str|None)
        """
        if not self._api_key or self._api_key == "your_service_key_here":
            _log.error("API Key não configurada.")
            return {
                "success": False,
                "error": "API Key não configurada. Edite o arquivo .env.",
            }

        url = f"{self._base_url}/v2/messages"
        headers = {
            "Content-Type": "application/json",
            "key": self._api_key,
        }

        _log.debug("=== SEND REQUEST ===")
        _log.debug("URL: %s", url)
        _log.debug("Headers: Content-Type=application/json, key=***%s", self._api_key[-4:] if len(self._api_key) >= 4 else "****")
        _log.debug("Payload:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))

        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=_TIMEOUT,
            )

            _log.debug("=== RESPONSE ===")
            _log.debug("Status: %s", resp.status_code)
            _log.debug("Headers: %s", dict(resp.headers))
            _log.debug("Body: %s", resp.text[:2000])

            if resp.status_code in (200, 201):
                data: Dict[str, Any] = resp.json() if resp.content else {}
                _log.info("Mensagem enviada com sucesso. messageId=%s", data.get("messageId", ""))
                return {
                    "success": True,
                    "messageId": data.get("messageId", ""),
                    "status": data.get("status", "queued"),
                    "error": None,
                }
            else:
                error_msg = self._extract_error(resp)
                _log.warning("Falha no envio. HTTP %s — %s", resp.status_code, error_msg)
                return {
                    "success": False,
                    "messageId": None,
                    "status": f"HTTP {resp.status_code}",
                    "error": f"HTTP {resp.status_code} — {error_msg}",
                }

        except requests.exceptions.Timeout:
            _log.error("Timeout ao chamar %s", url)
            return {"success": False, "error": f"Timeout — sem resposta do servidor ({url})."}
        except requests.exceptions.ConnectionError as exc:
            _log.error("ConnectionError ao chamar %s: %s", url, exc, exc_info=True)
            return {"success": False, "error": f"Erro de conexão — verifique a URL base.\nURL tentada: {url}\nDetalhe: {exc}"}
        except Exception as exc:  # noqa: BLE001
            _log.error("Erro inesperado: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def check_rcs_capability(
        self,
        msisdn: str,
        app_id: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Check RCS capability for a phone number.

        Returns a dict with keys:
            success (bool), enabled (bool|None), capabilities (list), error (str|None)
        """
        if not self._api_key or self._api_key == "your_service_key_here":
            return {
                "success": False,
                "enabled": None,
                "capabilities": [],
                "error": "API Key não configurada.",
            }

        url = f"{self._base_url}/v1/rcs/capabilities"
        headers = {
            "Content-Type": "application/json",
            "key": self._api_key,
        }
        payload = {
            "msisdn": [msisdn],
            "appId": app_id,
            "forceRefresh": force_refresh,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=_TIMEOUT,
            )

            if resp.status_code == 200:
                data: List[Dict[str, Any]] = resp.json()
                if data and isinstance(data, list):
                    entry = data[0]
                    return {
                        "success": True,
                        "enabled": entry.get("enabled", False),
                        "capabilities": entry.get("capabilities", []),
                        "error": None,
                    }
                return {"success": True, "enabled": False, "capabilities": [], "error": None}
            else:
                return {
                    "success": False,
                    "enabled": None,
                    "capabilities": [],
                    "error": self._extract_error(resp),
                }

        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "enabled": None,
                "capabilities": [],
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_error(resp: requests.Response) -> str:
        """Extract a human-readable error message from a failed response."""
        try:
            data = resp.json()
            # Try common error fields
            for key in ("message", "error", "description", "errorDescription"):
                if key in data:
                    return str(data[key])
            return str(data)
        except Exception:
            return resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
