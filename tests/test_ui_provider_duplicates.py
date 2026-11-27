"""Run subscription selection against TMDB-style offers and installed-app mappings."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1]
          / "launcher-ui/app/src/io/cleanyourtv/ui/DetailActivity.java")
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")


class ProviderDuplicatesTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_prefer_canonical_subscription_only_for_the_same_installed_app(self):
        source = SOURCE.read_text(encoding="utf-8")
        methods = source[source.index("    static String[] firstApp("):
                         source.index("    private TvUi.Flow whereLine;")]
        program = """
import java.util.*;

class ProviderDuplicatesCheck {
    static class Context {}
    static class JSONObject {
        final Map<String, Object> values = new LinkedHashMap<>();
        JSONObject put(String key, Object value) { values.put(key, value); return this; }
        JSONArray optJSONArray(String key) { return (JSONArray) values.get(key); }
        String optString(String key) { return (String) values.get(key); }
        int optInt(String key) { return (Integer) values.get(key); }
    }
    static class JSONArray {
        final List<JSONObject> values = new ArrayList<>();
        JSONArray put(JSONObject value) { values.add(value); return this; }
        int length() { return values.size(); }
        JSONObject optJSONObject(int index) { return values.get(index); }
    }
    static class Providers {
        static final Map<Integer, String> apps = new HashMap<>();
        static String app(Context c, int id, String name) { return apps.get(id); }
    }
""" + methods + """
    static JSONObject region(String... names) {
        JSONArray offers = new JSONArray();
        Providers.apps.clear();
        for (int i = 0; i < names.length; i++) {
            offers.put(new JSONObject().put("provider_id", i).put("provider_name", names[i]));
            Providers.apps.put(i, "same.app");
        }
        return new JSONObject().put("flatrate", offers);
    }
    static void expect(String wanted, String actual) {
        if (!Objects.equals(wanted, actual)) throw new AssertionError(wanted + " != " + actual);
    }
    public static void main(String[] args) {
        Context c = new Context();
        JSONObject r = region("Netflix Standard with Ads", "Netflix");
        expect("Netflix", preferredSubscription(c, r, "Netflix Standard with Ads", "flatrate", "same.app"));
        expect("Netflix", firstApp(c, r)[1]);
        expect("Netflix", preferredSubscription(c, r, "Netflix with Ads", "ads", "same.app"));
        expect("Netflix with Ads", preferredSubscription(c, r, "Netflix with Ads", "rent", "same.app"));
        expect("Netflix with Ads", preferredSubscription(c, r, "Netflix with Ads", "buy", "same.app"));
        expect("Netflix with Ads", preferredSubscription(c, r, "Netflix with Ads", "flatrate", null));
        Providers.apps.put(1, "different.app");
        expect("Netflix Standard with Ads",
               preferredSubscription(c, r, "Netflix Standard with Ads", "flatrate", "same.app"));
        expect("Netflix Standard with Ads", firstApp(c, r)[1]);
        r = region("Netflix with Ads");
        expect("Netflix with Ads", firstApp(c, r)[1]);
        r = region("Apple TV Plus", "Apple TV+", "Apple TV");
        expect("Apple TV", preferredSubscription(c, r, "Apple TV Plus", "flatrate", "same.app"));
        expect("Apple TV", preferredSubscription(c, r, "Apple TV+", "flatrate", "same.app"));
        expect("Apple TV", preferredSubscription(c, r, "Apple TV Amazon Channel", "flatrate", "same.app"));
        r = region("Amazon Prime Video");
        expect("Amazon Prime Video", firstApp(c, r)[1]);
        expect("Amazon Prime Video",
               preferredSubscription(c, r, "Amazon Prime Video", "flatrate", "same.app"));
        Providers.apps.clear();
        if (firstApp(c, r) != null) throw new AssertionError("missing app selected");
        if (firstApp(c, null) != null) throw new AssertionError("missing offers selected");
    }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            check = Path(directory) / "ProviderDuplicatesCheck.java"
            check.write_text(program, encoding="utf-8")
            subprocess.run([JAVA, check], check=True, capture_output=True, text=True, timeout=30)
