"""Проверка основных сценариев «Логоса» (python test_app.py)."""

import os
import re
import tempfile

from app import create_app

SIDEBAR = ("Темы", "О чём писать")


def titles(html):
    return [t for t in re.findall(r"<h3>(.*?)</h3>", html) if t not in SIDEBAR]


def run():
    tmp = tempfile.mkdtemp()
    app = create_app({
        "TESTING": True,
        "DATABASE": os.path.join(tmp, "test.sqlite3"),
        "SECRET_KEY": "test",
    })
    client = app.test_client()
    checks = []

    def check(name, condition):
        checks.append((name, condition))

    r = client.get("/")
    check("Главная страница", r.status_code == 200 and "Логос".encode() in r.data)

    r = client.post("/new", data={
        "title": "Проверочная публикация",
        "body": "Это текст проверки с **разметкой** и словом блог.",
        "author": "Тест",
        "tags": "тест, проверка",
        "summary": "Коротко о проверке",
    }, follow_redirects=True)
    check("Создание публикации", r.status_code == 200 and "Проверочная публикация".encode() in r.data)

    r = client.post("/new", data={"title": "ab", "body": "short"}, follow_redirects=True)
    check("Валидация формы", "минимум 3 символа".encode() in r.data)

    posts = client.get("/api/posts").get_json()
    check("API списка", isinstance(posts, list) and len(posts) == 1)
    post_id = posts[0]["id"]

    # Поиск: раньше не находил слова с заглавной буквы (кириллица в SQLite LIKE).
    check("Поиск строчными", titles(client.get("/?q=разметкой").get_data(as_text=True)) == ["Проверочная публикация"])
    check("Поиск заглавными", titles(client.get("/?q=Публикация").get_data(as_text=True)) == ["Проверочная публикация"])
    check("Поиск ВЕРХНИМ регистром", titles(client.get("/?q=БЛОГ").get_data(as_text=True)) == ["Проверочная публикация"])

    r = client.get("/?tag=тест")
    check("Фильтр по тегу", "Проверочная публикация".encode() in r.data)

    r = client.post(f"/post/{post_id}/comment", data={
        "author": "Читатель", "body": "Хороший текст!",
    }, follow_redirects=True)
    check("Добавление комментария", "Хороший текст!".encode() in r.data)

    r = client.post(f"/post/{post_id}/react/insight", follow_redirects=True)
    check("Реакция", r.status_code == 200 and "💡".encode() in r.data)
    check("Недопустимая реакция", client.post(f"/post/{post_id}/react/nope").status_code == 302)

    check("Время чтения в API", posts[0].get("reading_time", 0) >= 1)
    check("Страница авторов", client.get("/authors").status_code == 200)
    check("Страница автора", client.get("/author/Тест").status_code == 200)
    check("Случайная мысль", client.get("/random").status_code == 302)

    r = client.get("/feed.xml")
    check("RSS-лента", r.status_code == 200 and r.mimetype == "application/rss+xml")

    check("Страница «О блоге»", client.get("/about").status_code == 200)
    check("404 для несуществующего поста", client.get("/post/9999").status_code == 404)

    ok = True
    for name, passed in checks:
        print(("  ✓ " if passed else "  ✗ ") + name)
        ok = ok and passed

    print("\nИтог:", "все проверки пройдены" if ok else "ЕСТЬ ОШИБКИ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
