"""Caricamento della configurazione da config.ini.

Nessun I/O all'import: i plugin importano questo modulo e leggono ``config.CFG``
dentro gli handler, così l'import dei plugin non tocca mai il filesystem.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = "config.ini"


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    operators_chat_id: int
    seed_admins: tuple[int, ...]


CFG: Config | None = None


def _int_or_exit(section: str, key: str, value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise SystemExit(
            f"[{section}] {key} non è un intero valido: {value!r}"
        ) from None


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
    """Legge ``path``, popola ``CFG`` e lo restituisce."""
    global CFG

    if not Path(path).is_file():
        raise SystemExit(
            f"File di configurazione '{path}' non trovato.\n"
            f"Copia 'config.ini.example' in '{path}' e compila i valori."
        )

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    def raw(section: str, key: str) -> str:
        try:
            value = parser[section][key]
        except KeyError:
            raise SystemExit(f"Chiave mancante in '{path}': [{section}] {key}") from None
        value = value.strip()
        if not value:
            raise SystemExit(f"Chiave vuota in '{path}': [{section}] {key}")
        return value

    api_id = _int_or_exit("pyrogram", "api_id", raw("pyrogram", "api_id"))
    operators_chat_id = _int_or_exit(
        "bot", "operators_chat_id", raw("bot", "operators_chat_id")
    )

    seed_admins: list[int] = []
    for chunk in raw("bot", "admins").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            seed_admins.append(int(chunk))
        except ValueError:
            raise SystemExit(
                f"[bot] admins contiene un ID non numerico in '{path}': {chunk!r}"
            ) from None

    CFG = Config(
        api_id=api_id,
        api_hash=raw("pyrogram", "api_hash"),
        bot_token=raw("pyrogram", "bot_token"),
        operators_chat_id=operators_chat_id,
        seed_admins=tuple(seed_admins),
    )
    return CFG
