#!/usr/bin/env python3
"""
Простой локальный сервер для Ollama чата с инструментами
Запуск: python local_server.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов

# Файл для хранения данных
DATA_FILE = 'submissions.json'

def load_data():
    """Загружает данные из файла"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_data(data):
    """Сохраняет данные в файл"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

@app.route('/')
def index():
    """Главная страница - Ollama чат"""
    return send_from_directory('.', 'ollama-chat.html')

@app.route('/form')
def form_page():
    """Страница с формой"""
    return send_from_directory('.', 'index3.html')

@app.route('/api/submit', methods=['POST'])
def submit_data():
    """Обработка отправки формы"""
    try:
        # Получаем данные из запроса
        data = request.get_json()
        
        # Проверяем обязательные поля
        required_fields = ['name', 'email', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Поле "{field}" обязательно для заполнения'}), 400
        
        # Добавляем временную метку
        data['timestamp'] = datetime.now().isoformat()
        data['id'] = len(load_data()) + 1
        
        # Загружаем существующие данные
        submissions = load_data()
        
        # Добавляем новую запись
        submissions.append(data)
        
        # Сохраняем данные
        if save_data(submissions):
            return jsonify({
                'message': f'Данные успешно сохранены! ID: {data["id"]}',
                'id': data['id']
            }), 200
        else:
            return jsonify({'error': 'Ошибка при сохранении данных'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500

# Tools API для работы с файлами
@app.route('/api/tools', methods=['POST'])
def execute_tool():
    """Выполнение инструментов для работы с файлами"""
    try:
        data = request.get_json()
        tool_name = data.get('tool')
        parameters = data.get('parameters', {})
        
        # Получаем текущую директорию
        current_dir = os.getcwd()
        
        if tool_name == 'create_file':
            filename = parameters.get('filename')
            content = parameters.get('content', '')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Безопасность: проверяем путь
            safe_path = os.path.join(current_dir, filename)
            if not safe_path.startswith(current_dir):
                return jsonify({'error': 'Недопустимый путь к файлу'}), 400
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return jsonify({'result': f'Файл {filename} создан успешно'})
        
        elif tool_name == 'read_file':
            filename = parameters.get('filename')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            safe_path = os.path.join(current_dir, filename)
            if not safe_path.startswith(current_dir):
                return jsonify({'error': 'Недопустимый путь к файлу'}), 400
            
            if not os.path.exists(safe_path):
                return jsonify({'error': f'Файл {filename} не найден'}), 404
            
            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return jsonify({'result': f'Содержимое файла {filename}:\n{content}'})
        
        elif tool_name == 'create_directory':
            dirname = parameters.get('dirname')
            
            if not dirname:
                return jsonify({'error': 'Не указано имя папки'}), 400
            
            safe_path = os.path.join(current_dir, dirname)
            if not safe_path.startswith(current_dir):
                return jsonify({'error': 'Недопустимый путь к папке'}), 400
            
            os.makedirs(safe_path, exist_ok=True)
            
            return jsonify({'result': f'Папка {dirname} создана успешно'})
        
        elif tool_name == 'list_files':
            path = parameters.get('path', current_dir)
            
            if not path.startswith(current_dir):
                path = current_dir
            
            if not os.path.exists(path):
                return jsonify({'error': f'Путь {path} не найден'}), 404
            
            files = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path):
                    files.append(f'📄 {item}')
                elif os.path.isdir(item_path):
                    files.append(f'📁 {item}/')
            
            files_list = '\n'.join(files) if files else 'Папка пуста'
            return jsonify({'result': f'Содержимое {path}:\n{files_list}'})
        
        elif tool_name == 'delete_file':
            filename = parameters.get('filename')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            safe_path = os.path.join(current_dir, filename)
            if not safe_path.startswith(current_dir):
                return jsonify({'error': 'Недопустимый путь к файлу'}), 400
            
            if not os.path.exists(safe_path):
                return jsonify({'error': f'Файл {filename} не найден'}), 404
            
            os.remove(safe_path)
            
            return jsonify({'result': f'Файл {filename} удален успешно'})
        
        else:
            return jsonify({'error': f'Неизвестный инструмент: {tool_name}'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Ошибка выполнения инструмента: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({
        'status': 'OK',
        'message': 'Сервер работает нормально',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.errorhandler(404)
def not_found(error):
    """Обработчик ошибки 404"""
    return jsonify({'error': 'Страница не найдена'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработчик ошибки 500"""
    return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

if __name__ == '__main__':
    print("🚀 Запуск локального сервера...")
    print("🌐 Ollama чат доступен по адресу: http://localhost:5000")
    print("📝 Форма доступна по адресу: http://localhost:5000/form")
    print("🔧 API endpoints:")
    print("   GET  /                     - Ollama чат с инструментами")
    print("   GET  /form                 - Форма")
    print("   POST /api/submit           - Отправка формы")
    print("   POST /api/tools            - Выполнение инструментов")
    print("   GET  /api/health           - Проверка работоспособности")
    print("\n💡 Убедитесь, что Ollama запущен на localhost:11434")
    
    app.run(host='0.0.0.0', port=5000, debug=True)