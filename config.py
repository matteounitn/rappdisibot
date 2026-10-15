"""Caricamento della configurazione.

I **segreti** (`api_id`, `api_hash`, `bot_token`) si leggono, in ordine di
precedenza:

1. variabili d'ambiente con prefisso `RAPPDISIBOT_` (es. `RAPPDISIBOT_BOT_TOKEN`);
2. file `.env` nella cartella da cui si avvia il bot (vedi `.env.example`);
3. sezione `[pyrogram]` di `config.ini` (compatibilità).

Le impostazioni non segrete (`operators_chat_id`, `admins`) restano in
`config.ini`. Nessun I/O all'import: i plugin leggono `config.CFG` dentro gli
handler, così l'import dei plugin non tocca mai il filesystem.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = "config.ini"
DEFAULT_ENV_PATH = ".env"
ENV_PREFIX = "RAPPDISIBOT_"


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    operators_chat_id: int
    seed_admins: tuple[int, ...]


CFG: Config | None = None


def _leggi_dotenv(path: str) -> dict[str, str]:
    """Legge un `.env` minimale: `CHIAVE=valore`, `#` per i commenti."""
    file = Path(path)
    if not file.is_file():
        return {}

    valori: dict[str, str] = {}
    for riga in file.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        valori[chiave.strip()] = valore.strip().strip('"').strip("'")
    return valori


def _int_or_exit(nome: str, value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise SystemExit(f"{nome} non è un intero valido: {value!r}") from None


def load_config(
    path: str = DEFAULT_CONFIG_PATH, env_path: str = DEFAULT_ENV_PATH
) -> Config:
    """Legge la configurazione, popola ``CFG`` e lo restituisce."""
    global CFG

    if not Path(path).is_file():
        raise SystemExit(
            f"File di configurazione '{path}' non trovato.\n"
            f"Copia 'config.ini.example' in '{path}' e compila i valori."
        )

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    # L'ambiente reale ha la precedenza sul file .env.
    ambiente = {**_leggi_dotenv(env_path), **os.environ}

    def segreto(nome: str, sezione: str, chiave: str) -> str:
        """Valore di un segreto: ambiente/.env, altrimenti config.ini."""
        value = ambiente.get(f"{ENV_PREFIX}{nome}")
        if value:
            return value
        try:
            value = parser[sezione][chiave]
        except KeyError:
            value = ""
        value = value.strip()
        if not value:
            raise SystemExit(
                f"Segreto '{nome}' mancante.\n"
                f"Impostalo in '{env_path}' come {ENV_PREFIX}{nome}=... "
                f"(vedi '.env.example'), oppure in '{path}' sotto [{sezione}] {chiave}."
            )
        return value

    def richiesto(sezione: str, chiave: str) -> str:
        try:
            value = parser[sezione][chiave]
        except KeyError:
            raise SystemExit(f"Chiave mancante in '{path}': [{sezione}] {chiave}") from None
        value = value.strip()
        if not value:
            raise SystemExit(f"Chiave vuota in '{path}': [{sezione}] {chiave}")
        return value

    api_id = _int_or_exit("api_id", segreto("API_ID", "pyrogram", "api_id"))
    operators_chat_id = _int_or_exit(
        "operators_chat_id", richiesto("bot", "operators_chat_id")
    )

    seed_admins: list[int] = []
    for chunk in richiesto("bot", "admins").split(","):
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
        api_hash=segreto("API_HASH", "pyrogram", "api_hash"),
        bot_token=segreto("BOT_TOKEN", "pyrogram", "bot_token"),
        operators_chat_id=operators_chat_id,
        seed_admins=tuple(seed_admins),
    )
    return CFG
