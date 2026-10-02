"""Точка входа: python run.py"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "12000"))
    # Отладка только по явному запросу: с debug=True Werkzeug открывает
    # интерактивную консоль по /console, и любой посетитель может
    # выполнить код на сервере. Для разработки: LOGOS_DEBUG=1 python run.py
    debug = os.environ.get("LOGOS_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
