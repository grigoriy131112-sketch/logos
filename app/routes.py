"""Маршруты блога «Логос»."""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

import markdown
from flask import (
    Blueprint, Response, abort, flash, jsonify, redirect, render_template,
    request, url_for,
)

from . import db

bp = Blueprint("blog", __name__)

MD = markdown.Markdown(extensions=["extra", "sane_lists", "nl2br"])


def render_markdown(text):
    MD.reset()
    return MD.convert(text or "")


def _context(**extra):
    data = {"tags": db.all_tags(), "stats": db.stats()}
    data.update(extra)
    return data


@bp.route("/")
def index():
    tag = request.args.get("tag", "").strip()
    query = request.args.get("q", "").strip()
    posts = db.list_posts(tag=tag or None, query=query or None)
    return render_template(
        "index.html",
        posts=posts,
        active_tag=tag,
        query=query,
        **_context(),
    )


@bp.route("/post/<int:post_id>")
def post(post_id):
    item = db.get_post(post_id)
    if item is None:
        abort(404)
    return render_template(
        "post.html",
        post=item,
        body_html=render_markdown(item["body"]),
        comments=db.list_comments(post_id),
        reactions=db.reaction_counts(post_id),
        reactions_def=db.REACTIONS,
        reading_time=db.reading_time(item["body"]),
        **_context(),
    )


@bp.route("/new", methods=("GET", "POST"))
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        author = request.form.get("author", "").strip() or "Гость"
        tags = request.form.get("tags", "")
        summary = request.form.get("summary", "").strip()

        errors = []
        if len(title) < 3:
            errors.append("Заголовок должен содержать минимум 3 символа.")
        if len(body) < 10:
            errors.append("Текст публикации слишком короткий — напишите хотя бы пару предложений.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "new_post.html",
                form={"title": title, "body": body, "author": author,
                      "tags": tags, "summary": summary},
                **_context(),
            )

        post_id = db.create_post(title, body, author, tags, summary)
        flash("Публикация добавлена в «Логос».", "success")
        return redirect(url_for("blog.post", post_id=post_id))

    return render_template(
        "new_post.html",
        form={"title": "", "body": "", "author": "", "tags": "", "summary": ""},
        **_context(),
    )


@bp.route("/post/<int:post_id>/comment", methods=("POST",))
def add_comment(post_id):
    if db.get_post(post_id) is None:
        abort(404)
    body = request.form.get("body", "").strip()
    author = request.form.get("author", "").strip() or "Гость"
    if len(body) < 2:
        flash("Комментарий не может быть пустым.", "error")
    else:
        db.add_comment(post_id, body, author)
        flash("Спасибо за отклик!", "success")
    return redirect(url_for("blog.post", post_id=post_id) + "#comments")


@bp.route("/post/<int:post_id>/react/<kind>", methods=("POST",))
def react(post_id, kind):
    if db.get_post(post_id) is None:
        abort(404)
    if db.add_reaction(post_id, kind):
        flash("Ваша реакция учтена.", "success")
    return redirect(url_for("blog.post", post_id=post_id) + "#reactions")


@bp.route("/random")
def random_thought():
    """Случайная мысль — открыть случайную публикацию."""
    item = db.random_post()
    if item is None:
        flash("Пока нечем поделиться — добавьте первую публикацию.", "error")
        return redirect(url_for("blog.index"))
    return redirect(url_for("blog.post", post_id=item["id"]))


@bp.route("/author/<path:name>")
def author(name):
    posts = db.list_posts_by_author(name)
    if not posts:
        abort(404)
    return render_template(
        "author.html",
        author_name=posts[0]["author"],
        posts=posts,
        **_context(),
    )


@bp.route("/authors")
def authors():
    return render_template(
        "authors.html",
        authors=db.list_authors(),
        **_context(),
    )


@bp.route("/about")
def about():
    return render_template("about.html", **_context())


@bp.route("/api/posts")
def api_posts():
    posts = db.list_posts(
        tag=request.args.get("tag") or None,
        query=request.args.get("q") or None,
    )
    return jsonify([
        {
            "id": p["id"],
            "title": p["title"],
            "author": p["author"],
            "tags": db.parse_tags(p["tags"]),
            "summary": p["summary"],
            "created_at": p["created_at"],
            "comments": db.comment_count(p["id"]),
            "reactions": db.reaction_total(p["id"]),
            "reading_time": db.reading_time(p["body"]),
        }
        for p in posts
    ])


def _rfc822(value):
    """ISO-дата → формат RFC 822, которого требует RSS 2.0."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


@bp.route("/feed.xml")
def rss():
    base = request.url_root.rstrip("/")
    posts = db.list_posts()[:20]
    items = []
    for p in posts:
        link = f"{base}{url_for('blog.post', post_id=p['id'])}"
        items.append(
            "<item>"
            f"<title>{escape(p['title'])}</title>"
            f"<link>{escape(link)}</link>"
            f"<guid isPermaLink=\"true\">{escape(link)}</guid>"
            f"<pubDate>{_rfc822(p['created_at'])}</pubDate>"
            f"<author>{escape(p['author'])}</author>"
            f"<description>{escape(p['summary'] or p['body'][:200])}</description>"
            "</item>"
        )
    # stylesheet: в браузере лента выглядит как страница,
    # RSS-читалки получают обычный XML.
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<?xml-stylesheet type="text/xsl" href="/feed.xsl"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        "<channel>"
        "<title>Логос</title>"
        f"<link>{escape(base)}</link>"
        f'<atom:link href="{escape(base)}/feed.xml" rel="self" type="application/rss+xml"/>'
        "<description>Блог, чтобы делиться мыслями и публикациями.</description>"
        "<language>ru</language>"
        + "".join(items) +
        "</channel></rss>"
    )
    # Отдаём ленту как application/xml, а не application/rss+xml:
    # Chrome не применяет XSLT к типу rss+xml и показывает сырой XML.
    # RSS-читалки принимают application/xml без проблем.
    return Response(xml, mimetype="application/xml")


@bp.route("/feed.xsl")
def rss_stylesheet():
    return Response(
        render_template("feed.xsl"),
        mimetype="application/xml",
    )
