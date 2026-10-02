"""Хранилище данных блога «Логос» на SQLite."""

import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    author      TEXT    NOT NULL DEFAULT 'Гость',
    tags        TEXT    NOT NULL DEFAULT '',
    summary     TEXT    NOT NULL DEFAULT '',
    body        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER NOT NULL,
    author      TEXT    NOT NULL DEFAULT 'Гость',
    body        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER NOT NULL,
    kind        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
);
"""

# Реакции: код, эмодзи, подпись.
REACTIONS = [
    ("like", "❤️", "Нравится"),
    ("insight", "💡", "Мысль"),
    ("thanks", "🙏", "Спасибо"),
    ("think", "🤔", "Задумался"),
]
REACTION_KINDS = {kind for kind, _, _ in REACTIONS}

WORDS_PER_MINUTE = 180


def get_db():
    """Вернуть соединение с БД, привязанное к текущему запросу."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_tags(raw):
    """Разобрать строку тегов через запятую в аккуратный список."""
    if not raw:
        return []
    seen = []
    for chunk in raw.replace("#", " ").split(","):
        tag = chunk.strip().lower()
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def tags_to_string(tags):
    return ", ".join(parse_tags(tags))


def reading_time(text):
    """Оценить время чтения в минутах (не меньше одной)."""
    words = len((text or "").split())
    return max(1, round(words / WORDS_PER_MINUTE))


def create_post(title, body, author="Гость", tags="", summary=""):
    ts = now_iso()
    db = get_db()
    cur = db.execute(
        "INSERT INTO posts (title, author, tags, summary, body, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title.strip(), author.strip() or "Гость", tags_to_string(tags),
         summary.strip(), body.strip(), ts, ts),
    )
    db.commit()
    return cur.lastrowid


def _matches(row, tag=None, query=None):
    if tag and tag.strip().lower() not in parse_tags(row["tags"]):
        return False
    if query:
        needle = query.strip().casefold()
        haystack = f"{row['title']} {row['summary']} {row['body']}".casefold()
        if needle not in haystack:
            return False
    return True


def list_posts(tag=None, query=None):
    """Список публикаций с фильтром по тегу и поиском.

    Поиск выполняется в Python через casefold: SQLite LIKE не умеет
    сравнивать кириллицу без учёта регистра, из-за чего «Блог» не находил
    «блог».
    """
    rows = get_db().execute(
        "SELECT * FROM posts ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [row for row in rows if _matches(row, tag, query)]


def get_post(post_id):
    return get_db().execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()


def random_post():
    return get_db().execute(
        "SELECT * FROM posts ORDER BY RANDOM() LIMIT 1"
    ).fetchone()


def comment_count(post_id):
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM comments WHERE post_id = ?", (post_id,)
    ).fetchone()
    return row["n"]


def list_comments(post_id):
    return get_db().execute(
        "SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC, id ASC",
        (post_id,),
    ).fetchall()


def add_comment(post_id, body, author="Гость"):
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, author, body, created_at) VALUES (?, ?, ?, ?)",
        (post_id, author.strip() or "Гость", body.strip(), now_iso()),
    )
    db.commit()
    return cur.lastrowid


def add_reaction(post_id, kind):
    if kind not in REACTION_KINDS:
        return False
    db = get_db()
    db.execute(
        "INSERT INTO reactions (post_id, kind, created_at) VALUES (?, ?, ?)",
        (post_id, kind, now_iso()),
    )
    db.commit()
    return True


def reaction_counts(post_id):
    counts = {kind: 0 for kind in REACTION_KINDS}
    for row in get_db().execute(
        "SELECT kind, COUNT(*) AS n FROM reactions WHERE post_id = ? GROUP BY kind",
        (post_id,),
    ):
        counts[row["kind"]] = row["n"]
    return counts


def reaction_total(post_id):
    return get_db().execute(
        "SELECT COUNT(*) AS n FROM reactions WHERE post_id = ?", (post_id,)
    ).fetchone()["n"]


def list_authors():
    rows = get_db().execute(
        "SELECT author, COUNT(*) AS n FROM posts GROUP BY author"
        " ORDER BY n DESC, author ASC"
    ).fetchall()
    return [(row["author"], row["n"]) for row in rows]


def list_posts_by_author(name):
    needle = (name or "").strip().casefold()
    rows = get_db().execute(
        "SELECT * FROM posts ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [row for row in rows if row["author"].casefold() == needle]


def all_tags():
    """Собрать все теги с количеством публикаций."""
    counts = {}
    for row in get_db().execute("SELECT tags FROM posts"):
        for tag in parse_tags(row["tags"]):
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def stats(tag_count=None):
    db = get_db()
    posts = db.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
    comments = db.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
    reactions = db.execute("SELECT COUNT(*) AS n FROM reactions").fetchone()["n"]
    if tag_count is None:
        tag_count = len(all_tags())
    return {
        "posts": posts,
        "comments": comments,
        "reactions": reactions,
        "tags": tag_count,
    }
