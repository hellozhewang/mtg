"""Compare the embedded Lua matcher with Python regex on generated expressions."""
import itertools
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import unittest


@unittest.skipUnless(shutil.which("lua"), "Lua is not installed")
class RegexCompatibility(unittest.TestCase):
    def test_generated_patterns_match_reference_engine(self):
        rng = random.Random(41)
        atoms = ["a", "b", ".", r"\d", r"\D", r"\w", r"\W", r"\s", r"\S",
                 "[ab]", "[^a]", "[a-c]", r"\b", r"\B", "^", "$"]

        def pattern(depth=0):
            if depth >= 2 or rng.random() < .45:
                return rng.choice(atoms)
            kind = rng.randrange(3)
            if kind == 0:
                return "(?:" + pattern(depth + 1) + "|" + pattern(depth + 1) + ")"
            if kind == 1:
                return pattern(depth + 1) + pattern(depth + 1)
            return "(?:" + pattern(depth + 1) + ")" + rng.choice(["*", "+", "?", "{0,2}", "{1,3}"])

        patterns = list(dict.fromkeys(pattern() for _ in range(250)))
        texts = ["", "a\nb", "123", "a b", "!_"] + [
            "".join(chars) for length in range(1, 5)
            for chars in itertools.product("ab1 ", repeat=length)]
        lines = ['dofile("tts/cactuar_regex.lua")', 'local n=0']
        for expression in patterns:
            reference = re.compile(expression, re.MULTILINE | re.ASCII | re.IGNORECASE)
            lines.append("do local f,e=CZRegex.compile(" + json.dumps(expression) + "); assert(f,e)")
            for text in texts:
                # Before 3.14 Python special-cased \B on empty input; our matcher
                # treats it consistently as the complement of a word boundary.
                if not text and r"\B" in expression and sys.version_info < (3, 14):
                    continue
                expected = str(bool(reference.search(text))).lower()
                message = json.dumps("Mismatch " + repr((expression, text)))
                lines.append(f"assert(f({json.dumps(text)})=={expected},{message});n=n+1")
            lines.append("end")
        lines.append('print(n.." differential regex comparisons passed")')
        result = subprocess.run(["lua", "-"], input="\n".join(lines), text=True,
                                capture_output=True, timeout=45, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("comparisons passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
