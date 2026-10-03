"""Фабрика приложения блога «Логос»."""

import os
import secrets
from datetime import datetime, timezone

from flask import Flask, g, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db

DEFAULT_SECRET = "logos-dev-secret"

# Настройки Giscus: обсуждения живут в GitHub Discussions репозитория «Логос».
# repo_id и category_id — публичные идентификаторы, они видны на самой
# странице и не являются секретом. Пока Discussions не включены, блок на
# сайте не показывается: иначе Giscus выведет своё сообщение об ошибке.
GISCUS = {
    "repo": "grigoriy131112-sketch/logos",
    "repo_id": "R_kgDOU4kzsQ",
    "category": "Отклики",
    "category_id": "",
}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", DEFAULT_SECRET),
        DATABASE=os.path.join(app.instance_path, "logos.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    # С ключом по умолчанию сессию можно подделать. Для разработки это
    # допустимо, но на живом сайте ключ обязательно задаётся переменной
    # окружения; иначе генерируем случайный при каждом запуске.
    if not test_config and app.config["SECRET_KEY"] == DEFAULT_SECRET:
        if os.environ.get("FLASK_ENV") == "production" or os.environ.get("LOGOS_ENV") == "production":
            raise RuntimeError(
                "Задайте SECRET_KEY в переменных окружения: со стандартным "
                "ключом сессии можно подделать."
            )
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    # Сайт работает за прокси платформы: без этого Flask считает схему
    # http, и ссылки в RSS уходили бы по http вместо https.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    os.makedirs(app.instance_path, exist_ok=True)

    with app.app_context():
        db.init_db()

    app.teardown_appcontext(db.close_db)

    _register_filters(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.before_request
    def make_csp_nonce():
        # Свой одноразовый номер на каждый запрос: он разрешает именно
        # встроенный скрипт темы и ничего больше.
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def security_headers(response):
        """Базовые заголовки безопасности.

        CSP разрешает только свои скрипты (и встроенный скрипт темы по
        одноразовому номеру), свои стили, шрифты Google и картинки из
        data: и https:. Без этого внедрённый скрипт выполнился бы в
        браузере читателя. Giscus — единственное внешнее исключение:
        его скрипт и окно с обсуждением живут на giscus.app.
        """
        nonce = getattr(g, "csp_nonce", None)
        script_src = f"'nonce-{nonce}'" if nonce else "'self'"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            f"script-src 'self' {script_src} https://giscus.app; "
            "frame-src https://giscus.app; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'",
        )
        return response

    @app.context_processor
    def inject_csp_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.context_processor
    def inject_giscus():
        """Настройки Giscus для страницы публикации.

        Пока не задан category_id, шаблон не выводит блок: Discussions ещё
        не включены, и Giscus показал бы ошибку вместо формы.
        """
        return {"giscus": app.config.get("GISCUS", GISCUS)}

    return app


def _register_filters(app):
    @app.template_filter("ru_date")
    def ru_date(value):
        """Отформатировать ISO-дату по-русски: «2 октября 2026»."""
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря",
        ]
        try:
            dt = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"

    @app.template_filter("tags_list")
    def tags_list(value):
        return db.parse_tags(value)

    @app.template_filter("reading_time")
    def reading_time(value):
        return db.reading_time(value)

    @app.template_filter("comments_count")
    def comments_count(post_id):
        return db.comment_count(post_id)
