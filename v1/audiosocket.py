import asyncio
import logging
import os
import atexit
from collections import Counter
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02
HEADER_SIZE = 17
MAX_AUDIO_READ = 320  # Ожидаемый размер аудиочанка

REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all-3.raw")
all_audio_file = None

# Логгер для аудиодиагностики
audio_diag_logger = logging.getLogger("audio_diag")

def setup_audio_file():
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
        audio_diag_logger.debug(f"Записано {len(chunk)} байт в {ALL_AUDIO_PATH}")
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
    audio_packet_num = 0
    audio_chunk_sizes = Counter()
    uuid_counter = Counter()
    try:
        header = await reader.readexactly(HEADER_SIZE)  # Строго ровно HEADER_SIZE
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
                try:
                    audio = await reader.readexactly(MAX_AUDIO_READ)
                except asyncio.IncompleteReadError as e:
                    audio_diag_logger.error(f"[ERR] Не удалось дочитать аудиофрейм: packet={audio_packet_num+1} (получено {len(e.partial)} байт из {MAX_AUDIO_READ}) UUID={pkt_uuid}")
                    break
                audio_packet_num += 1
                audio_chunk_sizes[len(audio)] += 1
                uuid_counter[str(pkt_uuid)] += 1
                audio_diag_logger.info(
                    f"#{audio_packet_num:05d} UUID={pkt_uuid} size={len(audio)} "
                    f"head={audio[:8].hex()} tail={audio[-8:].hex()}"
                )
                if len(audio) != MAX_AUDIO_READ:
                    audio_diag_logger.error(f"[ERR] НЕПОЛНЫЙ ЧАНК: packet={audio_packet_num} size={len(audio)} UUID={pkt_uuid}")
                    # Не пишем в файл битые фреймы!
                    continue
                total_audio_bytes += len(audio)
                write_all_audio(audio)
                await broadcast_audio(pkt_uuid, audio)
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                audio_diag_logger.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
            else:
                audio_diag_logger.warning(f"[UNKNOWN PACKET] type=0x{pkt_type:02x} UUID={pkt_uuid}")
    except asyncio.IncompleteReadError:
        logging.info(f"Сессия завершена (или конец потока от {addr})")
        audio_diag_logger.info("=== Сессия завершена ===")
    except Exception as e:
        logging.error(f"Ошибка в AudioSocket-сессии ({addr}): {e}")
        audio_diag_logger.exception(f"Исключение: {e}")
    finally:
        audio_diag_logger.info(
            f"ИТОГ: всего пакетов={audio_packet_num}, принято аудиобайт={total_audio_bytes}, "
            f"chunk_sizes={dict(audio_chunk_sizes)}, "
            f"uuid_counter_top3={uuid_counter.most_common(3)}"
        )
        writer.close()
        await writer.wait_closed()

async def run_audiosocket_server(port=None):
    if port is None:
        port = settings.AUDIO_PORT
    setup_audio_file()
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket: Слушает порт {port}")
    async with server:
        await server.serve_forever()
