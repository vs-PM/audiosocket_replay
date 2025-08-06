import asyncio
import logging
import os
import atexit
from .broadcast import broadcast_audio
from .utils import parse_uuid
from .config import settings

# Константы пакетов
INIT_PACKET_TYPE = 0x01
AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02
DTMF_PACKET_TYPE = 0x03
ERROR_PACKET_TYPE = 0xFF

# Глобальные переменные для аудиофайла
REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all-5.raw")
all_audio_file = None

def setup_audio_file():
    """Создание директории и файла для записи аудио"""
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
        # 1. Инициализационный пакет (17 байт)
        init_data = await reader.readexactly(17)
        if init_data[0] != INIT_PACKET_TYPE:
            logging.error(f"ОШИБКА: Первый пакет 0x{init_data[0]:02x}, ожидался 0x01!")
            logging.debug(f"Полученные данные: {init_data.hex()}")
            return
        
        session_uuid = parse_uuid(init_data[1:17])
        logging.info(f"Сессия начата: {session_uuid}")
        
        # 2. Обработка остальных пакетов
        packet_counter = 0
        while True:
            header = await reader.readexactly(3)
            pkt_type = header[0]
            payload_length = (header[1] << 8) | header[2]
            
            # Защита от некорректной длины
            if payload_length > 65535 or payload_length < 0:
                logging.error(f"Некорректная длина пакета: {payload_length}")
                break
                
            payload = await reader.readexactly(payload_length)
            packet_counter += 1
            
            # Логируем первый пакет для диагностики
            if packet_counter == 1:
                logging.debug(f"Первый пакет: тип=0x{pkt_type:02x}, длина={payload_length}")
                logging.debug(f"Заголовок: {header.hex()}")
                logging.debug(f"Payload (первые 16 байт): {payload[:16].hex()}")

            if pkt_type == AUDIO_PACKET_TYPE:
                total_audio_bytes += len(payload)
                write_all_audio(payload)
                await broadcast_audio(session_uuid, payload)
                
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                logging.debug(f"Хартбит")
                
            elif pkt_type == DTMF_PACKET_TYPE:
                logging.info(f"DTMF: {payload.decode('ascii', 'ignore')}")
                
            elif pkt_type == ERROR_PACKET_TYPE:
                logging.error(f"Ошибка от Asterisk: код=0x{payload[0]:02x}")
                
            else:
                logging.warning(f"Неизвестный тип: 0x{pkt_type:02x}")
                # Сохраняем сырые данные для анализа
                with open(os.path.join(REC_DIR, "unknown_packets.bin"), "ab") as f:
                    f.write(header + payload)
    
    except asyncio.IncompleteReadError:
        logging.info(f"Соединение закрыто: {addr}")
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        logging.info(f"Сессия завершена: {session_uuid}, аудио={total_audio_bytes} байт")
        writer.close()
        await writer.wait_closed()

async def run_audiosocket_server(port=None):
    """Запуск сервера AudioSocket"""
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