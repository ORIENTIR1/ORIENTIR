@app.route('/mygpttoken123', methods=['POST'])
def handle_request():
    logger.info(f"Получен запрос от Jivo: {request.json}")
    try:
        data = request.json
        user_message = data.get('message', data.get('text', ''))
        chat_id = data.get('chat_id', '')
        if not user_message:
            return jsonify({"error": "Нет сообщения в запросе"}), 400

        response_message = f"Эхо: {user_message}"
        send_response_to_jivochat(response_message, chat_id)
        return jsonify({"message": response_message}), 200
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        return jsonify({"error": str(e)}), 500
