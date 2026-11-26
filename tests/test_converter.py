import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from des_save_converter import (
    ConversionError,
    convert_save,
    fnv1a32,
    read_character,
    validate_usr_data,
)


FIELDS = {
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


def checksum(data):
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def make_usr(body, *, version=7, marker=1, declared_size=None):
    size = len(body) if declared_size is None else declared_size
    return struct.pack("<IIII", version, checksum(body), size, marker) + body


def u32_field(name, value):
    key, field_type = FIELDS[name]
    return struct.pack("<IBI", key, field_type, value)


def string_field(name, value, declared_length=None):
    key, field_type = FIELDS[name]
    encoded = value.encode("utf-8")
    length = len(encoded) if declared_length is None else declared_length
    return struct.pack("<IBB", key, field_type, length) + encoded


def make_player(name="mobus", class_id=1, stats=(14, 13, 13, 16, 11, 11, 12, 8)):
    stat_names = (
        "vitality", "intelligence", "endurance", "strength",
        "dexterity", "magic", "faith", "luck",
    )
    body = string_field("name", name)
    body += u32_field("class", class_id)
    body += b"".join(u32_field(field, value) for field, value in zip(stat_names, stats))
    return make_usr(body)


class ChecksumTests(unittest.TestCase):
    def test_fnv1a_known_values(self):
        self.assertEqual(fnv1a32(b""), 0x811C9DC5)
        self.assertEqual(fnv1a32(b"a"), 0xE40C292C)


class HeaderValidationTests(unittest.TestCase):
    def test_valid_header_is_accepted(self):
        self.assertIsNone(validate_usr_data(make_usr(b"test")))

    def test_invalid_header_fields_are_rejected(self):
        valid = make_usr(b"test")
        mutations = {
            "version": make_usr(b"test", version=6),
            "marker": make_usr(b"test", marker=0),
            "declared size": make_usr(b"test", declared_size=3),
            "checksum": valid[:4] + b"\0\0\0\0" + valid[8:],
            "short header": b"\x07\0",
        }
        for label, data in mutations.items():
            with self.subTest(label=label), self.assertRaises(ConversionError):
                validate_usr_data(data)


class CharacterTests(unittest.TestCase):
    def test_reads_mobus_knight_level_18(self):
        character = read_character(make_player())
        self.assertEqual(character.name, "mobus")
        self.assertEqual(character.class_id, 1)
        self.assertEqual(character.class_name, "Knight")
        self.assertEqual(character.soul_level, 18)

    def test_reads_jirka_soldier_level_6(self):
        character = read_character(make_player(
            name="Jirka", class_id=0, stats=(14, 9, 12, 12, 11, 8, 10, 10),
        ))
        self.assertEqual(character.name, "Jirka")
        self.assertEqual(character.class_name, "Soldier")
        self.assertEqual(character.soul_level, 6)

    def test_truncated_name_is_rejected(self):
        data = make_usr(string_field("name", "test", declared_length=16))
        with self.assertRaisesRegex(ConversionError, "(?i)truncated"):
            read_character(data)

    def test_unknown_class_is_rejected(self):
        with self.assertRaisesRegex(ConversionError, "class"):
            read_character(make_player(class_id=99))

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ConversionError, "class"):
            read_character(make_usr(string_field("name", "mobus")))

    def test_unknown_field_type_is_rejected(self):
        data = make_usr(struct.pack("<IB", 0x12345678, 0xFF) + b"\0" * 9)
        with self.assertRaisesRegex(ConversionError, "field type"):
            read_character(data)

    def test_known_blob_fields_do_not_desynchronize_character_parser(self):
        blobs = b"".join(
            struct.pack("<IBB", key, 0x0E, 4) + b"blob"
            for key in (0xFB0FAEB2, 0x739273B8, 0x639244AA)
        )
        data = make_usr(blobs + make_player()[16:])
        self.assertEqual(read_character(data).name, "mobus")

    def test_statistics_above_99_are_rejected(self):
        for value in (100, 0xFFFFFFFF):
            with self.subTest(value=value), self.assertRaisesRegex(ConversionError, "statistics"):
                read_character(make_player(stats=(value, 13, 13, 16, 11, 11, 12, 8)))

    def test_soul_level_712_is_accepted(self):
        self.assertEqual(read_character(make_player(stats=(99,) * 8)).soul_level, 712)


PROFILES = ("SAVEDATA0PlayerProfile0", "SAVEDATA0OptionsProfile0")


def make_param():
    data = bytearray(0x530)
    title = b"Demon's Souls\0"
    data[:len(title)] = title
    return bytes(data)


def populate_input(root):
    for profile in PROFILES:
        (root / profile).mkdir(parents=True)
    (root / PROFILES[0] / "USR-DATA").write_bytes(make_player())
    valid_options = make_usr(struct.pack("<IBI", 0x12345678, 0x08, 1))
    (root / PROFILES[1] / "USR-DATA").write_bytes(valid_options)


def populate_reference(root):
    populate_input(root)
    for index, profile in enumerate(PROFILES):
        sys_dir = root / profile / "sce_sys"
        sys_dir.mkdir()
        (sys_dir / "param.bin").write_bytes(make_param())
        (sys_dir / "icon0.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index]))
        (sys_dir / "blocks").write_bytes(struct.pack("<Q", 96 if index == 0 else 48))


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input = self.root / "input"
        self.reference = self.root / "reference"
        populate_input(self.input)
        populate_reference(self.reference)
        self.output = self.root / "output"

    def tearDown(self):
        self.temporary.cleanup()

    def test_creates_complete_save_without_modifying_game_data(self):
        character = convert_save(self.input, self.reference, self.output)
        expected = {
            Path(profile) / name
            for profile in PROFILES
            for name in ("USR-DATA", "sce_sys/blocks", "sce_sys/icon0.png", "sce_sys/param.bin")
        }
        actual = {
            path.relative_to(self.output)
            for path in self.output.rglob("*") if path.is_file()
        }
        self.assertEqual(actual, expected)
        self.assertEqual((character.name, character.class_name, character.soul_level), ("mobus", "Knight", 18))
        for profile in PROFILES:
            original = (self.input / profile / "USR-DATA").read_bytes()
            converted = (self.output / profile / "USR-DATA").read_bytes()
            self.assertEqual(hashlib.sha256(converted).digest(), hashlib.sha256(original).digest())
            for filename in ("blocks", "icon0.png"):
                self.assertEqual(
                    (self.output / profile / "sce_sys" / filename).read_bytes(),
                    (self.reference / profile / "sce_sys" / filename).read_bytes(),
                )
        self.assertEqual(
            (self.output / PROFILES[1] / "sce_sys" / "param.bin").read_bytes(),
            (self.reference / PROFILES[1] / "sce_sys" / "param.bin").read_bytes(),
        )

    def test_player_param_contains_only_converted_character_details(self):
        convert_save(self.input, self.reference, self.output)
        param = (self.output / PROFILES[0] / "sce_sys" / "param.bin").read_bytes()
        self.assertEqual(len(param), 0x530)
        self.assertEqual(param[0x80:0x100].split(b"\0", 1)[0], b"Player - mobus")
        self.assertEqual(param[0x100:0x500].split(b"\0", 1)[0], b"Soul Level 18 Knight")

    def test_missing_input_is_rejected_without_output(self):
        (self.input / PROFILES[0] / "USR-DATA").unlink()
        with self.assertRaisesRegex(ConversionError, "USR-DATA"):
            convert_save(self.input, self.reference, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_reference_asset_is_rejected_without_output(self):
        (self.reference / PROFILES[0] / "sce_sys" / "icon0.png").unlink()
        with self.assertRaisesRegex(ConversionError, "reference"):
            convert_save(self.input, self.reference, self.output)
        self.assertFalse(self.output.exists())

    def test_unsupported_reference_param_is_rejected(self):
        param_path = self.reference / PROFILES[0] / "sce_sys" / "param.bin"
        param_path.write_bytes(b"not a supported param")
        with self.assertRaisesRegex(ConversionError, "param.bin"):
            convert_save(self.input, self.reference, self.output)
        self.assertFalse(self.output.exists())

    def test_structurally_invalid_options_are_rejected_without_output(self):
        options = self.input / PROFILES[1] / "USR-DATA"
        options.write_bytes(make_usr(b"options"))
        with self.assertRaisesRegex(ConversionError, PROFILES[1]):
            convert_save(self.input, self.reference, self.output)
        self.assertFalse(self.output.exists())

    def test_output_nested_under_input_or_reference_is_rejected(self):
        for source in (self.input, self.reference):
            nested_output = source / "converted"
            with self.subTest(source=source.name):
                with self.assertRaisesRegex(ConversionError, "overlap"):
                    convert_save(self.input, self.reference, nested_output)
                self.assertFalse(nested_output.exists())

    def test_nonempty_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("important", encoding="utf-8")
        with self.assertRaisesRegex(ConversionError, "output"):
            convert_save(self.input, self.reference, self.output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "important")

    def test_copy_failure_leaves_no_output_or_staging_directory(self):
        with patch("des_save_converter.shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ConversionError, "disk full"):
                convert_save(self.input, self.reference, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob("output.tmp-*")), [])


class CliTests(unittest.TestCase):
    def test_cli_converts_save_and_reports_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, reference = root / "input", root / "reference"
            populate_input(source)
            populate_reference(reference)
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "des_save_converter.py"),
                    "--input", str(source), "--reference", str(reference), "--output", str(root / "output"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mobus", result.stdout)
            self.assertIn("Knight", result.stdout)

    def test_cli_reports_destination_parent_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, reference = root / "input", root / "reference"
            populate_input(source)
            populate_reference(reference)
            blocking_file = root / "not-a-directory"
            blocking_file.write_text("keep", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "des_save_converter.py"),
                    "--input", str(source), "--reference", str(reference),
                    "--output", str(blocking_file / "output"),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(blocking_file.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
