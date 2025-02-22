import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
from flask import Flask, jsonify, request
import openai
import os
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
AGENT_ID = os.getenv("AGENT_ID", None)  # Если агент уже создан, используем его ID
JIVOCHAT_WEBHOOK_URL = os.getenv("JIVOCHAT_WEBHOOK_URL", "https://bot.jivosite.com/webhooks/WEVYtVZzXuYaG3/mygpttoken123")

# Создаем или получаем агента OpenAI при запуске (если AGENT_ID не задан)
if not AGENT_ID:
    def create_agent():
        response = openai.beta.assistants.create(
            name="Менеджер по продажам сувенирной продукции",
            instructions="""
Ты — менеджер по продажам брендированной сувенирной продукции.  
ВАЖНО: Твоя задача поэтапно выполнять действия, задавать вопросы в виде интервью и переходить к следующему шагу только после ответа клиента.
Твои действия:
1. Проверить с какого сайта и страницы зашел клиент.
2. Уточни интересующий продукт, тираж и необходимость брендирования.
3. Спроси, какой предполагаемый бюджет на 1 подарок
4. Спроси, есть ли логотип или готовый макет для расчета.
5. Предложи удобный способ получения расчета и попроси контакты.
Общайся вежливо, профессионально, с ориентацией на выявление потребностей клиента. Все взаимодействие должно опираться на методики из книги Скрипты продаж. Готовые сценарии холодных звонков и личных встреч Дмитрия Ткаченко. 
Если клиент просит визуализацию - бери информацию и фотографии только с сайта, на котором клиент находится и обратился к тебе.
""",
            tools=[{"type": "code_interpreter"}],
            model="gpt-4o"
        )
        return response.id

    # Создаем агента при запуске, если AGENT_ID не указан
    AGENT_ID = os.getenv("AGENT_ID", create_agent())
    logger.info(f"Используется агент с ID: {AGENT_ID}")

@app.route('/', methods=['GET'])
def index():
    """Проверка, что сервис работает."""
    return jsonify({"message": "Сервис работает! 🟢"}), 200

@app.route('/mygpttoken123', methods=['POST'])  # Убрал GET, так как Jivo использует только POST
def handle_request():
    """Обработка запросов от JivoChat с использованием OpenAI."""
    logger.info(f"Получен запрос на /mygpttoken123: URL={request.url}, Data={request.json}")
    try:
        data = request.json
        logger.info(f"Полученные данные от Jivo: {data}")

        # Проверка обязательных полей
        event = data.get('event', '')
        chat_id = data.get('chat_id', '')
        client_id = data.get('client_id', '')
        user_message = data.get('message', {}).get('text', data.get('text', ''))
        if not user_message or not chat_id or event != 'CLIENT_MESSAGE':
            return jsonify({"error": {"code": "invalid_request", "message": "Некорректный запрос от Jivo"}}), 400

        logger.info("Создание потока в OpenAI...")
        # Создаем поток без assistant_id
        thread = openai.beta.threads.create(
            messages=[{"role": "user", "content": user_message}]
        )

        # Запускаем выполнение с ассистентом
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=AGENT_ID
        )

        # Ожидание завершения с тайм-аутом (3 секунды для соответствия Jivo)
        max_wait_time = 3  # Уменьшаем до 3 секунд, как указано в документации
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status == "completed":
                break
            time.sleep(0.5)  # Уменьшаем задержку для скорости

        if run_status.status != "completed":
            return jsonify({"error": {"code": "timeout", "message": "Превышено время ожидания ответа от OpenAI"}}), 504

        # Получаем ответ от OpenAI
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        response_message = messages.data[0].content[0].text.value if messages.data else "Нет ответа от OpenAI."

        # Отправляем ответ в JivoChat
        send_response_to_jivochat(response_message, chat_id, client_id)

        logger.info(f"Ответ отправлен: {response_message}")
        return jsonify({"message": response_message}), 200

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {str(e)}")
        return jsonify({"error": {"code": "server_error", "message": str(e)}}), 500

def send_response_to_jivochat(response_message, chat_id, client_id):
    """Отправка ответа обратно в JivoChat через webhook."""
    if not JIVOCHAT_WEBHOOK_URL:
        logger.warning("JIVOCHAT_WEBHOOK_URL не настроен, ответ не отправлен")
        return

    headers = {'Content-Type': 'application/json'}
    data = {
        "id": str(uuid.uuid4()),  # Уникальный идентификатор события
        "event": "BOT_MESSAGE",
        "client_id": client_id,
        "chat_id": chat_id,
        "message": {
            "type": "TEXT",
            "text": response_message,
            "timestamp": int(time.time())
        }
    }

    try:
        logger.info(f"Отправка ответа в JivoChat на URL: {JIVOCHAT_WEBHOOK_URL}, Данные: {data}")
        response = requests.post(JIVOCHAT_WEBHOOK_URL, json=data, headers=headers, timeout=3)  # Тайм-аут 3 секунды
        logger.info(f"Ответ от JivoChat: статус={response.status_code}, тело={response.text}")
        if response.status_code == 200:
            logger.info("✅ Ответ успешно отправлен в JivoChat")
        else:
            logger.error(f"⚠️ Ошибка при отправке в JivoChat: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка при подключении к JivoChat: {str(e)}")

if __name__ == '__main__':
    # Запуск приложения на указанном порту (для локального теста)
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
