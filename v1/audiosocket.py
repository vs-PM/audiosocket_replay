import asyncio
import logging
import os
import atexit
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all-7.raw")
all_audio_file = None

def setup_audio_file():
    global all_audio_file
    try:
        os.makedirs(REC_DIR, exist_ok=True)
        all_audio_file = open(ALL_AUDIO_PATH, "ab")
        logging.info(f"Аудиофайл готов: {ALL_AUDIO_PATH}")
    except Exception as e:
        logging.critical(f"Ошибка файла: {e}")
        all_audio_file = None

def write_all_audio(chunk: bytes):
    if all_audio_file:
        all_audio_file.write(chunk)
        all_audio_file.flush()

def close_audio_file():
    if all_audio_file and not all_audio_file.closed:
        all_audio_file.close()

atexit.register(close_audio_file)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logging.info(f"Новое соединение: {addr}")
    total_audio_bytes = 0
    session_uuid = None

    try:
        # === 0. Считываем init-пакет (17 байт), только один раз в начале соед. ===
        init_data = await reader.readexactly(17)
        if init_data[0] != 0x01:
            logging.error(f"[Relay] ОШИБКА: Первый пакет 0x{init_data[0]:02x} (нужен 0x01)")
            logging.debug(f"[Relay] Получено: {init_data.hex()}")
            return
        session_uuid = parse_uuid(init_data[1:17])
        logging.info(f"Сессия начата: {session_uuid}")

        packet_counter = 0
        while True:
            # === 1. Читаем strict: 3 байта header (type(1)+len(2)), потом len байт payload ===
            header = await reader.readexactly(3)
            pkt_type = header[0]
            payload_length = int.from_bytes(header[1:3], 'big')
            if payload_length > 65535 or payload_length < 0:
                logging.error(f"Некорректная длина пакета: {payload_length}")
                break
            payload = await reader.readexactly(payload_length)
            packet_counter += 1

            if packet_counter == 1:
                logging.debug(f"Пакет 1: тип=0x{pkt_type:02x}, длина={payload_length}")
                logging.debug(f"Header: {header.hex()}")
                logging.debug(f"Payload[0:16]: {payload[:16].hex()}")

            if pkt_type == 0x10:  # AUDIO_PACKET_TYPE
                if payload_length >= 16:
                    uuid = parse_uuid(payload[:16])
                    audio = payload[16:]
                else:
                    uuid = session_uuid
                    audio = payload
                    logging.warning("Payload AUDIO слишком короток!")

                total_audio_bytes += len(audio)
                write_all_audio(audio)
                await broadcast_audio(uuid, audio)

            elif pkt_type == 0x02:  # HEARTBEAT
                logging.debug(f"[Relay] Heartbeat [{session_uuid}]")
            elif pkt_type == 0x03:  # DTMF
                logging.info(f"[Relay] DTMF: {payload.decode('ascii', 'ignore')}")
            elif pkt_type == 0xFF:  # ERROR
                if payload:
                    logging.error(f"[Relay] Ошибка от Asterisk: код=0x{payload[0]:02x}")
                else:
                    logging.error("[Relay] Ошибка пакета: пустой payload")
            else:
                logging.warning(f"[Relay] Неизвестный тип: 0x{pkt_type:02x}")
                # Сохраним для диагностики
                with open(os.path.join(REC_DIR, "unknown_packets.bin"), "ab") as f:
                    f.write(header + payload)

    except asyncio.IncompleteReadError:
        logging.info(f"[Relay] Соединение закрыто: {addr}")
    except Exception as e:
        logging.error(f"[Relay] Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        logging.info(f"[Relay] Сессия завершена: {session_uuid}, аудио={total_audio_bytes} байт")
        writer.close()
        await writer.wait_closed()

async def run_audiosocket_server(port=None):
    port = port or settings.AUDIO_PORT
    setup_audio_file()
    server = await asyncio.start_server(
        handle_client,
        "0.0.0.0",
        port,
        reuse_address=True,
        start_serving=True
    )
    logging.info(f"AudioSocket слушает 0.0.0.0:{port}")
    async with server:
        await server.serve_forever()
