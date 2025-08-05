"""
Сервер приёма AudioSocket-потока от Asterisk. Прокидывает аудиофрагменты дальше.
"""

import asyncio
import logging
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

async def handle_client(reader, writer):
    """
    Обрабатывает подключение одного AudioSocket-клиента (один звонок).
    """
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение от {addr}")
    total_audio_bytes = 0
    try:
        header = await reader.readexactly(17)
        pkttype = header[0]
        uuid = parse_uuid(header[1:17])
        if pkttype != 1:
            logging.error(f"ОШИБКА: Первый пакет не type=0x01, а {pkttype:02x}!")
            writer.close()
            await writer.wait_closed()
            return

        logging.info(f"AudioSocket-сессия UUID: {uuid}")

        while True:
            hdr = await reader.readexactly(17)
            ptype = hdr[0]
            pkt_uuid = parse_uuid(hdr[1:17])
            if ptype == 0x10:
                audio = await reader.readexactly(320)
                total_audio_bytes += len(audio)
                await broadcast_audio(pkt_uuid, audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
            elif ptype == 0x02:
                logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
            else:
                logging.warning(f"[UNKNOWN PACKET] type=0x{ptype:02x} UUID={pkt_uuid}")

    except asyncio.IncompleteReadError:
        logging.info(f"Сессия {addr} завершена или конец потока")
    except Exception as e:
        logging.error(f"Ошибка в AudioSocket-сессии ({addr}): {e}")
    finally:
        logging.info(f"Сессия {addr} закрыта, принято аудиобайт: {total_audio_bytes}")
        writer.close()
        await writer.wait_closed()

async def run_audiosocket_server(port=None):
    """
    Запуск TCP сервера.
    """
    if port is None:
        port = settings.AUDIO_PORT
    server = await asyncio.start_server(handle_client, '0.0.0.0', port)
    logging.info(f"AudioSocket: Слушаем порт {port}")
    async with server:
        await server.serve_forever()
