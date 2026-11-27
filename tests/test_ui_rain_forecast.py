"""Execute production Java methods with small platform boundaries replaced for the JVM."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "launcher-ui/app/src/io/cleanyourtv/ui/HomeData.java"
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")

def method(source, signature):
    start = source.index(signature)
    end = source.index("\n    }", start) + len("\n    }")
    return source[start:end]

class FeatureTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_behavior(self):
        source = SOURCE.read_text(encoding="utf-8")
        production = (method(source, "    static int rainInHours(") + method(source, "    private static boolean isRain("))
        program = """import java.util.*;
class FeatureCheck {
    static final long HOUR = 3_600_000L, NOW = 48 * HOUR;
    static class Weather {
        int code;
        final List<Long> hours = new ArrayList<>();
        final List<Integer> hourCode = new ArrayList<>();
        Weather at(long time, int forecast) { hours.add(time); hourCode.add(forecast); return this; }
    }
""" + production + """
    static void check(int wanted, Weather w) {
        int actual = rainInHours(w, NOW);
        if (actual != wanted) throw new AssertionError(wanted + " != " + actual);
    }
    public static void main(String[] args) {
        check(-1, new Weather());
        Weather raining = new Weather(); raining.code = 61;
        check(0, raining);
        check(2, new Weather().at(NOW - HOUR, 61).at(NOW + 2 * HOUR, 61));
        check(-1, new Weather().at(NOW - HOUR, 61).at(NOW, 80));
        check(1, new Weather().at(NOW - HOUR, 95).at(NOW + HOUR, 51));
        check(-1, new Weather().at(NOW + HOUR, 71).at(NOW + 2 * HOUR, 75));
        check(3, new Weather().at(NOW + HOUR, 0).at(NOW + 3 * HOUR, 95));
        Weather shortCodes = new Weather(); shortCodes.hours.add(NOW + HOUR);
        check(-1, shortCodes);
        Weather shortHours = new Weather(); shortHours.hourCode.add(61);
        check(-1, shortHours);
    }
}
"""
        with tempfile.TemporaryDirectory() as folder:
            check = Path(folder) / "FeatureCheck.java"
            check.write_text(program, encoding="utf-8")
            result = subprocess.run([JAVA, check], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
