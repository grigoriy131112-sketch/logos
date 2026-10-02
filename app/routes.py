"""Маршруты блога «Логос»."""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

import markdown
import nh3
from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import db

bp = Blueprint("blog", __name__)

MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]

# Белый список для HTML, который получается из Markdown. Всё остальное
# вырезается: посетитель может опубликовать текст, а он показывается
# другим людям, поэтому сырой HTML и `javascript:` в ссылках недопустимы.
ALLOWED_TAGS = {
    "p", "br", "hr", "em", "strong", "del", "blockquote", "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "th": {"align"},
    "td": {"align"},
}
ALLOWED_SCHEMES = {"http", "https", "mailto", "tel"}

# Пределы длины: атрибуты maxlength в форме проверяются только браузером,
# поэтому то же самое нужно проверять на сервере.
MAX_TITLE = 160
MAX_SUMMARY = 220
MAX_AUTHOR = 60
MAX_TAGS = 200
MAX_BODY = 20000
MAX_COMMENT = 2000
MAX_REACTIONS_IN_SESSION = 200


def render_markdown(text):
    # Свой объект Markdown на каждый вызов: markdown.Markdown хранит
    # состояние между convert(), а сервер обрабатывает запросы в потоках.
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    html = md.convert(text or "")
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes=ALLOWED_SCHEMES,
        link_rel="noopener noreferrer",
    )


def _validate_post(title, body, author, summary, tags):
    """Общие правила для создания и правки публикации."""
    errors = []
    if len(title) < 3:
        errors.append("Заголовок должен содержать минимум 3 символа.")
    if len(title) > MAX_TITLE:
        errors.append(f"Заголовок слишком длинный — максимум {MAX_TITLE} символов.")
    if len(body) < 10:
        errors.append("Текст публикации слишком короткий — напишите хотя бы пару предложений.")
    if len(body) > MAX_BODY:
        errors.append(f"Текст слишком длинный — максимум {MAX_BODY} символов.")
    if len(author) > MAX_AUTHOR:
        errors.append(f"Имя автора слишком длинное — максимум {MAX_AUTHOR} символов.")
    if len(summary) > MAX_SUMMARY:
        errors.append(f"Описание слишком длинное — максимум {MAX_SUMMARY} символов.")
    if len(tags) > MAX_TAGS:
        errors.append(f"Список тем слишком длинный — максимум {MAX_TAGS} символов.")
    return errors


def _context(**extra):
    tags = db.all_tags()
    data = {"tags": tags, "stats": db.stats(tag_count=len(tags))}
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

        errors = _validate_post(title, body, author, summary, tags)
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


@bp.route("/post/<int:post_id>/edit", methods=("GET", "POST"))
def edit_post(post_id):
    item = db.get_post(post_id)
    if item is None:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        author = request.form.get("author", "").strip() or item["author"]
        tags = request.form.get("tags", "")
        summary = request.form.get("summary", "").strip()

        errors = _validate_post(title, body, author, summary, tags)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "edit_post.html",
                post=item,
                form={"title": title, "body": body, "author": author,
                      "tags": tags, "summary": summary},
                **_context(),
            )

        db.update_post(post_id, title, body, author, tags, summary)
        flash("Изменения сохранены.", "success")
        return redirect(url_for("blog.post", post_id=post_id))

    return render_template(
        "edit_post.html",
        post=item,
        form={"title": item["title"], "body": item["body"], "author": item["author"],
              "tags": item["tags"], "summary": item["summary"]},
        **_context(),
    )


@bp.route("/post/<int:post_id>/delete", methods=("POST",))
def delete_post(post_id):
    if db.get_post(post_id) is None:
        abort(404)
    db.delete_post(post_id)
    flash("Публикация удалена.", "success")
    return redirect(url_for("blog.index"))


@bp.route("/post/<int:post_id>/comment", methods=("POST",))
def add_comment(post_id):
    if db.get_post(post_id) is None:
        abort(404)
    body = request.form.get("body", "").strip()
    author = request.form.get("author", "").strip() or "Гость"
    if len(body) < 2:
        flash("Комментарий не может быть пустым.", "error")
    elif len(body) > MAX_COMMENT:
        flash(f"Комментарий слишком длинный — максимум {MAX_COMMENT} символов.", "error")
    elif len(author) > MAX_AUTHOR:
        flash(f"Имя слишком длинное — максимум {MAX_AUTHOR} символов.", "error")
    else:
        db.add_comment(post_id, body, author)
        flash("Спасибо за отклик!", "success")
    return redirect(url_for("blog.post", post_id=post_id) + "#comments")


@bp.route("/post/<int:post_id>/react/<kind>", methods=("POST",))
def react(post_id, kind):
    if db.get_post(post_id) is None:
        abort(404)
    # Ограничение на число реакций от одного посетителя: иначе счётчик
    # накручивается одним скриптом. Считаем по сессии.
    used = session.get("reactions", 0)
    if used >= MAX_REACTIONS_IN_SESSION:
        flash("Вы поставили много реакций за эту сессию. Отдохните немного.", "error")
    elif db.add_reaction(post_id, kind):
        session["reactions"] = used + 1
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


@bp.route("/workshop")
def workshop():
    """Личная мастерская: профиль и свои мысли в браузере, без регистрации."""
    return render_template("workshop.html", can_publish=True, **_context())


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
    # _external=True: абсолютные адреса собираются с учётом SCRIPT_NAME,
    # поэтому лента работает и в корне домена, и в подкаталоге (/logos/).
    posts = db.list_posts()[:20]
    items = []
    for p in posts:
        link = url_for("blog.post", post_id=p["id"], _external=True)
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
    base = url_for("blog.index", _external=True).rstrip("/")
    # stylesheet: в браузере лента выглядит как страница,
    # RSS-читалки получают обычный XML.
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<?xml-stylesheet type="text/xsl" href="{url_for("blog.rss_stylesheet")}"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        "<channel>"
        "<title>Логос</title>"
        f"<link>{escape(base)}</link>"
        f'<atom:link href="{escape(url_for("blog.rss", _external=True))}"'
        ' rel="self" type="application/rss+xml"/>'
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


@bp.route("/robots.txt")
def robots():
    """Подсказка поисковикам: служебные страницы индексировать не нужно."""
    sitemap_url = url_for("blog.sitemap", _external=True)
    body = (
        "User-agent: *\n"
        "Disallow: /new\n"
        "Disallow: /random\n"
        "Disallow: /api/\n"
        "Disallow: /feed.xsl\n"
        f"\nSitemap: {sitemap_url}\n"
    )
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    urls = [
        url_for("blog.index", _external=True),
        url_for("blog.about", _external=True),
        url_for("blog.authors", _external=True),
    ]
    for p in db.list_posts():
        urls.append(url_for("blog.post", post_id=p["id"], _external=True))
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
        + "</urlset>"
    )
    return Response(body, mimetype="application/xml")
