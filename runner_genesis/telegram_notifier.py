from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .engines.early_runner_v2 import EarlyRunnerEvent


@dataclass(slots=True)
class TelegramNotifier:
    bot_token: str
    chat_id: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            return None
        return cls(token, chat_id)

    def send(self, event: EarlyRunnerEvent) -> bool:
        """Send one already-formatted Spanish engine event to Telegram."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            r = client.post(url, json={"chat_id": self.chat_id, "text": event.telegram_text})
            r.raise_for_status()
        return True
