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
MAX_AUDIO_READ = 320

# Глобальные переменные для аудиофайла
REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all-5.raw")
all_audio_file = None

def setup_audio_file():
    """
    Создать директорию и открыть файл для записи аудио.
    Можно вызывать сколько угодно раз — повторно ничего не случится.
    """
    global all_audio_file
    try:
        if not os.path.exists(REC_DIR):
            logging.info(f"Создаём директорию для записи аудио: {REC_DIR}")
            os.makedirs(REC_DIR, exist_ok=True)
        all_audio_file = open(ALL_AUDIO_PATH, "ab")
        logging.info(f"Открыт единый аудиофайл для записи: {ALL_AUDIO_PATH}")
    except Exception as e:
        logging.critical(f"Ошибка открытия файла {ALL_AUDIO_PATH}: {e}")
        all_audio_file = None

def write_all_audio(chunk: bytes):
    global all_audio_file
    if all_audio_file:
        all_audio_file.write(chunk)
        all_audio_file.flush()
        logging.debug(f"Записано {len(chunk)} байт в {ALL_AUDIO_PATH}")
    else:
        logging.error("all_audio_file не открыт — запись не выполнена!")

def close_audio_file():
    global all_audio_file
    if all_audio_file and not all_audio_file.closed:
        logging.info(f"Закрываем файл {ALL_AUDIO_PATH}")
        all_audio_file.close()

atexit.register(close_audio_file)

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
                write_all_audio(audio)
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
    """
    Запуск TCP сервера AudioSocket.
    Перед стартом сервера вызываем setup_audio_file(),
    когда уже настроено логирование!
    """
    if port is None:
        port = settings.AUDIO_PORT
    setup_audio_file()  # Теперь вызываем тут, когда logging уже сконфигурирован!
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket: Слушает порт {port}")
    async with server:
        await server.serve_forever()
