package io.cleanyourtv.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.EditText;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Hold OK on a movie or a show (a poster, Explore's banner): seen, My list, favorites and the account's lists, without
 * opening the title. The screen behind is told (Host) so its rows and seen badges follow.
 */
final class TitleMenu {
    private TitleMenu() {}

    /** A screen whose rows depend on the lists (Explore): told after a change (`lists`: My list or favorites, not seen). */
    interface Host { void titleChanged(boolean lists); }

    private interface Task { void run() throws Exception; }

    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    static void show(Activity a, View anchor, Tmdb.Title t) {
        if (!"movie".equals(t.kind) && !"tv".equals(t.kind)) return;
        boolean account = Tmdb.signedIn(a);
        new Thread(() -> {   // with an account, My list and favorites are the account's: ask TMDB first
            JSONObject states = account ? Tmdb.states(a, t.kind, t.id) : new JSONObject();
            boolean inList = account ? states.optBoolean("watchlist") : Tmdb.inWatchlist(a, t.kind, t.id);
            boolean favorite = states.optBoolean("favorite");
            MAIN.post(() -> {
                if (!a.isFinishing() && anchor.isAttachedToWindow()) pick(a, anchor, t, account, inList, favorite);
            });
        }, "title-menu").start();
    }

    private static void pick(Activity a, View anchor, Tmdb.Title t, boolean account, boolean inList, boolean favorite) {
        List<String> labels = new ArrayList<>();
        List<Runnable> actions = new ArrayList<>();
        boolean seen = Tmdb.isSeen(a, t.kind, t.id);
        labels.add(seen ? Ui.tr("Desmarcar “Já assisti”", "Unmark as seen") : "✓  " + Ui.tr("Já assisti", "Mark as seen"));
        actions.add(() -> {
            Tmdb.setSeen(a, t, !seen);
            changed(a, seen ? Ui.tr("Desmarcado", "Unmarked") : Ui.tr("Marcado como assistido", "Marked as seen"), false);
        });
        labels.add(inList ? Ui.tr("Remover da Minha lista", "Remove from My list") : "+  " + Ui.tr("Adicionar à Minha lista", "Add to My list"));
        actions.add(() -> background(a, Ui.tr("Não deu para salvar: ", "Couldn't save: "), () -> Tmdb.setWatchlist(a, t, !inList),
                inList ? Ui.tr("Removido da Minha lista", "Removed from My list") : Ui.tr("Adicionado à Minha lista", "Added to My list")));
        if (account) {
            labels.add(favorite ? Ui.tr("Remover dos favoritos", "Remove from favorites") : "♥  " + Ui.tr("Favoritar", "Favorite"));
            actions.add(() -> background(a, Ui.tr("Não deu para favoritar: ", "Couldn't favorite: "), () -> Tmdb.setFavorite(a, t, !favorite),
                    favorite ? Ui.tr("Removido dos favoritos", "Removed from favorites") : Ui.tr("Adicionado aos favoritos", "Added to favorites")));
            if ("movie".equals(t.kind)) {   // TMDB's v3 lists hold movies only
                labels.add("≡  " + Ui.tr("Adicionar a uma lista…", "Add to a list…"));
                actions.add(() -> addToList(a, t.id));
            }
        }
        labels.add(Ui.tr("Ver detalhes", "Details"));
        actions.add(() -> DetailActivity.open(a, t.kind, t.id));
        labels.add(Ui.tr("Cancelar", "Cancel"));
        actions.add(null);
        int[] xy = new int[2];
        anchor.getLocationInWindow(xy);
        Rect at = new Rect(xy[0], xy[1], xy[0] + anchor.getWidth(), xy[1] + anchor.getHeight());
        TvUi.popover(a, anchor, at, t.name, labels.toArray(new String[0]), which -> {
            Runnable r = actions.get(which);
            if (r != null) r.run();
        });
    }

    /** The account's lists to pick from, or a new one (movies only). */
    static void addToList(Activity a, int movie) {
        new Thread(() -> {
            try {
                List<String[]> lists = Tmdb.lists(a);
                MAIN.post(() -> { if (!a.isFinishing()) pickList(a, movie, lists); });
            } catch (Exception e) {
                MAIN.post(() -> Toast.makeText(a, e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }, "title-lists").start();
    }

    private static void pickList(Activity a, int movie, List<String[]> lists) {
        String[] items = new String[lists.size() + 1];
        for (int i = 0; i < lists.size(); i++) items[i] = lists.get(i)[1] + "  (" + lists.get(i)[2] + ")";
        items[lists.size()] = "+  " + Ui.tr("Nova lista…", "New list…");
        new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle(Ui.tr("Adicionar a uma lista", "Add to a list"))
                .setItems(items, (d, which) -> {
                    if (which < lists.size()) {
                        String list = lists.get(which)[0], name = lists.get(which)[1];
                        background(a, Ui.tr("Não deu para adicionar: ", "Couldn't add: "), () -> Tmdb.addToList(a, list, movie),
                                Ui.tr("Adicionado a ", "Added to ") + name);
                        return;
                    }
                    EditText field = new EditText(a);
                    field.setSingleLine(true);
                    field.setHint(Ui.tr("Nome da lista", "List name"));
                    new AlertDialog.Builder(a, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                            .setTitle(Ui.tr("Nova lista", "New list"))
                            .setView(field)
                            .setPositiveButton(Ui.tr("Criar", "Create"), (d2, w2) -> background(a, Ui.tr("Não deu para criar: ", "Couldn't create: "),
                                    () -> Tmdb.addToList(a, Tmdb.createList(a, field.getText().toString().trim()), movie),
                                    Ui.tr("Lista criada", "List created")))
                            .setNegativeButton(Ui.tr("Cancelar", "Cancel"), null)
                            .show();
                })
                .show();
    }

    /** Runs `task` off the main thread (the account is TMDB's), then says `done` and refreshes the screen. */
    private static void background(Activity a, String failure, Task task, String done) {
        new Thread(() -> {
            try {
                task.run();
                MAIN.post(() -> changed(a, done, true));
            } catch (Exception e) {
                MAIN.post(() -> Toast.makeText(a, failure + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }, "title-action").start();
    }

    private static void changed(Activity a, String done, boolean lists) {
        if (a.isFinishing()) return;
        Toast.makeText(a, done, Toast.LENGTH_SHORT).show();
        TvUi.refreshSeen(a.getWindow().getDecorView());
        if (a instanceof Host) ((Host) a).titleChanged(lists);
    }
}
