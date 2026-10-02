"""Проверка основных маршрутов «Логоса» (python test_app.py)."""

import os
import tempfile

from app import create_app


def run():
    tmp = tempfile.mkdtemp()
    app = create_app({
        "TESTING": True,
        "DATABASE": os.path.join(tmp, "test.sqlite3"),
        "SECRET_KEY": "test",
    })
    client = app.test_client()
    checks = []

    r = client.get("/")
    checks.append(("Главная страница", r.status_code == 200 and "Логос".encode() in r.data))

    r = client.post("/new", data={
        "title": "Проверочная публикация",
        "body": "Это текст проверки с **разметкой**.",
        "author": "Тест",
        "tags": "тест, проверка",
        "summary": "Коротко о проверке",
    }, follow_redirects=True)
    checks.append(("Создание публикации", r.status_code == 200 and "Проверочная публикация".encode() in r.data))

    r = client.post("/new", data={"title": "ab", "body": "short"}, follow_redirects=True)
    checks.append(("Валидация формы", "минимум 3 символа".encode() in r.data))

    posts = client.get("/api/posts").get_json()
    checks.append(("API списка", isinstance(posts, list) and len(posts) == 1))
    post_id = posts[0]["id"]

    r = client.post(f"/post/{post_id}/comment", data={
        "author": "Читатель", "body": "Хороший текст!",
    }, follow_redirects=True)
    checks.append(("Добавление комментария", "Хороший текст!".encode() in r.data))

    r = client.get("/?q=разметкой")
    checks.append(("Поиск", "Проверочная публикация".encode() in r.data))

    r = client.get("/?tag=тест")
    checks.append(("Фильтр по тегу", "Проверочная публикация".encode() in r.data))

    r = client.get("/about")
    checks.append(("Страница «О блоге»", r.status_code == 200))

    r = client.get("/post/9999")
    checks.append(("404 для несуществующего поста", r.status_code == 404))

    ok = True
    for name, passed in checks:
        print(("  ✓ " if passed else "  ✗ ") + name)
        ok = ok and passed

    print("\nИтог:", "все проверки пройдены" if ok else "ЕСТЬ ОШИБКИ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
