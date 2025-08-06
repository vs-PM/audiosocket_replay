import asyncio
import logging
import os
import atexit
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02
HEADER_SIZE = 17
MAX_AUDIO_READ = 320   # обычно 320, реально < 320!

########### ДОБАВЬ: глобальный файл для записи ###
REC_DIR = os.path.join("data", "rec")
os.makedirs(REC_DIR, exist_ok=True)
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all.raw")
all_audio_file = open(ALL_AUDIO_PATH, "ab")

def write_all_audio(chunk: bytes):
    all_audio_file.write(chunk)
    # Для мелких записей можешь делать flush, если нужно видеть реальный размер "по ходу":
    all_audio_file.flush()

# Корректное закрытие при завершении процесса:
atexit.register(all_audio_file.close)
#################################################

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение: {addr}")
    total_audio_bytes = 0
    try:
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
            hdr = await reader.readexactly(HEADER_SIZE)
            pkt_type = hdr[0]
            pkt_uuid = parse_uuid(hdr[1:17])
            if pkt_type == AUDIO_PACKET_TYPE:
                audio = await reader.read(MAX_AUDIO_READ)
                total_audio_bytes += len(audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")

                ########### ДОБАВЛЕНО: запись аудио во "всеобщий" файл ##########
                write_all_audio(audio)
                ###############################################################

                await broadcast_audio(pkt_uuid, audio)
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
            else:
                logging.debug(f"[UNKNOWN PACKET] type=0x{pkt_type:02x} UUID={pkt_uuid}")
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
    if port is None:
        port = settings.AUDIO_PORT
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket: Слушает порт {port}")
    async with server:
        await server.serve_forever()