"""Фабрика приложения блога «Логос»."""

import os
from datetime import datetime, timezone

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "logos-dev-secret"),
        DATABASE=os.path.join(app.instance_path, "logos.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

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
