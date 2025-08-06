import asyncio
import logging
import logging.handlers
from v1.audiosocket import run_audiosocket_server
from v1.config import settings
from v1.ws_server import run_ws_server

def setup_logging():
    loglevel = settings.LOG_LEVEL.upper()
    # основной лог в stdout
    logging.basicConfig(
        level=loglevel,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # отдельный логгер для аудиодиагностики
    audio_logfile = "audiosocket_diag.log"
    audio_logger = logging.getLogger("audio_diag")
    handler = logging.handlers.RotatingFileHandler(
        audio_logfile, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    audio_logger.setLevel(logging.INFO)
    audio_logger.addHandler(handler)

async def main():
    setup_logging()
    logging.info(f"Старт сервиса, PROD={settings.PROD_REPLAY}")
    await asyncio.gather(
        run_audiosocket_server(port=settings.AUDIO_PORT),
        run_ws_server(port=settings.WS_PORT),
    )

if __name__ == "__main__":
    asyncio.run(main())