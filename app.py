from flask import Flask, request, jsonify, Response
import json

app = Flask(__name__)

BOT_TOKEN = 'mygpttoken123'  # Токен, который укажем на Render

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def jivo_webhook():
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({"error": "Нет сообщения"}), 400

    # 📝 Тестовый ответ с правильной кодировкой
    bot_reply = f"🤖 Бот получил сообщение: '{user_message}' и готов помочь!"

    response_data = {"message": bot_reply}
    return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
