import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;

// The queue, eviction, image-loading, byte accounting and download methods are inserted unchanged from production.
public class HomeArtworkCheck {
    static final long MB = 1024 * 1024;
    final ManualExecutor imageIo = new ManualExecutor();
    final Context context = new Context();
    boolean light = true;
    int notifications;
    String IMAGES;
    /* FIELDS */
    /* METHODS */
    private void download(Pick p) throws IOException {
        if (IMAGES != null) { actualDownload(p); return; }
        if (Downloads.fetch(p.backdrop) == null) throw new IOException("Test download failure");
    }

    static class Pick { String kind = "movie", title = "", backdrop; }
    static class AppLog { static void w(String message) {} }
    static class Context {
        final File dir;
        Context() {
            try { dir = Files.createTempDirectory("home-artwork-").toFile(); }
            catch (IOException e) { throw new UncheckedIOException(e); }
        }
        File getCacheDir() { return dir; }
    }
    static class Bitmap {
        final int size;
        Bitmap(int size) { this.size = size; }
        int getAllocationByteCount() { return size; }
        void recycle() {}
    }
    static class BitmapFactory {
        static class Options { boolean inJustDecodeBounds; int inSampleSize, outWidth = 1920, outHeight = 1080; }
        static Bitmap decodeFile(String path, Options opts) { return new Bitmap(Downloads.size); }
    }
    static class Backdrop {
        static final int W = 1920;
        Bitmap image, wide, tall, lightImage, nightImage;
        int[] frost, glass, light, lightGlass, nightFrost, nightGlass;
        static int builds;
        /* BYTES */
        static Backdrop make(Bitmap bitmap, boolean light) {
            builds++;
            Backdrop out = new Backdrop(); out.image = bitmap;
            return out;
        }
    }
    static class Downloads {
        static final List<String> fetched = new ArrayList<>();
        static final Set<String> failed = new HashSet<>();
        static Runnable onFetch;
        static int size = (int) (4 * MB);
        static Bitmap fetch(String url) {
            fetched.add(url);
            if (onFetch != null) { Runnable run = onFetch; onFetch = null; run.run(); }
            return failed.contains(url) ? null : new Bitmap(size);
        }
    }
    static class ManualExecutor implements Executor {
        final Deque<Runnable> work = new ArrayDeque<>();
        public void execute(Runnable run) {
            work.addLast(run);
            check(work.size() <= 2, "More than two jobs submitted");
        }
        void drain() {
            int count = 0;
            while (!work.isEmpty()) {
                check(++count < 100, "Queue never settles");
                work.removeFirst().run();
            }
        }
    }
    void notifyListeners() { notifications++; }
    List<Pick> now(String kind) { return Collections.emptyList(); }
    static List<Pick> picks(String prefix, int count) {
        List<Pick> result = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            Pick p = new Pick(); p.backdrop = prefix + i; result.add(p);
        }
        return result;
    }
    void page(String service, List<Pick> picks) {
        prepareImages(service, picks.subList(0, 3), picks.subList(3, picks.size()));
    }
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    void withinBudget() {
        long bytes = images.values().stream().mapToLong(Backdrop::bytes).sum();
        check(bytes <= IMAGE_BYTES, "Cache over memory budget");
    }
    void run(String scenario) throws Exception {
        List<Pick> a = picks("a", 9), b = picks("b", 9);
        switch (scenario) {
            case "priority":
                page("a", picks("a", 20));
                check(pending.size() == 2 && imageQueue.size() == 7, "Window is not bounded to nine");
                imageIo.drain();
                check(Downloads.fetched.equals(Arrays.asList("a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8")),
                        "Visible cards did not load first: " + Downloads.fetched);
                page("a", a); imageIo.drain();
                check(Downloads.fetched.size() == 9, "Repeated window downloaded cached images");
                break;
            case "switch":
                page("a", a); page("b", b); imageIo.drain();
                check(Downloads.fetched.size() == 9 && Downloads.fetched.stream().allMatch(s -> s.startsWith("b")),
                        "Stale service was downloaded");
                check(pending.isEmpty() && imageQueue.isEmpty(), "Work left pending");
                break;
            case "recent":
                for (String service : new String[]{"a", "b", "c"}) {
                    page(service, picks(service, 9)); imageIo.drain(); withinBudget();
                }
                for (String service : new String[]{"a", "b", "c"})
                    for (Pick p : picks(service, 3)) check(backdrop(p) != null, "Recent page evicted: " + p.backdrop);
                Downloads.fetched.clear();
                page("a", a); imageIo.drain();
                check(Downloads.fetched.stream().noneMatch(s -> Arrays.asList("a0", "a1", "a2").contains(s)),
                        "Returning service reloaded visible cards");
                break;
            case "budget":
                // One larger prefetch must not evict the current page or continually rebuild itself.
                page("a", a); imageIo.drain();
                for (String key : new ArrayList<>(images.keySet())) {
                    Backdrop item = images.get(key); item.image = new Bitmap((int) (8 * MB));
                }
                pruneImages(); withinBudget();
                int builds = Backdrop.builds;
                for (int i = 0; i < 20; i++) { page("a", a); imageIo.drain(); withinBudget(); }
                check(Backdrop.builds == builds, "Evicted prefetch repeatedly rebuilt");
                for (Pick p : a.subList(0, 3)) check(backdrop(p) != null, "Visible card evicted");
                Backdrop size = new Backdrop(); size.image = new Bitmap(100); size.frost = new int[7];
                check(size.bytes() == 128, "Bitmap and array bytes not both counted");
                break;
            case "failure":
                Downloads.failed.add("a0");
                page("a", a); imageIo.drain();
                int fetched = Downloads.fetched.size();
                page("a", a); imageIo.drain();
                check(Downloads.fetched.size() == fetched, "Failed image immediately retried");
                imageFailedAt.put("a0", System.currentTimeMillis() - 61_000);
                Downloads.failed.clear(); page("a", a); imageIo.drain();
                check(backdrop(a.get(0)) != null, "Visible failure never retried");
                break;
            case "pressure":
                Downloads.size = (int) (8 * MB);
                for (String service : new String[]{"a", "b", "c"}) {
                    page(service, picks(service, 9)); imageIo.drain(); withinBudget();
                }
                List<Pick> c = picks("c", 9);
                check(backdrop(c.get(8)) == null, "Test did not evict a prefetch");
                check(!imageFailedAt.containsKey("c8"), "Eviction treated as network failure");
                prepareImages("c", Arrays.asList(c.get(8), c.get(0), c.get(1)), List.of()); imageIo.drain();
                check(backdrop(c.get(8)) != null, "Evicted prefetch delayed when it became visible");
                break;
            case "stale":
                Downloads.onFetch = () -> page("b", b);
                page("a", a); imageIo.drain();
                check(!images.containsKey("a0"), "Stale running result cached");
                check(Backdrop.builds == 9, "Stale image unnecessarily prepared");
                break;
            case "trim":
                page("a", a); imageIo.drain();
                page("b", b); trim(); imageIo.drain();
                check(Downloads.fetched.stream().noneMatch(s -> s.startsWith("b")), "Trim left queued loads");
                page("b", b); prepareImages("", List.of(), List.of()); imageIo.drain();
                check(Downloads.fetched.stream().noneMatch(s -> s.startsWith("b")), "Pause left queued loads");
                break;
            case "download":
                parallelDownloads();
                break;
            default: throw new AssertionError(scenario);
        }
    }
    void parallelDownloads() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        ExecutorService workers = Executors.newFixedThreadPool(2), requests = Executors.newFixedThreadPool(2);
        CountDownLatch arrived = new CountDownLatch(2);
        AtomicInteger sequence = new AtomicInteger();
        byte[] first = new byte[32768], second = new byte[32768];
        Arrays.fill(first, (byte) 1); Arrays.fill(second, (byte) 2);
        server.setExecutor(requests);
        server.createContext("/shared.jpg", exchange -> {
            byte[] body = sequence.getAndIncrement() == 0 ? first : second;
            try {
                exchange.sendResponseHeaders(200, body.length);
                exchange.getResponseBody().write(body, 0, 1024);
                exchange.getResponseBody().flush();
                arrived.countDown();
                if (!arrived.await(5, TimeUnit.SECONDS)) throw new IOException("Second request did not arrive");
                exchange.getResponseBody().write(body, 1024, body.length - 1024);
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            finally { exchange.close(); }
        });
        try {
            server.start(); IMAGES = "http://127.0.0.1:" + server.getAddress().getPort();
            Pick p = new Pick(); p.backdrop = "/shared.jpg";
            Callable<Void> task = () -> { download(p); return null; };
            Future<Void> one = workers.submit(task), two = workers.submit(task);
            one.get(10, TimeUnit.SECONDS); two.get(10, TimeUnit.SECONDS);
            byte[] stored = Files.readAllBytes(imageFile(p).toPath());
            check(Arrays.equals(stored, first) || Arrays.equals(stored, second), "Concurrent download corrupted cache");
            check(imageFile(p).getParentFile().listFiles((d, n) -> n.endsWith(".part")).length == 0, "Temporary files left");
        } finally { server.stop(0); workers.shutdownNow(); requests.shutdownNow(); }
    }
    public static void main(String[] args) throws Exception {
        HomeArtworkCheck test = new HomeArtworkCheck();
        try { test.run(args[0]); }
        finally {
            try (java.util.stream.Stream<Path> files = Files.walk(test.context.dir.toPath())) {
                files.sorted(Comparator.reverseOrder()).forEach(p -> { try { Files.delete(p); } catch (IOException ignored) {} });
            }
        }
    }
}
