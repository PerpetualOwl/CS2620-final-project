from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Union

import requests
from requests import Response

_JSON = Union[Dict[str, Any], List[Any]]


class NodeError(RuntimeError):
    """Raised when the node returns a non‑2xx JSON response with an error body."""


class PosNodeClient:
    """
    Minimal client for the Proof‑of‑Stake Blockchain Node API (v1.1.0).

    Parameters
    ----------
    host : str
        e.g. "127.0.0.1"
    port : int | str
        e.g. 10000
    """

    def __init__(self, host: str = "127.0.0.1", port: Union[int, str] = 10000) -> None:
        self.base = f"http://{host}:{port}".rstrip("/")

    # ------------- helpers --------------------------------------------------

    @staticmethod
    def _json(response: Response) -> _JSON:
        """
        Return response.json() or raise NodeError with the 'message' field
        if the status code signals failure.
        """
        try:
            data: _JSON = response.json()
        except json.JSONDecodeError:
            response.raise_for_status()
            raise  # should never reach here

        if not response.ok:
            msg = data.get("message") if isinstance(data, dict) else None
            raise NodeError(msg or f"Node returned {response.status_code}")
        return data

    # ------------- endpoint wrappers ---------------------------------------

    # /wallet/new  -----------------------------------------------------------
    def create_wallet(self) -> str:
        r = requests.post(f"{self.base}/wallet/new", headers={"Accept": "application/json"})
        return self._json(r)["address"]

    # /transactions/new  -----------------------------------------------------
    def create_transaction(
        self,
        sender: str,
        recipient: str,
        amount: int,
        token: str = "MAIN",
    ) -> str:
        body = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "token_type": token,
        }
        r = requests.post(f"{self.base}/transactions/new", json=body)
        return self._json(r)["message"]

    # /balance/{address}  ----------------------------------------------------
    def get_balance(self, address: str) -> Dict[str, int]:
        r = requests.get(f"{self.base}/balance/{address}", headers={"Accept": "application/json"})
        return self._json(r)["balances"]  # {'MAIN': ..., 'SECOND': ...}

    # /chain  ----------------------------------------------------------------
    def get_chain(self) -> _JSON:
        r = requests.get(f"{self.base}/chain")
        return self._json(r)
