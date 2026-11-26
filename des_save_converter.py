"""Safe conversion of decrypted Demon's Souls saves from KytyPS5 to native PC."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import struct
import sys
import tempfile


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
    0xFB0FAEB2, 0x739273B8, 0x639244AA,
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
    if any(stat < 1 or stat > 99 for stat in stats):
        raise ConversionError("Character statistics must be between 1 and 99.")
    soul_level = sum(stats) - 80
    if soul_level < 1 or soul_level > 712:
        raise ConversionError(f"Implausible Soul Level {soul_level}; character stats are invalid.")
    return Character(name, class_id, CLASSES[class_id], soul_level)


PLAYER_PROFILE = "SAVEDATA0PlayerProfile0"
OPTIONS_PROFILE = "SAVEDATA0OptionsProfile0"
PROFILES = (PLAYER_PROFILE, OPTIONS_PROFILE)


def _required_file(root: Path, relative: str, label: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ConversionError(f"Required {label} file is missing: {path}")
    return path


def _read_input_profile(root: Path, profile: str) -> bytes:
    path = _required_file(root, f"{profile}/USR-DATA", "input")
    try:
        data = path.read_bytes()
        validate_usr_data(data)
        for _field in _iter_fields(data):
            pass
    except OSError as error:
        raise ConversionError(f"Could not read {path}: {error}") from error
    except ConversionError as error:
        raise ConversionError(f"{profile}/USR-DATA: {error}") from error
    return data


def _reference_param(reference: Path, profile: str) -> bytes:
    relative = f"{profile}/sce_sys/param.bin"
    path = _required_file(reference, relative, "reference")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ConversionError(f"Could not read {path}: {error}") from error
    if len(data) != 0x530 or not data.startswith(b"Demon's Souls\0"):
        raise ConversionError(f"Unsupported reference param.bin format: {path}")
    return data


def _make_player_param(template: bytes, character: Character) -> bytes:
    subtitle = f"Player - {character.name}".encode("utf-8")
    detail = f"Soul Level {character.soul_level} {character.class_name}".encode("utf-8")
    if len(subtitle) > 0x7F or len(detail) > 0x3FF:
        raise ConversionError("Character details are too long for param.bin.")
    result = bytearray(template)
    result[0x80:0x100] = bytes(0x80)
    result[0x100:0x500] = bytes(0x400)
    result[0x80:0x80 + len(subtitle)] = subtitle
    result[0x100:0x100 + len(detail)] = detail
    return bytes(result)


def convert_save(input_dir: Path, reference_dir: Path, output_dir: Path) -> Character:
    input_dir, reference_dir, output_dir = map(Path, (input_dir, reference_dir, output_dir))
    source_paths = {path.resolve() for path in (input_dir, reference_dir)}
    resolved_output = output_dir.resolve()
    if any(resolved_output.is_relative_to(source) for source in source_paths):
        raise ConversionError("The output directory cannot overlap input or reference.")
    if output_dir.exists() and (
        not output_dir.is_dir() or any(output_dir.iterdir())
    ):
        raise ConversionError(f"The output directory is not empty: {output_dir}")

    input_data = {profile: _read_input_profile(input_dir, profile) for profile in PROFILES}
    character = read_character(input_data[PLAYER_PROFILE])
    reference_params = {profile: _reference_param(reference_dir, profile) for profile in PROFILES}
    player_param = _make_player_param(reference_params[PLAYER_PROFILE], character)
    for profile in PROFILES:
        for filename in ("blocks", "icon0.png"):
            _required_file(reference_dir, f"{profile}/sce_sys/{filename}", "reference")

    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f"{output_dir.name}.tmp-", dir=output_dir.parent))
    except OSError as error:
        raise ConversionError(f"Could not prepare output directory {output_dir}: {error}") from error
    try:
        for profile in PROFILES:
            (staging / profile).mkdir()
            shutil.copy2(input_dir / profile / "USR-DATA", staging / profile / "USR-DATA")
            (staging / profile / "sce_sys").mkdir()
            for filename in ("blocks", "icon0.png"):
                source = reference_dir / profile / "sce_sys" / filename
                shutil.copy2(source, staging / profile / "sce_sys" / filename)
        shutil.copy2(
            reference_dir / OPTIONS_PROFILE / "sce_sys" / "param.bin",
            staging / OPTIONS_PROFILE / "sce_sys" / "param.bin",
        )
        (staging / PLAYER_PROFILE / "sce_sys" / "param.bin").write_bytes(player_param)

        for profile in PROFILES:
            converted = (staging / profile / "USR-DATA").read_bytes()
            if converted != input_data[profile]:
                raise ConversionError(f"Output verification failed for {profile}/USR-DATA.")
            validate_usr_data(converted)
        if output_dir.exists():
            if any(output_dir.iterdir()):
                raise ConversionError(f"The output directory became non-empty: {output_dir}")
            output_dir.rmdir()
        staging.replace(output_dir)
    except Exception as error:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(error, ConversionError):
            raise
        raise ConversionError(f"Conversion failed: {error}") from error
    return character


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Incomplete save directory")
    parser.add_argument("--reference", required=True, type=Path, help="Known-good save directory")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory")
    args = parser.parse_args()
    try:
        character = convert_save(args.input, args.reference, args.output)
    except (ConversionError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(
        f"Converted {character.name} ({character.class_name}, Soul Level "
        f"{character.soul_level}) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
