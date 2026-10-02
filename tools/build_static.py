"""Сборка статической версии «Логоса» для GitHub Pages.

GitHub Pages отдаёт только готовые файлы, поэтому страницы рендерит само
приложение — так вид и содержимое совпадают с живым сайтом. Ссылки
переписываются под адрес проекта (подкаталог /logos/), а формы, которым нужен
сервер, заменяются: без сервера их не обслужить.

Исходные данные — data/content.json. Запуск из корня репозитория:

    python tools/build_static.py

Результат — папка docs/, её и отдаёт Pages.
"""

import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
CONTENT = os.path.join(ROOT, "data", "content.json")
HOST = "https://grigoriy131112-sketch.github.io"
PREFIX = "/logos"

sys.path.insert(0, ROOT)
from app import create_app  # noqa: E402
from app import db as blog_db  # noqa: E402

# Транслитерация: адреса страниц должны быть читаемыми и без кириллицы.
TRANS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(text):
    parts = []
    for ch in (text or "").lower():
        if ch in TRANS:
            parts.append(TRANS[ch])
        elif ch.isascii() and ch.isalnum():
            parts.append(ch)
        else:
            parts.append("-")
    return re.sub(r"-+", "-", "".join(parts)).strip("-") or "x"


def make_database(path):
    """Собрать базу из снимка контента — на нём работает рендер."""
    with open(CONTENT, encoding="utf-8") as f:
        data = json.load(f)
    conn = sqlite3.connect(path)
    conn.executescript(blog_db.SCHEMA)
    for table, columns in (
        ("posts", ("id", "title", "author", "tags", "summary", "body",
                   "created_at", "updated_at")),
        ("comments", ("id", "post_id", "author", "body", "created_at")),
        ("reactions", ("id", "post_id", "kind", "created_at")),
    ):
        rows = data.get(table, [])
        if not rows:
            continue
        marks = ", ".join("?" for _ in columns)
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})",
            [tuple(row.get(c) for c in columns) for row in rows],
        )
    conn.commit()
    conn.close()
    return data


db_path = os.path.join(tempfile.mkdtemp(prefix="logos-build-"), "logos.sqlite3")
data = make_database(db_path)

posts = data["posts"]
post_ids = {p["id"] for p in posts}
tag_names = []
for post in posts:
    for tag in blog_db.parse_tags(post["tags"]):
        if tag not in tag_names:
            tag_names.append(tag)
author_names = list(dict.fromkeys(p["author"] for p in posts))
tag_slugs = {t: slugify(t) for t in tag_names}
author_slugs = {a: slugify(a) for a in author_names}

app = create_app({"DATABASE": db_path, "SECRET_KEY": "static-build", "TESTING": True})
client = app.test_client()
ENV = {"SCRIPT_NAME": PREFIX}


def render(path, allow_404=False, **kwargs):
    resp = client.get(path, base_url=HOST, environ_overrides=ENV, **kwargs)
    if resp.status_code == 200 or (allow_404 and resp.status_code == 404):
        return resp.get_data(as_text=True)
    raise SystemExit(f"не отдалась страница {path}: {resp.status_code}")


def fix_links(html, random_posts, page_url):
    """Переписать ссылки приложения под статический адрес в подкаталоге."""

    def repl(match):
        href = match.group(1)
        m = re.match(rf"^{PREFIX}/\?tag=([^&]+)$", href)
        if m:
            return f'href="{PREFIX}/tag/{tag_slugs[unquote(m.group(1))]}/"'
        m = re.match(rf"^{PREFIX}/post/(\d+)$", href)
        if m:
            return f'href="{PREFIX}/post/{m.group(1)}/"'
        m = re.match(rf"^{PREFIX}/author/(.+)$", href)
        if m:
            slug = author_slugs.get(unquote(m.group(1)))
            if slug:
                return f'href="{PREFIX}/author/{slug}/"'
        if href == f"{PREFIX}/random":
            return (f'href="#random" id="random-link"'
                    f' data-posts="{",".join(random_posts)}"')
        if href in (f"{PREFIX}/authors", f"{PREFIX}/about", f"{PREFIX}/new"):
            return f'href="{href}/"'
        return match.group(0)

    html = re.sub(r'href="([^"]*)"', repl, html)
    # canonical и og:url у приложения указывают на адрес запроса (с ?tag=…).
    # У статической страницы адрес один, поэтому подставляем его. Порядок
    # атрибутов в <meta> произвольный, поэтому заменяем по содержимому.
    html = re.sub(r'(rel="canonical"[^>]*href=")[^"]*(")', rf"\g<1>{page_url}\g<2>", html)
    html = re.sub(r'(href=")[^"]*("[^>]*rel="canonical")', rf"\g<1>{page_url}\g<2>", html)
    html = re.sub(r'(property="og:url"[^>]*content=")[^"]*(")', rf"\g<1>{page_url}\g<2>", html)
    html = re.sub(r'(content=")[^"]*("[^>]*property="og:url")', rf"\g<1>{page_url}\g<2>", html)
    return html.replace(
        "</body>",
        f'  <script src="{PREFIX}/static/js/static.js"></script>\n</body>')


def strip_server_forms(html):
    """Убрать формы, которым нужен сервер, и оставить понятный след.

    Реакции становятся обычными счётчиками: выглядит законченно и не
    обещает того, чего статика не может.
    """
    soup = BeautifulSoup(html, "html.parser")

    for form in soup.select(".reactions form"):
        button = form.find("button")
        if button:
            button.attrs.pop("type", None)
            button.name = "span"
            form.replace_with(button)

    comment_form = soup.select_one(".comment-form")
    if comment_form:
        note = soup.new_tag("p")
        note["class"] = "muted static-note"
        note.string = "Отклик можно оставить в версии блога с админкой."
        comment_form.replace_with(note)

    editor = soup.select_one(".editor-form")
    if editor:
        box = soup.new_tag("div")
        box["class"] = "empty"
        para = soup.new_tag("p")
        para.string = ("Публикации добавляет автор блога — так тексты остаются "
                       "вычитанными. Здесь показано, как выглядит форма новой "
                       "записи в полной версии «Логоса».")
        box.append(para)
        editor.replace_with(box)

    return str(soup)


def write(rel_path, text):
    full = os.path.join(DOCS, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


shutil.rmtree(DOCS, ignore_errors=True)
os.makedirs(DOCS, exist_ok=True)
post_urls = [f"{PREFIX}/post/{p['id']}/" for p in posts]

print("=== страницы ===")
write("index.html",
      fix_links(strip_server_forms(render("/")), post_urls, HOST + PREFIX + "/"))
print("  index.html")

for post in posts:
    write(f"post/{post['id']}/index.html",
          fix_links(strip_server_forms(render(f"/post/{post['id']}")), post_urls,
                    f"{HOST}{PREFIX}/post/{post['id']}/"))
print(f"  post/ — {len(posts)}")

for tag in tag_names:
    write(f"tag/{tag_slugs[tag]}/index.html",
          fix_links(strip_server_forms(render("/", query_string={"tag": tag})), post_urls,
                    f"{HOST}{PREFIX}/tag/{tag_slugs[tag]}/"))
print(f"  tag/ — {len(tag_names)}")

for name in author_names:
    write(f"author/{author_slugs[name]}/index.html",
          fix_links(strip_server_forms(render("/author/" + quote(name))), post_urls,
                    f"{HOST}{PREFIX}/author/{author_slugs[name]}/"))
print(f"  author/ — {len(author_names)}")

for page in ("authors", "about", "new"):
    write(f"{page}/index.html",
          fix_links(strip_server_forms(render(f"/{page}")), post_urls,
                    f"{HOST}{PREFIX}/{page}/"))
print("  authors/, about/, new/")

write("404.html",
      fix_links(strip_server_forms(render("/net-takoj-stranicy", allow_404=True)),
                post_urls, f"{HOST}{PREFIX}/404.html"))
print("  404.html")

print("=== служебные файлы ===")
for name in ("feed.xml", "feed.xsl", "robots.txt", "sitemap.xml"):
    write(name, render("/" + name))
print("  feed.xml, feed.xsl, robots.txt, sitemap.xml")

shutil.copytree(os.path.join(ROOT, "app", "static"), os.path.join(DOCS, "static"))
# .nojekyll отключает обработку Jekyll: без него Pages может не отдать часть файлов.
write(".nojekyll", "")
print("  static/, .nojekyll")

print("=== проверка ссылок ===")
problems = []
for root_dir, _dirs, files in os.walk(DOCS):
    for name in files:
        if not name.endswith((".html", ".xml")):
            continue
        full = os.path.join(root_dir, name)
        text = open(full, encoding="utf-8").read()
        rel = os.path.relpath(full, DOCS)
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http", "#", "data:", "mailto:", "tel:")):
                continue
            if href.startswith("/") and not href.startswith(PREFIX + "/"):
                problems.append(f"{rel}: ссылка мимо проекта — {href}")
            if re.search(r"/post/\d+$", href) or re.search(r"/tag/[^/]+$", href):
                problems.append(f"{rel}: ссылка без завершающего слеша — {href}")
        for pid in re.findall(rf'href="{PREFIX}/post/(\d+)/"', text):
            if int(pid) not in post_ids:
                problems.append(f"{rel}: ссылка на несуществующий пост {pid}")
        if "?tag=" in text:
            problems.append(f"{rel}: осталась ссылка с параметром ?tag=")
        if re.search(r'<form[^>]*action="[^"]*(comment|react)', text):
            problems.append(f"{rel}: осталась серверная форма отклика")

if problems:
    print("  НАЙДЕНЫ ПРОБЛЕМЫ:")
    for p in sorted(set(problems))[:25]:
        print("   -", p)
    raise SystemExit(1)
print("  ссылки в порядке, серверных форм нет")

files_count = sum(len(f) for _r, _d, f in os.walk(DOCS))
print(f"  всего файлов: {files_count}")
print("\nГотово: docs/")
