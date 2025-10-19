from loguru import logger
import sys
from pathlib import Path

def setup_logging():
    logger.remove()  # убираем дефолтный sink
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # консоль
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                      "<level>{level: <8}</level> | "
                      "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                      "<level>{message}</level>")

    # файл с ротацией
    logger.add(
        logs_dir / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
