"""
Сервер приёма AudioSocket потока от Asterisk. Парсит аудиофрагменты и ретранслирует их через broadcast_audio.
"""

import asyncio
import logging
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обрабатывает подключение одного AudioSocket-клиента (обычно звонок от Asterisk).
    """
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение: {addr}")
    total_audio_bytes = 0

    try:
        # 1. Первый пакет (17 байт): 0x01 + 16 байт UUID
        header = await reader.readexactly(17)
        pkttype = header[0]
        uuid = parse_uuid(header[1:17])
        if pkttype != 1:
            logging.error(f"ОШИБКА: Первый пакет не type=0x01, а {pkttype:02x}!")
            writer.close()
            await writer.wait_closed()
            return

        logging.info(f"Началась сессия UUID: {uuid}")

        # 2. Далее цикл обработки входящих пакетов
        while True:
            # Читаем следующий заголовок: 1 байт type + 16 байт uuid
            hdr = await reader.readexactly(17)
            ptype = hdr[0]
            pkt_uuid = parse_uuid(hdr[1:17])
            if ptype == 0x10:
                # Audio packet (type=0x10, чаще всего 320 байт slin16)
                audio = await reader.readexactly(320)
                total_audio_bytes += len(audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
                # Отправляем аудио всем ws-клиентам
                await broadcast_audio(pkt_uuid, audio)
            elif ptype == 0x02:
                logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
            else:
                # Неизвестный тип — выводим warn, по желанию дамп хедера
                logging.warning(f"[UNKNOWN PACKET] type=0x{ptype:02x} UUID={pkt_uuid}")

    except asyncio.IncompleteReadError:
        logging.info(f"Сессия завершена (или конец потока от {addr})")
    except Exception as e:
        logging.error(f"Ошибка в AudioSocket-сессии ({addr}): {e}")
    finally:
        logging.info(
            f"Сессия {addr} завершена, принято аудиобайт: {total_audio_bytes}"
        )
        writer.close()
        await writer.wait_closed()

async def run_audiosocket_server(port=None):
    """
    Запуск TCP сервера AudioSocket.
    """
    if port is None:
        port = settings.AUDIO_PORT
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket: Слушает порт {port}")
    async with server:
        await server.serve_forever()
