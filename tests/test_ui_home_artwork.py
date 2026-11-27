"""Exercise the production home artwork queue/cache with deterministic workers and a real HTTP download race."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui"
JAVA_HOME = os.getenv("JAVA_HOME")
JAVA = str(Path(JAVA_HOME) / "bin/java") if JAVA_HOME else shutil.which("java")
JAVAC = str(Path(JAVA_HOME) / "bin/javac") if JAVA_HOME else shutil.which("javac")


def method(source, signature):
    start = source.index(signature)
    depth = 0
    for end in range(source.index("{", start), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(signature)


@unittest.skipUnless(JAVA and JAVAC, "JDK 17 required")
class HomeArtworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.folder = Path(cls.tmp.name)
        source = (SRC / "Recs.java").read_text()
        fields = source[source.index("    private final Map<String, Backdrop> images ="):
                        source.index("    private final java.util.Set<String> asked =")]
        methods = "\n".join(method(source, signature) for signature in (
            "    Backdrop backdrop(", "    void prepareImages(", "    private void startImages(",
            "    private void pruneImages(", "    private void loadImage(", "    void trim(",
            "    private void download(", "    private File imageFile(", "    private static void prune("))
        program = (ROOT / "tests/home_artwork/HomeArtworkCheck.java").read_text()
        methods = methods.replace("private void download(", "private void actualDownload(")
        program = program.replace("/* FIELDS */", fields).replace("/* METHODS */", methods)
        program = program.replace("/* BYTES */", method((SRC / "Backdrop.java").read_text(), "    long bytes("))
        target = cls.folder / "HomeArtworkCheck.java"
        target.write_text(program)
        result = subprocess.run([JAVAC, str(target)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def check(self, scenario):
        result = subprocess.run([JAVA, "-cp", str(self.folder), "HomeArtworkCheck", scenario],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_visible_first_and_nine_card_window(self):
        self.check("priority")

    def test_fast_switch_drops_stale_work(self):
        self.check("switch")

    def test_recent_service_page_stays_ready(self):
        self.check("recent")

    def test_prefetch_respects_memory_budget_and_does_not_churn(self):
        self.check("budget")

    def test_failed_visible_image_has_retry_delay(self):
        self.check("failure")

    def test_evicted_prefetch_is_not_treated_as_a_download_failure(self):
        self.check("pressure")

    def test_stale_running_result_is_not_prepared(self):
        self.check("stale")

    def test_pause_and_memory_trim_drop_queued_work(self):
        self.check("trim")

    def test_parallel_downloads_publish_complete_files(self):
        self.check("download")
