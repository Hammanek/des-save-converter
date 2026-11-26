"""Safe conversion of decrypted Demon's Souls saves for KytyPS5."""

from dataclasses import dataclass
import struct


class ConversionError(Exception):
    """A save cannot be safely converted."""


@dataclass(frozen=True)
class Character:
    name: str
    class_id: int
    class_name: str
    soul_level: int


CLASSES = {
    0: "Soldier",
    1: "Knight",
    2: "Hunter",
    3: "Priest",
    4: "Magician",
    5: "Wanderer",
    6: "Barbarian",
    7: "Thief",
    8: "Temple Knight",
    9: "Royalty",
}

CHARACTER_FIELDS = {
    "name": (0x324FEFCE, 0x0D),
    "class": (0x45B54344, 0x08),
    "vitality": (0xF059AB80, 0x08),
    "intelligence": (0x14795A91, 0x08),
    "endurance": (0xD02FD40F, 0x08),
    "strength": (0x5078FC63, 0x08),
    "dexterity": (0xA144D982, 0x08),
    "magic": (0xB06E4ED9, 0x08),
    "faith": (0xD6A72566, 0x08),
    "luck": (0x7B664AD3, 0x08),
}
STATS = (
    "vitality", "intelligence", "endurance", "strength",
    "dexterity", "magic", "faith", "luck",
)
FIXED_SIZES = {
    0x02: 1, 0x03: 2, 0x04: 4, 0x06: 1,
    0x08: 4, 0x0A: 4, 0x0C: 1, 0x0F: 16,
}
BLOB_KEYS = {
    0x522AD995, 0x0AF4946A, 0x78A5C2D7, 0xB98A1BFF,
    0xE56C5A97, 0x2B87B29A, 0x94A8D348, 0x6D87F588,
}


def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def validate_usr_data(data: bytes) -> None:
    if len(data) < 16:
        raise ConversionError("USR-DATA is too short to contain a valid header.")
    version, stored_checksum, payload_size, marker = struct.unpack_from("<IIII", data)
    if version != 7:
        raise ConversionError(f"Unsupported USR-DATA version {version}; expected 7.")
    if marker != 1:
        raise ConversionError(f"Invalid USR-DATA marker {marker}; expected 1.")
    if payload_size != len(data) - 16:
        raise ConversionError("USR-DATA payload size does not match the file length.")
    if stored_checksum != fnv1a32(data[16:]):
        raise ConversionError("USR-DATA checksum mismatch; the file is corrupt or edited.")


def _read_varint(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if position >= len(data) or shift > 35:
            raise ConversionError("Truncated or oversized varint in USR-DATA.")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, position
        shift += 7


def _iter_fields(data: bytes):
    position = 16
    while position < len(data):
        if position + 5 > len(data):
            raise ConversionError(f"Truncated field header at offset 0x{position:X}.")
        key, field_type = struct.unpack_from("<IB", data, position)
        start = position
        position += 5
        value_position = position
        if field_type in FIXED_SIZES:
            size = FIXED_SIZES[field_type]
        elif field_type == 0x0D:
            if position >= len(data):
                raise ConversionError(f"Truncated string at offset 0x{start:X}.")
            size = 1 + data[position]
            value_position += 1
        elif field_type == 0x0E:
            size, after_varint = _read_varint(data, position)
            position = after_varint
            if key not in BLOB_KEYS:
                yield key, field_type, b"", start
                continue
        else:
            raise ConversionError(
                f"Unknown field type 0x{field_type:02X} at offset 0x{start:X}."
            )
        end = position + size
        if end > len(data):
            raise ConversionError(f"Truncated field value at offset 0x{start:X}.")
        yield key, field_type, data[value_position:end], start
        position = end


def read_character(data: bytes) -> Character:
    validate_usr_data(data)
    wanted = {signature: name for name, signature in CHARACTER_FIELDS.items()}
    values = {}
    for key, field_type, raw, _offset in _iter_fields(data):
        name = wanted.get((key, field_type))
        if name is not None and name not in values:
            values[name] = raw

    missing = [name for name in CHARACTER_FIELDS if name not in values]
    if missing:
        raise ConversionError(f"Required character field is missing: {missing[0]}.")

    try:
        name = values["name"].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConversionError("Character name is not valid UTF-8.") from error
    if not name:
        raise ConversionError("Character name is empty.")

    class_id = int.from_bytes(values["class"], "little")
    if class_id not in CLASSES:
        raise ConversionError(f"Unknown character class {class_id}.")
    stats = [int.from_bytes(values[stat], "little") for stat in STATS]
    soul_level = sum(stats) - 80
    if soul_level < 1:
        raise ConversionError(f"Implausible Soul Level {soul_level}; character stats are invalid.")
    return Character(name, class_id, CLASSES[class_id], soul_level)
