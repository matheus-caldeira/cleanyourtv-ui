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
        production = (method(source, "    private void startVoiceSearch() {")
                + method(source, "    @Override protected void onActivityResult("))
        program = """import java.util.*;
class FeatureCheck extends BaseActivity {
    static final int VOICE_SEARCH = 1, RESULT_OK = -1;
    static final String SEARCH = "search";
    String current = SEARCH;
    EditText searchField = new EditText();
    int submitted;
    Intent started;
    boolean googleAvailable, recognizerMissing;
    static class ActivityNotFoundException extends RuntimeException {}
    static class RecognizerIntent {
        static final String ACTION_RECOGNIZE_SPEECH = "recognize", EXTRA_LANGUAGE_MODEL = "model",
                LANGUAGE_MODEL_FREE_FORM = "free", EXTRA_MAX_RESULTS = "max",
                EXTRA_LANGUAGE = "lang", EXTRA_RESULTS = "results";
    }
    static class Intent {
        String action, pkg;
        final Map<String, Object> extras = new HashMap<>();
        Intent() {}
        Intent(String action) { this.action = action; }
        Intent(Intent other) { action = other.action; pkg = other.pkg; extras.putAll(other.extras); }
        Intent setPackage(String value) { pkg = value; return this; }
        Intent putExtra(String key, Object value) { extras.put(key, value); return this; }
        Object resolveActivity(FeatureCheck pm) { return pm.googleAvailable ? new Object() : null; }
        @SuppressWarnings("unchecked")
        ArrayList<String> getStringArrayListExtra(String key) { return (ArrayList<String>) extras.get(key); }
    }
    static class Ui { static Locale locale() { return Locale.forLanguageTag("uk"); } }
    static class R { static class string { static int voice_search_unavailable = 1; } }
    static class Strings { static String get(int key) { return "unavailable"; } }
    static class Toast {
        static final int LENGTH_SHORT = 0;
        static int shown;
        static Toast makeText(Object context, String message, int length) { return new Toast(); }
        void show() { shown++; }
    }
    static class EditText {
        String value = "before";
        int selection;
        void setText(String text) { value = text; }
        void setSelection(int at) { selection = at; }
    }
    FeatureCheck getPackageManager() { return this; }
    void startActivityForResult(Intent intent, int request) {
        if (recognizerMissing) throw new ActivityNotFoundException();
        if (request != VOICE_SEARCH) throw new AssertionError("wrong result request");
        started = intent;
    }
    void submitSearch() { submitted++; }
""" + production + """
    static Intent result(String... words) {
        return new Intent().putExtra(RecognizerIntent.EXTRA_RESULTS, new ArrayList<>(Arrays.asList(words)));
    }
    static void equal(Object wanted, Object actual) {
        if (!Objects.equals(wanted, actual)) throw new AssertionError(wanted + " != " + actual);
    }
    public static void main(String[] args) {
        FeatureCheck search = new FeatureCheck();
        search.startVoiceSearch();
        equal(null, search.started.pkg);
        equal("uk", search.started.extras.get(RecognizerIntent.EXTRA_LANGUAGE));
        equal(1, search.started.extras.get(RecognizerIntent.EXTRA_MAX_RESULTS));
        search.googleAvailable = true;
        search.startVoiceSearch();
        equal("com.google.android.tts", search.started.pkg);
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result("  planet earth  ", "other"));
        equal("planet earth", search.searchField.value);
        equal(12, search.searchField.selection);
        equal(1, search.submitted);
        search.onActivityResult(VOICE_SEARCH, 0, result("cancelled"));
        search.onActivityResult(2, RESULT_OK, result("other request"));
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, null);
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, new Intent());
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result());
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result((String) null));
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result("   "));
        equal("planet earth", search.searchField.value);
        equal(1, search.submitted);
        search.current = "movie";
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result("late result"));
        equal("planet earth", search.searchField.value);
        search.current = SEARCH;
        search.searchField = null;
        search.onActivityResult(VOICE_SEARCH, RESULT_OK, result("destroyed field"));
        equal(1, search.submitted);
        search.recognizerMissing = true;
        search.startVoiceSearch();
        equal(1, Toast.shown);
    }
}
class BaseActivity {
    protected void onActivityResult(int request, int result, FeatureCheck.Intent data) {}
}
"""
        with tempfile.TemporaryDirectory() as folder:
            check = Path(folder) / "FeatureCheck.java"
            check.write_text(program, encoding="utf-8")
            result = subprocess.run([JAVA, check], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
