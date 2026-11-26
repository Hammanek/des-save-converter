import struct
import unittest

from des_save_converter import ConversionError, fnv1a32, read_character, validate_usr_data


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


if __name__ == "__main__":
    unittest.main()
