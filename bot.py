"""Avvio di RappDisiBot."""

from __future__ import annotations

import logging

from pyrogram import Client

import config
import core
import db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("rappdisibot")


def main() -> None:
    cfg = config.load_config()  # SystemExit con messaggio chiaro se il file è rotto
    db.init()
    db.seed_admins(cfg.seed_admins)
    core.load_admins()
    core.load_operators()
    core.load_ops_chat()

    app = Client(
        "rappdisibot",
        api_id=cfg.api_id,
        api_hash=cfg.api_hash,
        bot_token=cfg.bot_token,
        plugins=dict(root="plugins"),
    )

    log.info("Avvio bot…")
    app.run()


if __name__ == "__main__":
    main()
