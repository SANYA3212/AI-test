from flask import Flask, request, jsonify, send_from_directory, Response
import os
import json
import requests
import subprocess
import platform
import signal
import time
import threading
import psutil
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
        
        # Получаем сообщение пользователя
        user_message = data.get('message', '')
        tools_enabled = data.get('tools_enabled', False)
        
        if "history" in data:
            messages = data["history"]
        else:
            messages = data.get('messages', [])
        
        # Если есть новое сообщение пользователя, добавляем его
        if user_message:
            messages.append({"role": "user", "content": user_message})
        
        # Если включены инструменты, добавляем их в системное сообщение
        if tools_enabled:
            system_message = {
                "role": "system", 
                "content": """Ты AI ассистент с доступом к системным инструментам. У тебя есть следующие инструменты:

📁 Файловая система:
- list_files: просмотр содержимого папок
- read_file: чтение файлов
- create_file: создание файлов
- edit_file: редактирование файлов
- delete_file: удаление файлов
- create_directory: создание папок

💻 Системное управление:
- execute_command: выполнение команд
- get_system_info: информация о системе
- manage_processes: управление процессами
- network_info: информация о сети

Когда пользователь просит выполнить действие, используй соответствующий инструмент. Отвечай на русском языке."""
            }
            # Вставляем системное сообщение в начало, если его еще нет
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, system_message)
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m"
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
@app.route('/tools', methods=['POST'])
def execute_tool():
    """Выполнение инструментов для работы с файлами"""
    try:
        data = request.get_json()
        tool_name = data.get('tool_name') or data.get('tool')  # Поддержка обоих форматов
        parameters = data.get('parameters', {})
        
        print(f"[DEBUG] Tool request: {tool_name} with parameters: {parameters}")
        
        if tool_name == 'list_drives':
            """Показать все доступные диски в системе"""
            drives = []
            
            if platform.system() == 'Windows':
                import string
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        try:
                            # Проверяем доступность диска
                            os.listdir(drive)
                            drives.append(f"💾 {drive}")
                        except (PermissionError, OSError):
                            drives.append(f"🔒 {drive} (нет доступа)")
            else:
                # Unix-подобные системы
                drives.append("💾 / (корневая файловая система)")
                # Добавляем популярные точки монтирования
                mount_points = ['/mnt', '/media', '/Volumes', '/home', '/usr', '/var', '/tmp']
                for mount in mount_points:
                    if os.path.exists(mount) and os.path.isdir(mount):
                        drives.append(f"📁 {mount}")
            
            drives_list = '\n'.join(drives) if drives else 'Диски не найдены'
            return jsonify({'result': f'Доступные диски и основные папки:\n{drives_list}'})
        
        elif tool_name == 'create_file':
            filename = parameters.get('filename')
            content = parameters.get('content', '')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.abspath(filename)
            
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
                filename = os.path.abspath(filename)
            
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
                dirname = os.path.abspath(dirname)
            
            os.makedirs(dirname, exist_ok=True)
            
            return jsonify({'result': f'Папка {dirname} создана успешно'})
        
        elif tool_name == 'list_files':
            path = parameters.get('path')
            
            print(f"[DEBUG] list_files called with path: {path}")
            
            # Если путь не указан, используем корень системы
            if not path:
                if platform.system() == 'Windows':
                    path = 'C:\\'
                else:
                    path = '/'
            
            print(f"[DEBUG] Using path: {path}")
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            
            # Нормализуем путь для Windows
            path = os.path.normpath(path)
            
            # Специальная обработка для корневых дисков Windows
            if platform.system() == 'Windows' and len(path) == 2 and path[1] == ':':
                path = path + '\\'
            
            print(f"[DEBUG] Final path: {path}")
            
            if not os.path.exists(path):
                return jsonify({'error': f'Путь {path} не найден'}), 404
            
            if not os.path.isdir(path):
                return jsonify({'error': f'{path} не является папкой'}), 400
            
            files = []
            try:
                print(f"[DEBUG] Starting to list directory: {path}")
                
                # Добавляем родительскую папку если не в корне
                parent_path = os.path.dirname(path)
                if parent_path != path:  # Не в корне
                    files.append('📁 .. (родительская папка)')
                
                print(f"[DEBUG] About to call os.listdir({path})")
                
                # Ограничиваем количество файлов для корневых директорий
                items = os.listdir(path)
                if path == '/' or path == 'C:\\':
                    items = items[:20]  # Показываем только первые 20 элементов для корня
                
                print(f"[DEBUG] Got {len(items)} items")
                
                for item in items:
                    item_path = os.path.join(path, item)
                    try:
                        if os.path.isfile(item_path):
                            size = os.path.getsize(item_path)
                            # Форматируем размер файла
                            if size < 1024:
                                size_str = f"{size} B"
                            elif size < 1024*1024:
                                size_str = f"{size/1024:.1f} KB"
                            elif size < 1024*1024*1024:
                                size_str = f"{size/(1024*1024):.1f} MB"
                            else:
                                size_str = f"{size/(1024*1024*1024):.1f} GB"
                            files.append(f'📄 {item} ({size_str})')
                        elif os.path.isdir(item_path):
                            files.append(f'📁 {item}/')
                    except (PermissionError, OSError):
                        files.append(f'🔒 {item} (нет доступа)')
                
                files_list = '\n'.join(files) if files else 'Папка пуста'
                
                # Добавляем информацию о текущем пути
                result_text = f'📍 Текущий путь: {path}\n'
                result_text += f'📊 Всего элементов: {len(files)}\n'
                result_text += '─' * 50 + '\n'
                result_text += files_list
                
                print(f"[DEBUG] Returning result for {path}")
                return jsonify({'result': result_text, 'current_path': path, 'items': files})
            except PermissionError:
                print(f"[DEBUG] Permission error for {path}")
                return jsonify({'error': f'Нет доступа к папке {path}'}), 403
            except Exception as e:
                print(f"[DEBUG] Exception in list_files: {e}")
                return jsonify({'error': f'Ошибка при чтении папки {path}: {str(e)}'}), 500
        
        elif tool_name == 'delete_file':
            filename = parameters.get('filename')
            
            if not filename:
                return jsonify({'error': 'Не указано имя файла'}), 400
            
            # Поддержка абсолютных и относительных путей
            if not os.path.isabs(filename):
                filename = os.path.abspath(filename)
            
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
                filename = os.path.abspath(filename)
            
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
        
        elif tool_name == 'execute_command':
            command = parameters.get('command')
            
            if not command:
                return jsonify({'error': 'Не указана команда для выполнения'}), 400
            
            try:
                # Выполняем команду в зависимости от ОС
                if platform.system() == 'Windows':
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                else:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                
                output = result.stdout if result.stdout else result.stderr
                return_code = result.returncode
                
                return jsonify({
                    'result': f'Команда выполнена (код возврата: {return_code})\nВывод:\n{output}',
                    'return_code': return_code,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                })
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'Команда превысила лимит времени выполнения (30 сек)'}), 408
            except Exception as e:
                return jsonify({'error': f'Ошибка выполнения команды: {str(e)}'}), 500
        
        elif tool_name == 'run_application':
            app_path = parameters.get('app_path')
            app_name = parameters.get('app_name')
            arguments = parameters.get('arguments', '')
            
            if not app_path and not app_name:
                return jsonify({'error': 'Не указан путь к приложению или имя приложения'}), 400
            
            try:
                if app_path:
                    # Запуск по полному пути
                    if platform.system() == 'Windows':
                        subprocess.Popen([app_path] + arguments.split() if arguments else [app_path])
                    else:
                        subprocess.Popen([app_path] + arguments.split() if arguments else [app_path])
                    return jsonify({'result': f'Приложение {app_path} запущено успешно'})
                else:
                    # Запуск по имени (поиск в PATH)
                    if platform.system() == 'Windows':
                        subprocess.Popen([app_name] + arguments.split() if arguments else [app_name], shell=True)
                    else:
                        subprocess.Popen([app_name] + arguments.split() if arguments else [app_name])
                    return jsonify({'result': f'Приложение {app_name} запущено успешно'})
            except FileNotFoundError:
                return jsonify({'error': f'Приложение не найдено: {app_path or app_name}'}), 404
            except Exception as e:
                return jsonify({'error': f'Ошибка запуска приложения: {str(e)}'}), 500
        
        elif tool_name == 'get_system_info':
            try:
                # Получаем информацию о системе
                system_info = {
                    'os': platform.system(),
                    'os_version': platform.version(),
                    'architecture': platform.architecture()[0],
                    'processor': platform.processor(),
                    'hostname': platform.node(),
                    'python_version': platform.python_version(),
                    'cpu_count': psutil.cpu_count(),
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_total': f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                    'memory_available': f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_usage': []
                }
                
                # Информация о дисках
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        system_info['disk_usage'].append({
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total': f"{usage.total / (1024**3):.2f} GB",
                            'used': f"{usage.used / (1024**3):.2f} GB",
                            'free': f"{usage.free / (1024**3):.2f} GB",
                            'percent': f"{(usage.used / usage.total) * 100:.1f}%"
                        })
                    except PermissionError:
                        continue
                
                info_text = f"""Информация о системе:
ОС: {system_info['os']} {system_info['os_version']}
Архитектура: {system_info['architecture']}
Процессор: {system_info['processor']}
Имя компьютера: {system_info['hostname']}
Python: {system_info['python_version']}

Ресурсы:
CPU: {system_info['cpu_count']} ядер, загрузка {system_info['cpu_percent']}%
Память: {system_info['memory_available']} доступно из {system_info['memory_total']} ({system_info['memory_percent']}% используется)

Диски:"""
                
                for disk in system_info['disk_usage']:
                    info_text += f"\n{disk['device']} ({disk['fstype']}): {disk['used']} из {disk['total']} ({disk['percent']})"
                
                return jsonify({'result': info_text, 'data': system_info})
            except Exception as e:
                return jsonify({'error': f'Ошибка получения информации о системе: {str(e)}'}), 500
        
        elif tool_name == 'manage_processes':
            action = parameters.get('action')  # 'list', 'kill', 'info'
            process_name = parameters.get('process_name')
            process_id = parameters.get('process_id')
            
            if not action:
                return jsonify({'error': 'Не указано действие (list, kill, info)'}), 400
            
            try:
                if action == 'list':
                    processes = []
                    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                        try:
                            processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cpu_percent': proc.info['cpu_percent'],
                                'memory_percent': proc.info['memory_percent']
                            })
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    # Сортируем по использованию CPU
                    processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
                    
                    result_text = "Список процессов (топ 20 по CPU):\n"
                    for proc in processes[:20]:
                        result_text += f"PID: {proc['pid']}, Имя: {proc['name']}, CPU: {proc['cpu_percent']:.1f}%, Память: {proc['memory_percent']:.1f}%\n"
                    
                    return jsonify({'result': result_text, 'processes': processes[:20]})
                
                elif action == 'kill':
                    if not process_id and not process_name:
                        return jsonify({'error': 'Не указан ID или имя процесса для завершения'}), 400
                    
                    killed_processes = []
                    
                    if process_id:
                        try:
                            proc = psutil.Process(int(process_id))
                            proc_name = proc.name()
                            proc.terminate()
                            killed_processes.append(f"PID {process_id} ({proc_name})")
                        except psutil.NoSuchProcess:
                            return jsonify({'error': f'Процесс с PID {process_id} не найден'}), 404
                        except psutil.AccessDenied:
                            return jsonify({'error': f'Нет прав для завершения процесса PID {process_id}'}), 403
                    
                    if process_name:
                        for proc in psutil.process_iter(['pid', 'name']):
                            try:
                                if proc.info['name'].lower() == process_name.lower():
                                    proc.terminate()
                                    killed_processes.append(f"PID {proc.info['pid']} ({proc.info['name']})")
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    
                    if killed_processes:
                        return jsonify({'result': f'Завершены процессы: {", ".join(killed_processes)}'})
                    else:
                        return jsonify({'error': f'Процессы с именем "{process_name}" не найдены или нет прав доступа'}), 404
                
                elif action == 'info':
                    if not process_id and not process_name:
                        return jsonify({'error': 'Не указан ID или имя процесса для получения информации'}), 400
                    
                    target_proc = None
                    
                    if process_id:
                        try:
                            target_proc = psutil.Process(int(process_id))
                        except psutil.NoSuchProcess:
                            return jsonify({'error': f'Процесс с PID {process_id} не найден'}), 404
                    elif process_name:
                        for proc in psutil.process_iter(['pid', 'name']):
                            try:
                                if proc.info['name'].lower() == process_name.lower():
                                    target_proc = psutil.Process(proc.info['pid'])
                                    break
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    
                    if not target_proc:
                        return jsonify({'error': f'Процесс "{process_name}" не найден'}), 404
                    
                    try:
                        proc_info = {
                            'pid': target_proc.pid,
                            'name': target_proc.name(),
                            'status': target_proc.status(),
                            'cpu_percent': target_proc.cpu_percent(),
                            'memory_percent': target_proc.memory_percent(),
                            'create_time': time.ctime(target_proc.create_time()),
                            'num_threads': target_proc.num_threads(),
                        }
                        
                        try:
                            proc_info['exe'] = target_proc.exe()
                            proc_info['cwd'] = target_proc.cwd()
                            proc_info['cmdline'] = ' '.join(target_proc.cmdline())
                        except psutil.AccessDenied:
                            proc_info['exe'] = 'Нет доступа'
                            proc_info['cwd'] = 'Нет доступа'
                            proc_info['cmdline'] = 'Нет доступа'
                        
                        info_text = f"""Информация о процессе:
PID: {proc_info['pid']}
Имя: {proc_info['name']}
Статус: {proc_info['status']}
CPU: {proc_info['cpu_percent']:.1f}%
Память: {proc_info['memory_percent']:.1f}%
Время создания: {proc_info['create_time']}
Потоков: {proc_info['num_threads']}
Исполняемый файл: {proc_info['exe']}
Рабочая папка: {proc_info['cwd']}
Командная строка: {proc_info['cmdline']}"""
                        
                        return jsonify({'result': info_text, 'process_info': proc_info})
                    except psutil.AccessDenied:
                        return jsonify({'error': 'Нет прав доступа к информации о процессе'}), 403
                
                else:
                    return jsonify({'error': f'Неизвестное действие: {action}'}), 400
                    
            except Exception as e:
                return jsonify({'error': f'Ошибка управления процессами: {str(e)}'}), 500
        
        elif tool_name == 'network_info':
            try:
                network_info = {
                    'interfaces': [],
                    'connections': []
                }
                
                # Информация о сетевых интерфейсах
                for interface, addrs in psutil.net_if_addrs().items():
                    interface_info = {'name': interface, 'addresses': []}
                    for addr in addrs:
                        interface_info['addresses'].append({
                            'family': str(addr.family),
                            'address': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
                    network_info['interfaces'].append(interface_info)
                
                # Активные сетевые соединения
                for conn in psutil.net_connections(kind='inet')[:10]:  # Ограничиваем до 10
                    try:
                        network_info['connections'].append({
                            'fd': conn.fd,
                            'family': str(conn.family),
                            'type': str(conn.type),
                            'local_address': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                            'remote_address': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                            'status': conn.status,
                            'pid': conn.pid
                        })
                    except:
                        continue
                
                result_text = "Сетевая информация:\n\nИнтерфейсы:\n"
                for iface in network_info['interfaces']:
                    result_text += f"{iface['name']}:\n"
                    for addr in iface['addresses']:
                        result_text += f"  {addr['address']} ({addr['family']})\n"
                
                result_text += "\nАктивные соединения (топ 10):\n"
                for conn in network_info['connections']:
                    result_text += f"{conn['local_address']} -> {conn['remote_address']} ({conn['status']})\n"
                
                return jsonify({'result': result_text, 'network_data': network_info})
            except Exception as e:
                return jsonify({'error': f'Ошибка получения сетевой информации: {str(e)}'}), 500
        
        elif tool_name == 'manage_services':
            action = parameters.get('action')  # 'list', 'start', 'stop', 'restart', 'status'
            service_name = parameters.get('service_name')
            
            if not action:
                return jsonify({'error': 'Не указано действие (list, start, stop, restart, status)'}), 400
            
            try:
                if action == 'list':
                    if platform.system() == 'Windows':
                        result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=30)
                        return jsonify({'result': f'Список служб Windows:\n{result.stdout}'})
                    else:
                        result = subprocess.run(['systemctl', 'list-units', '--type=service'], capture_output=True, text=True, timeout=30)
                        return jsonify({'result': f'Список служб Linux:\n{result.stdout}'})
                
                elif action in ['start', 'stop', 'restart', 'status']:
                    if not service_name:
                        return jsonify({'error': 'Не указано имя службы'}), 400
                    
                    if platform.system() == 'Windows':
                        if action == 'start':
                            result = subprocess.run(['sc', 'start', service_name], capture_output=True, text=True, timeout=30)
                        elif action == 'stop':
                            result = subprocess.run(['sc', 'stop', service_name], capture_output=True, text=True, timeout=30)
                        elif action == 'status':
                            result = subprocess.run(['sc', 'query', service_name], capture_output=True, text=True, timeout=30)
                        elif action == 'restart':
                            subprocess.run(['sc', 'stop', service_name], capture_output=True, text=True, timeout=30)
                            time.sleep(2)
                            result = subprocess.run(['sc', 'start', service_name], capture_output=True, text=True, timeout=30)
                    else:
                        result = subprocess.run(['systemctl', action, service_name], capture_output=True, text=True, timeout=30)
                    
                    return jsonify({
                        'result': f'Действие "{action}" для службы "{service_name}":\n{result.stdout}\n{result.stderr}',
                        'return_code': result.returncode
                    })
                
                else:
                    return jsonify({'error': f'Неизвестное действие: {action}'}), 400
                    
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'Команда превысила лимит времени выполнения'}), 408
            except Exception as e:
                return jsonify({'error': f'Ошибка управления службами: {str(e)}'}), 500
        
        elif tool_name == 'file_operations':
            operation = parameters.get('operation')  # 'copy', 'move', 'search', 'permissions'
            source = parameters.get('source')
            destination = parameters.get('destination')
            pattern = parameters.get('pattern')
            
            if not operation:
                return jsonify({'error': 'Не указана операция (copy, move, search, permissions)'}), 400
            
            try:
                if operation == 'copy':
                    if not source or not destination:
                        return jsonify({'error': 'Не указан источник или назначение'}), 400
                    
                    source = os.path.abspath(source)
                    destination = os.path.abspath(destination)
                    
                    if os.path.isfile(source):
                        import shutil
                        shutil.copy2(source, destination)
                        return jsonify({'result': f'Файл скопирован: {source} -> {destination}'})
                    elif os.path.isdir(source):
                        import shutil
                        shutil.copytree(source, destination)
                        return jsonify({'result': f'Папка скопирована: {source} -> {destination}'})
                    else:
                        return jsonify({'error': f'Источник не найден: {source}'}), 404
                
                elif operation == 'move':
                    if not source or not destination:
                        return jsonify({'error': 'Не указан источник или назначение'}), 400
                    
                    source = os.path.abspath(source)
                    destination = os.path.abspath(destination)
                    
                    import shutil
                    shutil.move(source, destination)
                    return jsonify({'result': f'Перемещено: {source} -> {destination}'})
                
                elif operation == 'search':
                    if not source or not pattern:
                        return jsonify({'error': 'Не указан путь поиска или шаблон'}), 400
                    
                    source = os.path.abspath(source)
                    found_files = []
                    
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            if pattern.lower() in file.lower():
                                found_files.append(os.path.join(root, file))
                        if len(found_files) >= 50:  # Ограничиваем результаты
                            break
                    
                    result_text = f"Найдено файлов с шаблоном '{pattern}' в {source}:\n"
                    result_text += '\n'.join(found_files[:50])
                    if len(found_files) >= 50:
                        result_text += f"\n... и еще {len(found_files) - 50} файлов"
                    
                    return jsonify({'result': result_text, 'found_files': found_files[:50]})
                
                elif operation == 'permissions':
                    if not source:
                        return jsonify({'error': 'Не указан путь к файлу'}), 400
                    
                    source = os.path.abspath(source)
                    
                    if not os.path.exists(source):
                        return jsonify({'error': f'Файл не найден: {source}'}), 404
                    
                    stat_info = os.stat(source)
                    permissions = oct(stat_info.st_mode)[-3:]
                    
                    result_text = f"Права доступа для {source}:\n"
                    result_text += f"Восьмеричное представление: {permissions}\n"
                    result_text += f"Размер: {stat_info.st_size} байт\n"
                    result_text += f"Последнее изменение: {time.ctime(stat_info.st_mtime)}\n"
                    result_text += f"Последний доступ: {time.ctime(stat_info.st_atime)}"
                    
                    return jsonify({'result': result_text, 'permissions': permissions, 'size': stat_info.st_size})
                
                else:
                    return jsonify({'error': f'Неизвестная операция: {operation}'}), 400
                    
            except Exception as e:
                return jsonify({'error': f'Ошибка файловой операции: {str(e)}'}), 500
        
        else:
            return jsonify({'error': f'Неизвестный инструмент: {tool_name}'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Ошибка выполнения инструмента: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Запуск сервера с поддержкой Ollama Tools...")
    print("🌐 Ollama чат доступен по адресу: http://localhost:12000")
    print("🔧 Поддерживаемые инструменты:")
    print("   📁 Файловая система:")
    print("      - list_drives: просмотр всех дисков в системе")
    print("      - create_file: создание файлов (поддержка абсолютных путей)")
    print("      - read_file: чтение файлов (любые файлы на компьютере)")
    print("      - edit_file: редактирование файлов (с резервной копией)")
    print("      - create_directory: создание папок")
    print("      - list_files: просмотр содержимого папок (с навигацией)")
    print("      - delete_file: удаление файлов и папок")
    print("   💻 Системное управление:")
    print("      - execute_command: выполнение системных команд")
    print("      - run_application: запуск приложений")
    print("      - get_system_info: информация о системе")
    print("      - manage_processes: управление процессами (list/kill/info)")
    print("      - network_info: информация о сети")
    print("      - manage_services: управление службами (list/start/stop/restart/status)")
    print("      - file_operations: расширенные файловые операции (copy/move/search/permissions)")
    print("\n💡 Убедитесь, что Ollama запущен на localhost:11434")
    print("⚠️  ВНИМАНИЕ: AI имеет ПОЛНЫЙ доступ к вашему компьютеру!")
    print("🗂️  Может читать/изменять файлы, запускать программы, управлять процессами")
    print("🔒 Используйте только с доверенными AI моделями!")
    
    app.run(host='0.0.0.0', port=12000, debug=False, threaded=True)
