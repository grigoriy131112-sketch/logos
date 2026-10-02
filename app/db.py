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
"""


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


def list_posts(tag=None, query=None):
    db = get_db()
    sql = "SELECT * FROM posts"
    clauses, params = [], []

    if tag:
        clauses.append("(',' || tags || ',') LIKE ?")
        params.append(f"%,{tag.strip().lower()},%")
    if query:
        clauses.append("(title LIKE ? OR body LIKE ? OR summary LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC"
    return db.execute(sql, params).fetchall()


def get_post(post_id):
    return get_db().execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
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


def all_tags():
    """Собрать все теги с количеством публикаций."""
    counts = {}
    for row in get_db().execute("SELECT tags FROM posts"):
        for tag in parse_tags(row["tags"]):
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def stats():
    db = get_db()
    posts = db.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
    comments = db.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
    return {"posts": posts, "comments": comments, "tags": len(all_tags())}
