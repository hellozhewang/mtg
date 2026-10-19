"""BSON, the format Tabletop Simulator uploads saves to the Steam Workshop in.

A TTS Workshop item is one file, `WorkshopUpload`: the save's JSON, as BSON. This is
the small part of the BSON spec those saves use, matching TTS's own choices: whole
numbers are int32 (int64 when too big, or for INT64_KEYS), other numbers are doubles. `encode(decode(b))`
returns `b` byte for byte for a real TTS upload (tests/test_tts_bson.py).
"""
from __future__ import annotations

import struct

INT32 = (-2**31, 2**31 - 1)
# Fields TTS declares as 64-bit (C# long), so they are int64 even when small or 0.
INT64_KEYS = {"OwnerSteamID"}


def _cstring(text: str) -> bytes:
    raw = text.encode("utf-8")
    if b"\x00" in raw:
        raise ValueError(f"key contains NUL: {text!r}")
    return raw + b"\x00"


def _element(key: str, value) -> bytes:
    name = _cstring(key)
    if isinstance(value, bool):                    # before int: bool is an int in Python
        return b"\x08" + name + (b"\x01" if value else b"\x00")
    if isinstance(value, int):
        if INT32[0] <= value <= INT32[1] and key not in INT64_KEYS:
            return b"\x10" + name + struct.pack("<i", value)
        return b"\x12" + name + struct.pack("<q", value)
    if isinstance(value, float):
        return b"\x01" + name + struct.pack("<d", value)
    if isinstance(value, str):
        raw = value.encode("utf-8") + b"\x00"
        return b"\x02" + name + struct.pack("<i", len(raw)) + raw
    if value is None:
        return b"\x0a" + name
    if isinstance(value, dict):
        return b"\x03" + name + encode(value)
    if isinstance(value, (list, tuple)):
        return b"\x04" + name + encode({str(i): v for i, v in enumerate(value)})
    raise TypeError(f"can't encode {type(value).__name__} at {key!r}")


def encode(doc: dict) -> bytes:
    body = b"".join(_element(k, v) for k, v in doc.items())
    return struct.pack("<i", len(body) + 5) + body + b"\x00"


def decode(data: bytes) -> dict:
    doc, end = _document(data, 0)
    if end != len(data):
        raise ValueError(f"{len(data) - end} trailing bytes")
    return doc


def _document(data: bytes, pos: int, array: bool = False):
    size = struct.unpack_from("<i", data, pos)[0]
    end, pos, out = pos + size, pos + 4, {}
    while data[pos] != 0:
        kind = data[pos]
        nul = data.index(b"\x00", pos + 1)
        key, pos = data[pos + 1:nul].decode("utf-8"), nul + 1
        if kind == 0x01:
            value, pos = struct.unpack_from("<d", data, pos)[0], pos + 8
        elif kind == 0x02:
            n = struct.unpack_from("<i", data, pos)[0]
            value, pos = data[pos + 4:pos + 3 + n].decode("utf-8"), pos + 4 + n
        elif kind in (0x03, 0x04):
            value, pos = _document(data, pos, kind == 0x04)
        elif kind == 0x08:
            value, pos = data[pos] == 1, pos + 1
        elif kind == 0x0a:
            value = None
        elif kind == 0x10:
            value, pos = struct.unpack_from("<i", data, pos)[0], pos + 4
        elif kind == 0x12:
            value, pos = struct.unpack_from("<q", data, pos)[0], pos + 8
        else:
            raise ValueError(f"unsupported BSON type 0x{kind:02x} at {key!r}")
        out[key] = value
    if pos + 1 != end:
        raise ValueError("document size doesn't match its contents")
    return (list(out.values()) if array else out), end
