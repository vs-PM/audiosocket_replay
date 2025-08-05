"""
Сервер приёма AudioSocket потока от Asterisk.
Парсит аудиофрагменты корректно (аналогично тестовому клиенту).
"""

import asyncio
import logging

from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02
HEADER_SIZE = 17
MAX_AUDIO_READ = 320   # Максимум, обычно 320, реально может быть меньше!

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обрабатывает подключение одного AudioSocket-клиента (обычно звонок от Asterisk).
    Корректно парсит любой размер аудиофрагмента (до 320 байт).
    """
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение: {addr}")

    total_audio_bytes = 0
    try:
        # 1. Первый стартовый пакет — header (type=0x01 + 16 байт UUID)
        header = await reader.readexactly(HEADER_SIZE)
        pkttype = header[0]
        uuid = parse_uuid(header[1:17])

        if pkttype != 1:
            logging.error(f"ОШИБКА: Первый пакет не type=0x01, а {pkttype:02x}!")
            writer.close()
            await writer.wait_closed()
            return

        logging.info(f"Началась сессия UUID: {uuid}")

        while True:
            # всегда ждем новый header (type + uuid = 17)
            hdr = await reader.readexactly(HEADER_SIZE)
            pkt_type = hdr[0]
            pkt_uuid = parse_uuid(hdr[1:17])

            if pkt_type == AUDIO_PACKET_TYPE:
                # Аудиопакет: читаем до 320 байт (может быть меньше!)
                audio = await reader.read(MAX_AUDIO_READ)
                total_audio_bytes += len(audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
                await broadcast_audio(pkt_uuid, audio)
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
            else:
                # Неизвестный пакет/log
                logging.warning(f"[UNKNOWN PACKET] type=0x{pkt_type:02x} UUID={pkt_uuid}")

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
