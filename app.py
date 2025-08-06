"""
Главная точка входа. Запускает TCP-сервер (AudioSocket) и WebSocket сервер.
"""

import asyncio
import logging
from v1.audiosocket import run_audiosocket_server
from v1.ws_server import run_ws_server
from v1.config import settings
from v1.audio_recorder import audio_logger  # <= новинка!

def setup_logging():
    loglevel = settings.LOG_LEVEL.upper()
    logging.basicConfig(
        level=loglevel,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    
async def main():
    setup_logging()
    logging.info(f"Старт сервиса, PROD={settings.PROD_REPLAY}")

    await asyncio.gather(
        run_audiosocket_server(port=settings.AUDIO_PORT),
        run_ws_server(port=settings.WS_PORT),
        audio_logger(settings.AUDIO_PORT),   # вот тут добавлен аудиорекордер!
    )

if __name__ == "__main__":
    asyncio.run(main())