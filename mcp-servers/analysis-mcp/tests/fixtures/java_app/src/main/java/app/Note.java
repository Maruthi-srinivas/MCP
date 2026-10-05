package app;

import app.Store;

public class Note {
    public String title() {
        return Store.load();
    }
}
