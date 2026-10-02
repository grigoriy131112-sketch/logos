# AGENTS.md — заметки о проекте «Логос»

## Что это
Блог «Логос» на Flask + SQLite. Название означает «слово/мысль/смысл».

## Команды
- Установка: `pip install -r requirements.txt`
- Наполнить примерами: `python seed.py`
- Запуск: `python run.py` (порт из `PORT`, по умолчанию 12000)
- Проверки: `python test_app.py`

## Устройство
- `app/db.py` — вся работа с SQLite. Таблицы `posts`, `comments`,
  `reactions`. Теги хранятся строкой через запятую.
- Поиск по постам идёт **в Python через `casefold`**, а не в SQL:
  SQLite `LIKE` не учитывает регистр кириллицы, из-за чего «Блог»
  не находил «блог». Не переносите поиск обратно в SQL без учёта этого.
- `app/routes.py` — маршруты; текст постов рендерится Markdown
  с расширениями `extra`, `sane_lists`, `nl2br` (без `html`, чтобы
  не исполнялся сырой HTML).
- Шаблоны — Jinja2, общий каркас в `templates/base.html`.
  Фильтры `ru_date`, `tags_list`, `reading_time`, `comments_count`
  регистрируются в `app/__init__.py`.
- Темы оформления — атрибут `data-theme` на `<html>`; значение хранится
  в `localStorage` (`logos-theme`) и применяется inline-скриптом в `<head>`
  до отрисовки, чтобы не было мигания. Палитры — CSS-переменные в
  `static/css/style.css` (`[data-theme="light"]` и `[data-theme="dark"]`).
- Даты хранятся в UTC в ISO-формате, выводятся фильтром `ru_date`.

## Соглашения
- Русский язык в интерфейсе и комментариях к коду.
- Сообщения об ошибках — через `flash` с категориями `error`/`success`.
- Новые маршруты регистрируются в `app/routes.py` (blueprint `blog`).
- База данных создаётся автоматически при старте приложения.

## Безопасность
- Пользовательский Markdown рендерится без `html`-расширения.
- Файл базы `instance/logos.sqlite3` и `server.log` не попадают в git.
