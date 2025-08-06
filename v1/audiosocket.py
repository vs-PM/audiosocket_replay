import asyncio
import logging
import os
import atexit

# === НАСТРОЙКИ ===

AUDIO_PORT = 4000      # ваш порт AudioSocket (из dialplan)
CHUNK_SIZE = 640       # ЧАНК для slin16/16000Hz/20ms = 16,000 * 2 * 0.02 = 640 байт
HEADER_SIZE = 17
AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02

REC_DIR = os.path.join("data", "rec")      # директория под raw-файлы
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all.raw")
all_audio_file = None

# === ФУНКЦИИ РАБОТЫ С ФАЙЛОМ ===

def setup_audio_file():
    """Открывает/создаёт файл для записи аудио."""
    global all_audio_file
    os.makedirs(REC_DIR, exist_ok=True)
    all_audio_file = open(ALL_AUDIO_PATH, "wb")  # всегда перезаписать!
    logging.info(f"Открыт файл для аудиозаписи: {ALL_AUDIO_PATH}")

def write_all_audio(chunk: bytes):
    """Записывает один raw-чанк аудиоданных."""
    global all_audio_file
    if all_audio_file:
        all_audio_file.write(chunk)
        # можно добавить .flush() если хочется полностью write-through
        logging.debug(f"Записано {len(chunk)} байт в {ALL_AUDIO_PATH}")
    else:
        logging.error("Файл audio не открыт!")

def close_audio_file():
    """Безопасно закрывает файл аудио при выходе."""
    global all_audio_file
    if all_audio_file and not all_audio_file.closed:
        all_audio_file.close()
        logging.info(f"Файл закрыт: {ALL_AUDIO_PATH}")

atexit.register(close_audio_file)


# === ОБРАБОТЧИК TCP-КЛИЕНТА ===

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое подключение: {addr}")
    total_audio_bytes = 0
    try:
        # Первый пакет — обычно type 0x01; UUID в header[1:17]
        header = await reader.readexactly(HEADER_SIZE)
        pkttype = header[0]
        session_uuid = header[1:17].hex('-')
        logging.info(f"Началась сессия: UUID={session_uuid}, [type={pkttype:02x}]")
        # далее — циклично: HEADER + PAYLOAD
        while True:
            hdr = await reader.readexactly(HEADER_SIZE)
            pkt_type = hdr[0]
            pkt_uuid = hdr[1:17].hex('-')
            if pkt_type == AUDIO_PACKET_TYPE:
                audio = await reader.readexactly(CHUNK_SIZE) # ВАЖНО: строго CHUNK_SIZE!
                write_all_audio(audio)
                total_audio_bytes += len(audio)
                logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
                continue
            else:
                logging.warning(f"[UNKNOWN PACKET] type={pkt_type:02x} UUID={pkt_uuid}")
    except asyncio.IncompleteReadError:
        logging.info(f"Сессия завершена: {addr}, принято аудио: {total_audio_bytes} байт")
    except Exception as e:
        logging.error(f"Ошибка в AudioSocket-сессии ({addr}): {e}")
    finally:
        writer.close()
        await writer.wait_closed()


# === ЗАПУСК СЕРВЕРА ===

async def run_audiosocket_server(port=AUDIO_PORT):
    """Запуск TCP AudioSocket listener."""
    setup_audio_file()
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logging.info(f"AudioSocket-сервер слушает порт {port}")
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s | %(levelname)8s | %(message)s")
    # Для асинхронного запуска сервера:
    asyncio.run(run_audiosocket_server())
