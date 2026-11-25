"""Execute production Java methods with small platform boundaries replaced for the JVM."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "launcher-ui/app/src/io/cleanyourtv/ui/Click.java"
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")

def method(source, signature):
    start = source.index(signature)
    end = source.index("\n    }", start) + len("\n    }")
    return source[start:end]

class FeatureTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_behavior(self):
        source = SOURCE.read_text(encoding="utf-8")
        production = (method(source, "    void move() {") + method(source, "    void open() {"))
        prefs = (SOURCE.parent / "Prefs.java").read_text(encoding="utf-8")
        getter = next(line.strip() for line in prefs.splitlines() if "static boolean muteNavigationSounds()" in line)
        setter = next(line.strip() for line in prefs.splitlines() if "static void setMuteNavigationSounds(" in line)
        program = """import java.util.*;
class FeatureCheck {
    static class Prefs {
        static Boolean saved;
        static Prefs sp() { return new Prefs(); }
        boolean getBoolean(String key, boolean defaultValue) { return saved == null ? defaultValue : saved; }
        static void put(String key, boolean value) { saved = value; }
        static boolean muteNavigationSounds() { return sp().getBoolean("muteNavigationSounds", false); }
        static void setMuteNavigationSounds(boolean on) { put("muteNavigationSounds", on); }
    }
    static class SoundPool {
        final List<Integer> played = new ArrayList<>();
        int play(int sound, float left, float right, int priority, int loop, float rate) {
            played.add(sound); return 1;
        }
    }
    static class Handler {
        final List<Runnable> pending = new ArrayList<>();
        void post(Runnable work) { pending.add(work); }
        void drain() { new ArrayList<>(pending).forEach(Runnable::run); pending.clear(); }
    }
    SoundPool pool = new SoundPool();
    final Handler handler = new Handler();
    int move = 1, open = 2;
""" + production + """
    public static void main(String[] args) {
        FeatureCheck click = new FeatureCheck();
        click.move(); click.open();
        if (!click.pool.played.isEmpty()) throw new AssertionError("play on caller thread");
        click.handler.drain();
        if (!click.pool.played.equals(Arrays.asList(1, 2))) throw new AssertionError("sounds should default on");
        Prefs.setMuteNavigationSounds(true);
        click.move(); click.open();
        if (!click.handler.pending.isEmpty()) throw new AssertionError("muted work was queued");
        Prefs.setMuteNavigationSounds(false);
        click.move(); click.open();
        Prefs.setMuteNavigationSounds(true);
        click.handler.drain();
        if (click.pool.played.size() != 2) throw new AssertionError("queued sound escaped mute");
        Prefs.setMuteNavigationSounds(false);
        click.open(); click.handler.drain();
        if (!click.pool.played.equals(Arrays.asList(1, 2, 2))) throw new AssertionError("unmute failed");
        click.pool = null;
        click.move(); click.open(); click.handler.drain();
    }
}
"""
        program = program.replace('static boolean muteNavigationSounds() { return sp().getBoolean("muteNavigationSounds", false); }', getter)
        program = program.replace('static void setMuteNavigationSounds(boolean on) { put("muteNavigationSounds", on); }', setter)
        with tempfile.TemporaryDirectory() as folder:
            check = Path(folder) / "FeatureCheck.java"
            check.write_text(program, encoding="utf-8")
            result = subprocess.run([JAVA, check], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
