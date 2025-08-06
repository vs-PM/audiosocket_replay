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
MAX_AUDIO_READ = 320  # Обычно 320, реально может быть < 320!

###########################
# === БЛОК: Подготовка "единого файла" для записи всего аудиопотока ===

# Определяем директорию и путь к файлу
REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all.raw")

all_audio_file = None  # Глобальная переменная для файлового объекта

def setup_audio_file():
    """Создать директорию, открыть файл для записи аудио, сделать логирование."""
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
    """Записывает аудиобайт в единый файл, с логом и защитой от ошибок."""
    global all_audio_file
    if all_audio_file:
        all_audio_file.write(chunk)
        all_audio_file.flush()
        logging.debug(f"Записано {len(chunk)} байт в {ALL_AUDIO_PATH}")
    else:
        logging.error("all_audio_file не открыт — запись не выполнена!")

def close_audio_file():
    """Безопасное закрытие файла при завершении работы приложения."""
    global all_audio_file
    if all_audio_file and not all_audio_file.closed:
        logging.info(f"Закрываем файл {ALL_AUDIO_PATH}")
        all_audio_file.close()

# === Вызовы подготовки и регистрации финального закрытия ===
setup_audio_file()
atexit.register(close_audio_file)
###########################

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Обрабатывает подключение одного AudioSocket-клиента (обычно звонок от Asterisk).
    Корректно парсит любой размер аудиофрагмента (до 320 байт).
    Также пишет каждый принятый аудиоблок в единый файл.
    """
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение: {addr}")
    total_audio_bytes = 0
    try:
        # Первый стартовый пакет — header (type=0x01 + 16 байт UUID)
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
            # Ждём очередной пакет (header: type+uuid)
            hdr = await reader.readexactly(HEADER_SIZE)
            pkt_type = hdr[0]
            pkt_uuid = parse_uuid(hdr[1:17])
            if pkt_type == AUDIO_PACKET_TYPE:
                # Аудиопакет: читаем до 320 байт
                audio = await reader.read(MAX_AUDIO_READ)
                total_audio_bytes += len(audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
                # --- Основная запись в единый файл ---
                write_all_audio(audio)
                # --- Конец записи ---
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
    """
    if port is None:
        port = settings.AUDIO_PORT
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket: Слушает порт {port}")
    async with server:
        await server.serve_forever()
