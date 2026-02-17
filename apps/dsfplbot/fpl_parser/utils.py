from datetime import datetime
import json
import logging
import sys


def load_config(path: str) -> dict:
    """Загружает конфигурацию из JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_logging(level=logging.INFO):
    """Настраивает логирование."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("fpl_parser.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
