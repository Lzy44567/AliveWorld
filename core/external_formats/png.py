"""Dependency-free, bounded PNG text-chunk reader for character cards."""

from __future__ import annotations

import struct
import zlib

from .models import ExternalFormatError


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_CHUNK_BYTES = 8 * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024


def read_character_text_chunks(payload: bytes) -> dict[str, bytes]:
    if not payload.startswith(PNG_SIGNATURE):
        raise ExternalFormatError("文件不是有效的 PNG/APNG 角色卡")
    chunks: dict[str, bytes] = {}
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        if length > MAX_CHUNK_BYTES or offset + 12 + length > len(payload):
            raise ExternalFormatError("PNG 元数据块尺寸异常或文件不完整")
        data = payload[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"tEXt":
            keyword, separator, value = data.partition(b"\0")
            if separator and keyword in {b"ccv3", b"chara"}:
                chunks[keyword.decode("ascii")] = value[:MAX_TEXT_BYTES]
        elif kind == b"zTXt":
            keyword, separator, encoded = data.partition(b"\0")
            if separator and keyword in {b"ccv3", b"chara"} and encoded[:1] == b"\0":
                try:
                    decoder = zlib.decompressobj()
                    value = decoder.decompress(encoded[1:], MAX_TEXT_BYTES + 1)
                    if decoder.unconsumed_tail or len(value) > MAX_TEXT_BYTES:
                        raise ExternalFormatError("PNG 压缩元数据超过安全限制")
                    chunks[keyword.decode("ascii")] = value
                except zlib.error as exc:
                    raise ExternalFormatError("PNG 压缩角色卡元数据损坏") from exc
        if kind == b"IEND":
            break
    if not chunks:
        raise ExternalFormatError("PNG 中没有找到 ccv3 或 chara 角色卡元数据")
    return chunks
