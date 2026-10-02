"""Маршруты блога «Логос»."""

import markdown
from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template,
    request, url_for,
)

from . import db

bp = Blueprint("blog", __name__)

MD = markdown.Markdown(extensions=["extra", "sane_lists", "nl2br"])


def render_markdown(text):
    MD.reset()
    return MD.convert(text or "")


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
        tags=db.all_tags(),
        stats=db.stats(),
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
        tags=db.all_tags(),
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
                tags=db.all_tags(),
            )

        post_id = db.create_post(title, body, author, tags, summary)
        flash("Публикация добавлена в «Логос».", "success")
        return redirect(url_for("blog.post", post_id=post_id))

    return render_template(
        "new_post.html",
        form={"title": "", "body": "", "author": "", "tags": "", "summary": ""},
        tags=db.all_tags(),
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


@bp.route("/about")
def about():
    return render_template("about.html", tags=db.all_tags(), stats=db.stats())


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
        }
        for p in posts
    ])
