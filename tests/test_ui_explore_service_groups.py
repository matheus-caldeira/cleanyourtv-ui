"""Execute production Java methods with small platform boundaries replaced for the JVM."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "launcher-ui/app/src/io/cleanyourtv/ui/ExploreActivity.java"
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")

def method(source, signature):
    start = source.index(signature)
    end = source.index("\n    }", start) + len("\n    }")
    return source[start:end]

class FeatureTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_behavior(self):
        source = SOURCE.read_text(encoding="utf-8")
        production = (method(source, "    private static final class Service {")
                + method(source, "    private List<String> order() {")
                + method(source, "    private int menuGroup(")
                + method(source, "    private Service service(")
                + method(source, "    private void move("))
        program = """import java.util.*;
class FeatureCheck {
    static final String SERVICE = "service:";
    static final String[] MOVABLE = {"movie", "tv", "categories"};
    List<Service> services;
    List<String> stored = new ArrayList<>();
    static class JSONObject {
        Iterator<String> keys() { return Arrays.asList("f:comedy").iterator(); }
    }
    JSONObject saved() { return new JSONObject(); }
    List<String> readList(String key) { return new ArrayList<>(stored); }
    void writeList(String key, List<String> value) { stored = new ArrayList<>(value); }
""" + production + """
    static Service app(String key, boolean installed) { return new Service(key, key, "", "", installed); }
    static void equal(Object wanted, Object actual) {
        if (!Objects.equals(wanted, actual)) throw new AssertionError(wanted + " != " + actual);
    }
    public static void main(String[] args) {
        FeatureCheck menu = new FeatureCheck();
        menu.services = Arrays.asList(app("offline", false), app("netflix", true),
                                     app("apple", true), app("offline2", false));
        menu.stored = Arrays.asList("service:offline", "f:comedy", "movie",
                                   "service:apple", "tv", "service:netflix", "obsolete");
        List<String> wanted = Arrays.asList("f:comedy", "movie", "tv", "categories",
                                          "service:apple", "service:netflix", "service:offline", "service:offline2");
        equal(wanted, menu.order());
        menu.move("service:apple", -1);
        equal(wanted, menu.order());
        menu.move("service:apple", 1);
        equal(Arrays.asList("f:comedy", "movie", "tv", "categories",
                            "service:netflix", "service:apple", "service:offline", "service:offline2"), menu.order());
        List<String> before = menu.order();
        menu.move("categories", 1);
        menu.move("service:offline", -1);
        menu.move("absent", 1);
        equal(before, menu.order());
        menu.services = Arrays.asList(app("apple", true), app("offline", true), app("netflix", false));
        equal(Arrays.asList("f:comedy", "movie", "tv", "categories",
                            "service:apple", "service:offline", "service:netflix"), menu.order());
        menu.services = null;
        equal(Arrays.asList("f:comedy", "movie", "tv", "categories"), menu.order());
    }
}
"""
        with tempfile.TemporaryDirectory() as folder:
            check = Path(folder) / "FeatureCheck.java"
            check.write_text(program, encoding="utf-8")
            result = subprocess.run([JAVA, check], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
