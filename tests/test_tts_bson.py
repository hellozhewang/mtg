"""scripts/tts_bson.py: the save format of a TTS Workshop upload."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tts_bson

SAVE = {"SaveName": "Cactuar π", "EpochTime": 1784846674, "Gravity": 0.5, "PlayArea": 1.0,
        "Note": None, "Locked": True, "Big": 2**40,
        "ObjectStates": [{"GUID": "c4c7a1", "OwnerSteamID": 0, "Transform": {"posX": -48.2, "rotY": 180.0},
                          "Tags": ["a", "b"], "Hands": False}]}


class BsonTests(unittest.TestCase):
    def test_round_trip_keeps_values_and_types(self):
        data = tts_bson.encode(SAVE)
        self.assertEqual(struct.unpack_from("<i", data)[0], len(data))
        back = tts_bson.decode(data)
        self.assertEqual(back, SAVE)
        self.assertIsInstance(back["PlayArea"], float)            # 1.0 stays a double
        self.assertEqual(tts_bson.encode(back), data)

    def test_tts_types(self):
        data = tts_bson.encode(SAVE)
        self.assertIn(b"\x10EpochTime\x00", data)                 # whole numbers: int32
        self.assertIn(b"\x12Big\x00", data)                       # too big: int64
        self.assertIn(b"\x12OwnerSteamID\x00" + b"\x00" * 8, data)  # a C# long, even at 0
        self.assertIn(b"\x01PlayArea\x00", data)                  # doubles
        self.assertIn(b"\x04Tags\x00", data)                      # arrays
        self.assertIn(b"\x0aNote\x00", data)                      # null

    def test_json_from_a_build_encodes_like_the_save(self):
        via_json = json.loads(json.dumps(SAVE))
        self.assertEqual(tts_bson.encode(via_json), tts_bson.encode(SAVE))


if __name__ == "__main__":
    unittest.main()
