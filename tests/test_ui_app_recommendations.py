"""Execute production Java methods with small platform boundaries replaced for the JVM."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "launcher-ui/app/src/io/cleanyourtv/ui/Recs.java"
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")

def method(source, signature):
    start = source.index(signature)
    end = source.index("\n    }", start) + len("\n    }")
    return source[start:end]

class FeatureTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_behavior(self):
        source = SOURCE.read_text(encoding="utf-8")
        production = (method(source, "    static final class Pick {") + method(source, "    static List<Pick> forApp("))
        program = """import java.util.*;
class FeatureCheck {
""" + production + """
    static Pick pick(String title, String app) {
        Pick p = new Pick(); p.title = title; p.pkg = app; return p;
    }
    public static void main(String[] args) {
        Pick n1 = pick("Netflix one", "netflix");
        Pick a = pick("Apple", "apple");
        Pick n2 = pick("Netflix two", "netflix");
        Pick unknown = pick("Unknown", null);
        List<Pick> input = Arrays.asList(n1, a, n2, unknown);
        List<Pick> netflix = forApp(input, "netflix");
        if (!netflix.equals(Arrays.asList(n1, n2))) throw new AssertionError("wrong app or order");
        if (!forApp(input, "apple").equals(Arrays.asList(a))) throw new AssertionError("apple missing");
        if (!forApp(input, "youtube").isEmpty()) throw new AssertionError("invented app picks");
        if (!forApp(input, null).isEmpty()) throw new AssertionError("null app matched");
        if (!forApp(input, "").isEmpty()) throw new AssertionError("empty app matched");
        if (!forApp(Collections.emptyList(), "netflix").isEmpty()) throw new AssertionError("empty input");
        netflix.clear();
        if (input.size() != 4) throw new AssertionError("input list was modified");
    }
}
"""
        with tempfile.TemporaryDirectory() as folder:
            check = Path(folder) / "FeatureCheck.java"
            check.write_text(program, encoding="utf-8")
            result = subprocess.run([JAVA, check], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
