"""Run the FX pair validation and rate selection without Android or live exchange rates."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1]
          / "launcher-ui/app/src/io/cleanyourtv/ui/HomeData.java")
JAVA = Path(os.environ["JAVA_HOME"]) / "bin/java" if os.getenv("JAVA_HOME") else shutil.which("java")


class CurrencyPairsTest(unittest.TestCase):
    @unittest.skipUnless(JAVA, "JDK 17 required")
    def test_normalization_latest_publications_and_percentage_change(self):
        source = SOURCE.read_text(encoding="utf-8")
        normalization = source[source.index("    static String normalizeFxPair("):
                               source.index("    private static volatile int[] activeCoins;")]
        parsing = source[source.index("    private static FxRate parseFx("):
                         source.index("    private void refreshFx(")]
        program = """
import java.io.IOException;
import java.util.*;

class CurrencyPairsCheck {
    static class Ui {
        static Locale locale() { return Locale.US; }
    }
    static class JSONObject {
        final Map<String, Object> values = new HashMap<>();
        JSONObject put(String key, Object value) { values.put(key, value); return this; }
        String getString(String key) { return (String) values.get(key); }
        double getDouble(String key) { return ((Number) values.get(key)).doubleValue(); }
        double optDouble(String key, double fallback) {
            return values.containsKey(key) ? getDouble(key) : fallback;
        }
    }
    static class JSONArray {
        final List<JSONObject> values = new ArrayList<>();
        JSONArray put(JSONObject row) { values.add(row); return this; }
        int length() { return values.size(); }
        JSONObject getJSONObject(int index) { return values.get(index); }
    }
""" + normalization + parsing + """
    interface Task { void run() throws Exception; }
    static void invalid(Task task) throws Exception {
        try { task.run(); } catch (Exception expected) { return; }
        throw new AssertionError("invalid rate was accepted");
    }
    static void equal(Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) throw new AssertionError(expected + " != " + actual);
    }
    static void close(double expected, double actual) {
        if (!Double.isFinite(actual) || Math.abs(expected - actual) > 0.000001) {
            throw new AssertionError(expected + " != " + actual);
        }
    }
    static JSONObject rate(String date, double value) {
        return new JSONObject().put("base", "EUR").put("quote", "RON").put("date", date).put("rate", value);
    }
    public static void main(String[] args) throws Exception {
        equal("EUR/RON", normalizeFxPair(" eur / ron "));
        equal("USD/UAH", normalizeFxPair("usd/uah"));
        for (String bad : new String[] {"", "EUR/EUR", "EURRON", "EUR/FOO", "EU/RON", "EUR/RON/USD"}) {
            equal(null, normalizeFxPair(bad));
        }

        JSONArray shuffled = new JSONArray().put(rate("2026-11-19", 5))
                .put(rate("2026-11-17", 4)).put(rate("2026-11-20", 5.1))
                .put(rate("2026-11-18", 4.5)).put(rate("2026-11-20", 5.1));
        FxRate latest = parseFx("EUR/RON", latestFx("EUR/RON", shuffled));
        equal("2026-11-20", latest.date);
        close(5.1, latest.rate);
        close(2, latest.change);
        equal("5.1", latest.text());

        JSONArray descending = new JSONArray().put(rate("2026-11-23", 4.9))
                .put(rate("2026-11-20", 5)).put(rate("2026-11-19", 4.8));
        close(-2, parseFx("EUR/RON", latestFx("EUR/RON", descending)).change);
        JSONObject flat = latestFx("EUR/RON",
                new JSONArray().put(rate("2026-11-20", 5)).put(rate("2026-11-19", 5)));
        close(0, parseFx("EUR/RON", flat).change);
        FxRate single = parseFx("EUR/RON", latestFx("EUR/RON", new JSONArray().put(rate("2026-11-20", 5))));
        if (!Double.isNaN(single.change)) throw new AssertionError("invented previous rate");
        for (double previous : new double[] {0, -1, Double.POSITIVE_INFINITY, Double.NaN}) {
            if (!Double.isNaN(parseFx("EUR/RON", rate("2026-11-20", 5).put("previous", previous)).change)) {
                throw new AssertionError("invalid baseline used");
            }
        }
        invalid(() -> latestFx("EUR/RON", new JSONArray()));
        invalid(() -> parseFx("USD/UAH", rate("2026-11-20", 5)));
        invalid(() -> parseFx("EUR/RON", rate("2026-13-44", 5)));
        for (double value : new double[] {0, -1, Double.POSITIVE_INFINITY, Double.NaN}) {
            invalid(() -> parseFx("EUR/RON", rate("2026-11-20", value)));
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            check = Path(directory) / "CurrencyPairsCheck.java"
            check.write_text(program, encoding="utf-8")
            subprocess.run([JAVA, check], check=True, capture_output=True, text=True, timeout=30)
