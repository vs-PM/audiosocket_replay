"""
Утилитарные функции (например, парсинг UUID).
"""

def parse_uuid(uuid_bytes: bytes) -> str:
    """
    Преобразует 16 байт UUID в строку xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.

    :param uuid_bytes: Массив байт UUID (16 байт)
    :return: Строковое представление UUID
    """
    hexstr = uuid_bytes.hex()
    return f"{hexstr[:8]}-{hexstr[8:12]}-{hexstr[12:16]}-{hexstr[16:20]}-{hexstr[20:32]}"