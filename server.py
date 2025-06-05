from flask import Flask, request, jsonify, send_from_directory, Response
import os
import json
import requests
import subprocess
from threading import Lock
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

 
CHATS_DIR = "chats"
os.makedirs(CHATS_DIR, exist_ok=True)

LAST_MODEL_FILE = 'last_model.txt'
SETTINGS_FILE = 'settings.json'

 
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except json.decoder.JSONDecodeError:
        settings = {"language": "en", "default_model": ""}
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
else:
    settings = {"language": "en", "default_model": ""}
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

current_model = settings.get("default_model", "")
model_lock = Lock()

 
OLLAMA_API = "http://localhost:11434"

 
if os.path.exists(LAST_MODEL_FILE):
    with open(LAST_MODEL_FILE, 'r', encoding='utf-8') as f:
        current_model = f.read().strip()

app.logger.info("Current model: %s", current_model)

@app.route('/')
def index():
    return send_from_directory('.', 'index3.html')

@app.route('/chats', methods=['GET'])
def list_chats():
    try:
        chats = [f.replace(".json", "") for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
        return jsonify(chats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chats/<chat_id>', methods=['GET', 'PUT'])
def chat_handler(chat_id):
     
     
    chat_file = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if request.method == 'GET':
        try:
            if os.path.exists(chat_file):
                with open(chat_file, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                return jsonify(chat_data)
            else:
                return jsonify({"error": "Chat not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            data = request.json
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/delete-chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
     
    chat_file = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(chat_file):
        try:
            os.remove(chat_file)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Chat not found"}), 404

@app.route('/generate', methods=['POST'])
def generate():
     
    try:
        data = request.json
        if "modelhs" in data:
            model = data["modelhs"][-1] if data["modelhs"] else current_model
        else:
            model = data.get('model', current_model)
        if "history" in data:
            messages = data["history"]
        else:
            messages = data.get('messages', [])
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        resp = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=120)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate-stream', methods=['POST'])
def generate_stream():
     
    try:
        data = request.json
        if "modelhs" in data:
            model = data["modelhs"][-1] if data["modelhs"] else current_model
        else:
            model = data.get('model', current_model)
        if "history" in data:
            messages = data["history"]
        else:
            messages = data.get('messages', [])
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        resp = requests.post(f"{OLLAMA_API}/api/chat", json=payload, stream=True, timeout=120)
        def generate():
            for line in resp.iter_lines():
                if line:
                    yield f"data: {line.decode('utf-8')}\n\n"
        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/switch-model', methods=['POST'])
def switch_model():
     
    global current_model
    try:
        data = request.json
        model = data.get('model', '')
        with model_lock:
            current_model = model
            with open(LAST_MODEL_FILE, 'w', encoding='utf-8') as f:
                f.write(model)
        return jsonify({"status": "success", "model": model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/installed-models', methods=['GET'])
def get_installed_models():
     
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
        output = result.stdout.strip()
        lines = output.splitlines()
        if lines and "NAME" in lines[0].upper():
            lines = lines[1:]
        models = [line.strip().split()[0] for line in lines if line.strip()]
        return jsonify(models)
    except Exception as e:
        app.logger.error("Error syncing with ollama list: %s", e)
        return jsonify([])

@app.route('/delete-model', methods=['POST'])
def delete_model():
     
    data = request.json
    model = data.get('model')
    try:
        result = subprocess.run(["ollama", "rm", model], capture_output=True, text=True)
        if result.returncode != 0:
            app.logger.error("Error deleting model: %s", result.stderr)
            return jsonify({"status": "error", "message": result.stderr}), 500
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error("Exception deleting model: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/install-model-stream', methods=['POST'])
def install_model_stream():
     
    data = request.json
    model_name = data.get("model")
    if not model_name:
        return jsonify({"error": "No model name provided"}), 400

    command = ["ollama", "run", model_name]
    app.logger.info("Installing model via command: %s", " ".join(command))

    def generate():
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ""):
            yield f"data: {line.strip()}\n\n"
        process.stdout.close()
        process.wait()
        yield "data: DONE\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/settings', methods=['GET', 'POST'])
def settings_handler():
     
    global settings, current_model
    if request.method == 'GET':
        return jsonify(settings)
    else:
        try:
            new_settings = request.json
            settings.update(new_settings)
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            if "default_model" in new_settings:
                current_model = new_settings["default_model"]
                with open(LAST_MODEL_FILE, 'w', encoding='utf-8') as f:
                    f.write(current_model)

            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# Tools API для работы с файлами
@app.route('/api/tools', methods=['POST'])
def execute_tool():
    """Выполнение инструментов для работы с файлами"""
    try:
        data = request.get_json()
        tool_name = data.get('tool')
        parameters = data.get('parameters', {})
        
        if tool_name == 'create_file':
            filename = parameters.get('filename')
            content = parameters.get('content', '')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.join(os.getcwd(), filename)
            
            # Создаем директории если их нет
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return jsonify({'result': f'Файл {filename} создан успешно'})
        
        elif tool_name == 'read_file':
            filename = parameters.get('filename')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.join(os.getcwd(), filename)
            
            if not os.path.exists(filename):
                return jsonify({'error': f'Файл {filename} не найден'}), 404
            
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({'result': f'Содержимое файла {filename}:\n{content}'})
            except UnicodeDecodeError:
                return jsonify({'error': f'Не удается прочитать файл {filename} (возможно, это бинарный файл)'}), 400
        
        elif tool_name == 'create_directory':
            dirname = parameters.get('dirname')
            
            if not dirname:
                return jsonify({'error': 'Не указано имя папки'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(dirname):
                dirname = os.path.join(os.getcwd(), dirname)
            
            os.makedirs(dirname, exist_ok=True)
            
            return jsonify({'result': f'Папка {dirname} создана успешно'})
        
        elif tool_name == 'list_files':
            path = parameters.get('path', os.getcwd())
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            
            if not os.path.exists(path):
                return jsonify({'error': f'Путь {path} не найден'}), 404
            
            if not os.path.isdir(path):
                return jsonify({'error': f'{path} не является папкой'}), 400
            
            files = []
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        files.append(f'📄 {item} ({size} bytes)')
                    elif os.path.isdir(item_path):
                        files.append(f'📁 {item}/')
                
                files_list = '\n'.join(files) if files else 'Папка пуста'
                return jsonify({'result': f'Содержимое {path}:\n{files_list}'})
            except PermissionError:
                return jsonify({'error': f'Нет доступа к папке {path}'}), 403
        
        elif tool_name == 'delete_file':
            filename = parameters.get('filename')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.join(os.getcwd(), filename)
            
            if not os.path.exists(filename):
                return jsonify({'error': f'Файл {filename} не найден'}), 404
            
            try:
                if os.path.isfile(filename):
                    os.remove(filename)
                    return jsonify({'result': f'Файл {filename} удален успешно'})
                elif os.path.isdir(filename):
                    import shutil
                    shutil.rmtree(filename)
                    return jsonify({'result': f'Папка {filename} удалена успешно'})
                else:
                    return jsonify({'error': f'{filename} не является файлом или папкой'}), 400
            except PermissionError:
                return jsonify({'error': f'Нет доступа для удаления {filename}'}), 403
        
        elif tool_name == 'edit_file':
            filename = parameters.get('filename')
            content = parameters.get('content', '')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.join(os.getcwd(), filename)
            
            if not os.path.exists(filename):
                return jsonify({'error': f'Файл {filename} не найден'}), 404
            
            if not os.path.isfile(filename):
                return jsonify({'error': f'{filename} не является файлом'}), 400
            
            try:
                # Создаем резервную копию
                backup_filename = filename + '.backup'
                import shutil
                shutil.copy2(filename, backup_filename)
                
                # Записываем новое содержимое
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return jsonify({'result': f'Файл {filename} отредактирован успешно (резервная копия: {backup_filename})'})
            except Exception as e:
                return jsonify({'error': f'Ошибка при редактировании файла: {str(e)}'}), 500
        
        else:
            return jsonify({'error': f'Неизвестный инструмент: {tool_name}'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Ошибка выполнения инструмента: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Запуск сервера с поддержкой Ollama Tools...")
    print("🌐 Ollama чат доступен по адресу: http://localhost:5000")
    print("🔧 Поддерживаемые инструменты:")
    print("   - create_file: создание файлов (поддержка абсолютных путей)")
    print("   - read_file: чтение файлов (любые файлы на компьютере)")
    print("   - edit_file: редактирование файлов (с резервной копией)")
    print("   - create_directory: создание папок")
    print("   - list_files: просмотр содержимого папок")
    print("   - delete_file: удаление файлов и папок")
    print("\n💡 Убедитесь, что Ollama запущен на localhost:11434")
    print("⚠️  Инструменты имеют доступ ко всей файловой системе!")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
