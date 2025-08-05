"""
WebSocket сервер. Отдаёт аудиопоток подписчикам.
"""

import asyncio
import logging
import websockets
import json
from .broadcast import register_ws, unregister_ws

async def ws_handler(websocket):
    """
    Обработка одного WebSocket-клиента.
    """
    await register_ws(websocket)
    logging.info("WS-подключение открытo.")
    try:
        # Для клиента можно в будущем добавить authentification/keepalive/резерв
        await websocket.wait_closed()
    finally:
        await unregister_ws(websocket)
        logging.info("WS-подключение закрыто.")

async def run_ws_server(port):
    """
    Запуск WS-сервера.
    """
    async with websockets.serve(ws_handler, "0.0.0.0", port):
        logging.info(f"WS сервер: слушаем порт {port}")
        await asyncio.Future()
