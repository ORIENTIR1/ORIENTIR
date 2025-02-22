import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

from flask import Flask, jsonify, request
import openai
import requests
import uuid
import time
from dotenv import load_dotenv
from flask_cors import CORS
import logging

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем приложение Flask
app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов

# Загружаем переменные окружения из .env (локально)
load_dotenv()

# Настраиваем API OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.proxy = {}  # Явно очищаем любые прокси

JIVOCHAT_WEBHOOK_URL = os.getenv(
    "JIVOCHAT_WEBHOOK_URL",
    "https://bot.jivosite.com/webhooks/WEVYtVZzXuYaG3/mygpttoken123",
)

@app.route("/", methods=["GET"])
def index():
    """Проверка, что сервис работает."""
    return jsonify({"message": "Сервис работает! 🟢"}), 200

@app.route("/mygpttoken123", methods=["POST"])
def handle_request():
    """Обработка запросов от JivoChat с использованием OpenAI."""
    logger.info(f"Получен запрос на /mygpttoken123: URL={request.url}, Data={request.json}")
    try:
        data = request.json
        logger.info(f"Полученные данные от Jivo: {data}")

        event = data.get("event", "")
        chat_id = data.get("chat_id", "")
        client_id = data.get("client_id", "")
        user_message = data.get("message", {}).get("text", data.get("text", ""))

        if not user_message or not chat_id or event != "CLIENT_MESSAGE":
            return (
                jsonify(
                    {
                        "error": {
                            "code": "invalid_request",
                            "message": "Некорректный запрос от Jivo",
                        }
                    }
                ),
                400,
            )

        logger.info("⚡ Отправляем запрос в OpenAI через новый метод ChatCompletions...")

        # Используем актуальный метод completions.create, совместимый с openai>=1.0.0
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}]
        )

        response_message = response.choices[0].message.content.strip()

        send_response_to_jivochat(response_message, chat_id, client_id)

        logger.info(f"📩 Ответ отправлен: {response_message}")
        return jsonify({"message": response_message}), 200

    except Exception as e:
        logger.error(f"🔥 Ошибка при обработке запроса: {str(e)}")
        return jsonify({"error": {"code": "server_error", "message": str(e)}}), 500


def send_response_to_jivochat(response_message, chat_id, client_id):
    """Отправка ответа обратно в JivoChat через webhook."""
    if not JIVOCHAT_WEBHOOK_URL:
        logger.warning("JIVOCHAT_WEBHOOK_URL не настроен, ответ не отправлен")
        return

    headers = {"Content-Type": "application/json"}
    data = {
        "id": str(uuid.uuid4()),
        "event": "BOT_MESSAGE",
        "client_id": client_id,
        "chat_id": chat_id,
        "message": {
            "type": "TEXT",
            "text": response_message,
            "timestamp": int(time.time()),
        },
    }

    try:
        logger.info(
            f"📤 Отправка ответа в JivoChat на URL: {JIVOCHAT_WEBHOOK_URL}, Данные: {data}"
        )
        response = requests.post(
            JIVOCHAT_WEBHOOK_URL, json=data, headers=headers, timeout=3
        )
        logger.info(
            f"📨 Ответ от JivoChat: статус={response.status_code}, тело={response.text}"
        )
        if response.status_code == 200:
            logger.info("✅ Ответ успешно отправлен в JivoChat")
        else:
            logger.error(
                f"⚠️ Ошибка при отправке в JivoChat: {response.status_code} - {response.text}"
            )
    except Exception as e:
        logger.error(f"❌ Ошибка при подключении к JivoChat: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
