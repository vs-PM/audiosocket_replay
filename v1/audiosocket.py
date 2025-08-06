import asyncio
import logging
import os

AUDIO_PACKET_TYPE = 0x10
HEARTBEAT_PACKET_TYPE = 0x02
HEADER_SIZE = 17
CHUNK_SIZE = 640  # slin16, 16kHz, 20ms

REC_DIR = os.path.join("data", "rec")
ALL_AUDIO_PATH = os.path.join(REC_DIR, "all.raw")

def setup_audio_file():
    os.makedirs(REC_DIR, exist_ok=True)
    return open(ALL_AUDIO_PATH, "wb")

async def handle_client(reader, writer):
    logging.info("New connection")
    fout = setup_audio_file()
    total_audio_bytes = 0

    # Прочитать первый (обычно служебный) пакет (НЕ писать его)
    header = await reader.readexactly(HEADER_SIZE)
    fmttype = header[0]
    if fmttype != AUDIO_PACKET_TYPE:
        logging.info(f"First packet type={fmttype:02x}, skipping payload if any")

    # Чтение основного потока (только type=0x10)
    try:
        while True:
            # header
            header = await reader.readexactly(HEADER_SIZE)
            pkt_type = header[0]

            if pkt_type == AUDIO_PACKET_TYPE:
                audio = await reader.readexactly(CHUNK_SIZE)
                fout.write(audio)
                total_audio_bytes += CHUNK_SIZE
                logging.debug(f"[AUDIO] bytes={CHUNK_SIZE}")
            elif pkt_type == HEARTBEAT_PACKET_TYPE:
                logging.debug("[HEARTBEAT]")
                continue
            else:
                logging.warning(f"[UNKNOWN PACKET] type={pkt_type:02x}")
                continue
    except asyncio.IncompleteReadError:
        logging.info(f"Session closed, wrote {total_audio_bytes} bytes")
    except Exception as e:
        logging.error(f"Stream err: {e}")
    finally:
        fout.close()

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )
    server = await asyncio.start_server(handle_client, host="0.0.0.0", port=4000)
    logging.info("AudioSocket server started on port 4000")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())