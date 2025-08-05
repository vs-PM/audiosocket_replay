"""
Broadcast: управление WebSocket-подписчиками и рассылка аудио-данных.
"""

import logging

ws_clients = set()

async def register_ws(ws):
    """
    Зарегистрировать ws-клиента.
    """
    ws_clients.add(ws)
    logging.info(f"WS-клиент добавлен ({len(ws_clients)} всего подключено)")

async def unregister_ws(ws):
    """
    Отписать ws-клиента.
    """
    ws_clients.discard(ws)
    logging.info(f"WS-клиент удалён ({len(ws_clients)} всего подключено)")

async def broadcast_audio(uuid: str, audio: bytes):
    """
    Рассылка аудио-пакета всем ws-клиентам.

    :param uuid: UUID звонка/сессии (строка)
    :param audio: Аудио-данные (байты)
    """
    message = {"uuid": uuid, "audio": audio.hex()}
    removed_ws = []
    for ws in list(ws_clients):
        try:
            await ws.send_json(message)
        except Exception as exc:
            removed_ws.append(ws)
            logging.error(f"Ошибка отправки данных ws-клиенту: {exc}")
    for ws in removed_ws:
        ws_clients.discard(ws)