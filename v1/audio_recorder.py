# В файле v1/audio_recorder.py ----
import asyncio
import logging
import os

AUDIO_PORT = 4001  # тот же, что и сервер Listen
HEADER_SIZE = 17
MAX_AUDIO_READ = 320

def parse_uuid(b):
    bs = b.hex()
    return f'{bs[:8]}-{bs[8:12]}-{bs[12:16]}-{bs[16:20]}-{bs[20:32]}'

async def audio_logger(port=AUDIO_PORT):
    rec_dir = os.path.join("data", "rec")
    os.makedirs(rec_dir, exist_ok=True)
    all_audio_path = os.path.join(rec_dir, "all.raw")
    all_audio_file = open(all_audio_path, "ab")
    logging.info(f"Audio recorder listening at port {port}, writing to {all_audio_path}")

    async def handle(reader, writer):
        addr = writer.get_extra_info("peername")
        session_uuid = None
        total = 0
        try:
            header = await reader.readexactly(HEADER_SIZE)
            pkttype = header[0]
            uuid = parse_uuid(header[1:17])
            session_uuid = uuid
            logging.info(f"New session: {addr}, UUID={uuid}")
            while True:
                hdr = await reader.readexactly(HEADER_SIZE)
                pkt_type = hdr[0]
                pkt_uuid = parse_uuid(hdr[1:17])
                if pkt_type == 0x10:
                    audio = await reader.read(MAX_AUDIO_READ)
                    total += len(audio)
                    logging.debug(f"[AUDIO] UUID={pkt_uuid} bytes={len(audio)}")
                    all_audio_file.write(audio)
                    all_audio_file.flush()
                elif pkt_type == 0x02:
                    logging.debug(f"[HEARTBEAT] UUID={pkt_uuid}")
                else:
                    logging.debug(f"[UNKNOWN PACKET] type=0x{pkt_type:02x} UUID={pkt_uuid}")
        except asyncio.IncompleteReadError:
            logging.info(f"Session done (IncompleteRead) UUID={session_uuid}, addr={addr}, bytes={total}")
        except Exception as e:
            logging.error(f"Recording error UUID={session_uuid}, addr={addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "0.0.0.0", port)
    logging.info(f"Audio recorder started at port {port}. Waiting for AudioSocket streams...")
    async with server:
        await server.serve_forever()