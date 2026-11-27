"""Run the Where to watch filter and service matching with a fake installed-app list."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROVIDERS = (Path(__file__).resolve().parents[1]
             / "launcher-ui/app/src/io/cleanyourtv/ui/Providers.java")
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")


class WhereToWatchTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_only_official_apps_count_when_filter_is_on(self):
        source = PROVIDERS.read_text(encoding="utf-8")
        apps = source[source.index("    private static final String[][] APPS"):source.index("    private static List<Provider> cached")]
        lookup = source[source.index("    static String officialApp("):source.index("    static boolean off(")]
        program = """
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

class WhereToWatchCheck {
    static class Context {
        final Set<String> installed = new HashSet<>();
    }
    static class Prefs {
        static String provider(String id) { return "com.example.player"; }
    }
    static boolean installed(Context c, String pkg) { return c.installed.contains(pkg); }
""" + apps + lookup + """
    public static void main(String[] args) {
        Context tv = new Context();
        tv.installed.add("com.example.player");
        for (String service : new String[] {"Amazon Prime Video", "Disney+"}) {
            if (!"com.example.player".equals(app(tv, 1, service))) throw new AssertionError("missing replacement");
            if (!showInWhereToWatch(tv, service, false)) throw new AssertionError("filter off: " + service);
            if (showInWhereToWatch(tv, service, true)) throw new AssertionError("replacement counted: " + service);
        }
        tv.installed.add("com.amazon.amazonvideo.livingroom");
        if (!showInWhereToWatch(tv, "Amazon Prime Video", true)) throw new AssertionError("official app hidden");
        if (showInWhereToWatch(tv, "Disney+", true)) throw new AssertionError("other official app missing");
    }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            check = Path(directory) / "WhereToWatchCheck.java"
            check.write_text(program, encoding="utf-8")
            subprocess.run([JAVA, check], check=True, capture_output=False, timeout=30)
