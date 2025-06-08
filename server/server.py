import os
import json
import time
import datetime
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import threading

import zlib  # 添加用于解压缩的库
import tempfile  # 添加用于临时文件处理
import shutil  # 添加用于文件处理
import base64  # 添加用于Base64编码处理

# 配置
app = Flask(__name__)
CORS(app)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 限制上传文件大小为100MB
app.config["SECRET_KEY"] = "family_cctv_secret_key"
app.config["STATIC_FOLDER"] = "static"  # 设置静态文件夹

# 默认自动清理配置
app.config["AUTO_CLEANUP_ENABLED"] = False  # 默认关闭自动清理
app.config["AUTO_CLEANUP_DAYS"] = 30  # 默认保留30天数据
app.config["AUTO_CLEANUP_INTERVAL"] = 24  # 默认每24小时执行一次清理
app.config["AUTO_CLEANUP_UNIT"] = "days"  # 新增：时间单位，支持 "days"、"hours"、"minutes"

# 后台实时捕获配置
app.config["BACKGROUND_CAPTURE_ENABLED"] = False  # 默认关闭后台实时捕获
app.config["BACKGROUND_CAPTURE_INTERVAL"] = 30  # 默认每30秒截图一次
app.config["BACKGROUND_CAPTURE_CLIENTS"] = {}  # 存储启用后台捕获的客户端配置

# 暂停配置文件路径
pause_config_file = os.path.join(app.config["UPLOAD_FOLDER"], "pause_config.json")



# 确保上传目录存在
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

# 创建元数据文件
metadata_file = os.path.join(app.config["UPLOAD_FOLDER"], "metadata.json")
if not os.path.exists(metadata_file):
    with open(metadata_file, "w") as f:
        json.dump({"clients": {}}, f)

# 创建客户端信息文件
clients_file = os.path.join(app.config["UPLOAD_FOLDER"], "clients.json")
if not os.path.exists(clients_file):
    with open(clients_file, "w") as f:
        json.dump({}, f)

# 初始化暂停配置文件
if not os.path.exists(pause_config_file):
    with open(pause_config_file, "w") as f:
        json.dump({}, f)

# 初始化验证配置文件
verification_config_file = os.path.join(app.config["UPLOAD_FOLDER"], "verification_config.json")
if not os.path.exists(verification_config_file):
    with open(verification_config_file, "w") as f:
        json.dump({}, f)

# 客户端命令队列 - 保存待执行的命令
# 格式: {client_id: [command1, command2, ...]}
client_commands = {}
command_results = {}
command_status = {}  # 格式: {command_id: {client_id, command, status, message, timestamp}}

# 加载暂停配置
def load_pause_config():
    try:
        with open(pause_config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载暂停配置错误: {str(e)}")
        return {}

# 保存暂停配置
def save_pause_config(configs):
    try:
        with open(pause_config_file, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except Exception as e:
        print(f"保存暂停配置错误: {str(e)}")
        return False

# 客户端配置文件路径
client_configs_file = os.path.join(app.config["UPLOAD_FOLDER"], "client_configs.json")
if not os.path.exists(client_configs_file):
    with open(client_configs_file, "w") as f:
        json.dump({}, f)

# 实时按键记录缓冲区，格式：{client_id: [key_data1, key_data2, ...]}
realtime_keylog_buffer = {}
max_buffer_size = 1000  # 每个客户端最多保存1000条记录

# 键盘记录实时模式状态跟踪
# 格式: {client_id: {'active': True/False, 'last_request_time': timestamp, 'expiry_time': timestamp, 'last_sent_index': int}}
keylog_realtime_sessions = {}

# 跟踪已发送给前端的数据索引，避免重复发送
# 格式: {client_id: last_sent_index}
realtime_keylog_sent_index = {}

# 客户端实时查看状态，记录哪些客户端正在被查看
client_live_views = {}  # 格式: {client_id: {'keylog': True/False, 'logs': True/False}}

# 检查是否应该进行截图的函数
def should_capture_now(client_id):
    """检查指定客户端是否应该在当前时间进行后台截图"""
    if client_id not in app.config["BACKGROUND_CAPTURE_CLIENTS"]:
        return False
    
    client_config = app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id]
    if not client_config.get('enabled', False):
        return False
    
    # 获取截图间隔（秒）
    interval = client_config.get('interval', app.config["BACKGROUND_CAPTURE_INTERVAL"])
    
    # 检查上次截图时间
    last_capture = client_config.get('last_capture', 0)
    current_time = time.time()
    
    # 如果间隔时间已到，允许截图
    if current_time - last_capture >= interval:
        # 更新上次截图时间
        app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id]['last_capture'] = current_time
        return True
    
    return False

# 客户端系统信息缓存 - 保存最新的系统信息
# 格式: {client_id: system_info}
sysinfo_cache = {}

# 实时日志缓冲区，格式：{client_id: [log_entry1, log_entry2, ...]}
realtime_log_buffer = {}
max_log_buffer_size = 1000  # 每个客户端最多保存1000条日志记录

# 文件列表缓存
downloaded_files_cache = {}
downloaded_files_cache_time = {}
CACHE_EXPIRY = 30  # 增加缓存时间到30秒

# 文件浏览API的缓存
file_browse_cache = {}
file_browse_cache_time = {}
FILE_BROWSE_CACHE_EXPIRY = 40  # 增加缓存时间到30秒，原来是15秒

# 文件读取API的缓存
file_read_cache = {}
file_read_cache_time = {}
FILE_READ_CACHE_EXPIRY = 20  # 增加缓存时间到20秒

# 后台键盘捕获配置存储
background_keylog_config_file = os.path.join(app.config["UPLOAD_FOLDER"], "background_keylog_config.json")
if not os.path.exists(background_keylog_config_file):
    with open(background_keylog_config_file, "w") as f:
        json.dump({}, f)

# 分块上传状态跟踪
chunked_uploads = {}  # 格式：{upload_id: {client_id, filename, total_chunks, received_chunks, chunk_data, type}}

# 检查文件扩展名是否允许
def allowed_file(filename):
    CONFIG = {
        "storage_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
        "allowed_extensions": {"jpg", "jpeg", "png", "txt", "avi", "mp4"}
    }
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in CONFIG["allowed_extensions"]

# 获取客户端目录
def get_client_dir(client_id):
    CONFIG = {
        "storage_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    }
    client_dir = os.path.join(CONFIG["storage_path"], client_id)
    if not os.path.exists(client_dir):
        os.makedirs(client_dir, exist_ok=True)
    return client_dir

# 加载元数据
def load_metadata():
    try:
        with open(metadata_file, "r") as f:
            return json.load(f)
    except:
        return {"clients": {}}

# 保存元数据
def save_metadata(metadata):
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

# 获取所有客户端信息
def get_all_clients():
    try:
        with open(clients_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取客户端信息错误: {str(e)}")
        return {}

# 保存客户端信息
def save_client_info(client_info):
    if not client_info or "client_id" not in client_info:
        return False
        
    client_id = client_info["client_id"]
    
    clients = get_all_clients()
    
    # 更新客户端信息
    clients[client_id] = {
        "hostname": client_info.get("hostname", "未知"),
        "username": client_info.get("username", "未知"),
        "last_seen": datetime.datetime.now().isoformat(),
        "ip": request.remote_addr
    }
    
    # 保存到文件
    try:
        with open(clients_file, "w") as f:
            json.dump(clients, f, indent=2)
        return True
    except Exception as e:
        print(f"保存客户端信息错误: {str(e)}")
        return False

# 创建新的命令ID
def generate_command_id():
    return str(uuid.uuid4())

# 处理文件上传
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
            
        file = request.files['file']
        client_id = request.form.get('client_id', '')
        
        if not file:
            return jsonify({"status": "error", "message": "No file selected"}), 400
            
        if not client_id:
            return jsonify({"status": "error", "message": "No client_id provided"}), 400
            
        # 使用原始文件名，而不是secure_filename，以保留特殊字符（如.和$开头的文件名）
        orig_filename = file.filename
        
        # 基本安全检查：确保文件名不包含非法路径字符
        if '/' in orig_filename or '\\' in orig_filename:
            # 只有当文件名包含路径分隔符时才使用secure_filename处理
            filename = secure_filename(orig_filename)
            print(f"文件名包含路径分隔符，已安全处理: {orig_filename} -> {filename}")
        else:
            filename = orig_filename
            
        # 获取文件类型
        file_type = request.form.get('type', 'unknown')
        
        # 确保客户端目录存在
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        os.makedirs(client_dir, exist_ok=True)
            
        # 判断是否为下载文件，如果是下载文件类型则创建并使用download子目录
        if file_type == "download":
            download_dir = os.path.join(client_dir, "download")
            os.makedirs(download_dir, exist_ok=True)
            file_path = os.path.join(download_dir, filename)
        else:
            file_path = os.path.join(client_dir, filename)
        
        # 检查文件是否已存在，如果存在则添加时间戳
        if os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"
            
            if file_type == "download":
                file_path = os.path.join(download_dir, filename)
            else:
                file_path = os.path.join(client_dir, filename)
        
        # 保存文件
        file.save(file_path)
        # 保存客户端信息
        client_info = {
            "client_id": client_id,
            "hostname": request.form.get('hostname', '未知'),
            "username": request.form.get('username', '未知'),
            "ip": request.remote_addr,
            "last_seen": datetime.datetime.now().isoformat()
        }
        save_client_info(client_info)
        
        # 检查是否是压缩文件
        compression = request.form.get("compression", "none")
        if compression == "zlib" and allowed_file(filename):
            try:
                # 尝试解压缩
                original_size = request.form.get("original_size", "0")
                print(f"正在解压缩文件: {filename}, 压缩算法: {compression}, 原始大小: {original_size}")
                with open(file_path, "rb") as f:
                    compressed_data = f.read()
                
                # 使用zlib解压缩
                import zlib
                decompressed_data = zlib.decompress(compressed_data)
                
                # 重写文件
                with open(file_path, "wb") as f:
                    f.write(decompressed_data)
                    
                print(f"文件解压缩完成: {filename}")
            except Exception as e:
                print(f"解压缩文件失败: {str(e)}")
        
        return jsonify({"status": "success", "message": "File uploaded successfully", "filename": filename})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 初始化分块上传
@app.route("/init_chunked_upload", methods=["POST"])
def init_chunked_upload():
    try:
        data = request.json
        client_id = data.get("client_id")
        filename = data.get("filename")
        total_size = data.get("total_size")
        chunk_size = data.get("chunk_size")
        total_chunks = data.get("total_chunks")
        file_type = data.get("type")
        
        if not client_id or not filename or not total_chunks:
            return jsonify({"error": "缺少必要参数"}), 400
            
        # 生成上传ID
        upload_id = str(uuid.uuid4())
        
        # 基本安全检查：确保文件名不包含非法路径字符
        orig_filename = filename
        if '/' in orig_filename or '\\' in orig_filename:
            # 只有当文件名包含路径分隔符时才使用secure_filename处理
            safe_filename = secure_filename(orig_filename)
            print(f"分块上传：文件名包含路径分隔符，已安全处理: {orig_filename} -> {safe_filename}")
            filename = safe_filename
        
        # 记录上传状态
        chunked_uploads[upload_id] = {
            "client_id": client_id,
            "filename": filename,
            "total_chunks": total_chunks,
            "received_chunks": 0,
            "chunk_data": {},
            "type": file_type,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "temp_dir": tempfile.mkdtemp(),
            "created_at": time.time()
        }
        
        # 保存客户端信息
        client_info = {
            "client_id": client_id,
            "last_seen": datetime.datetime.now().isoformat()
        }
        save_client_info(client_info)
        
        print(f"初始化分块上传: {filename}, 总大小: {total_size/1024/1024:.2f}MB, 共{total_chunks}块")
        
        return jsonify({
            "status": "success", 
            "upload_id": upload_id,
            "message": f"初始化分块上传成功，共{total_chunks}块"
        })
    except Exception as e:
        print(f"初始化分块上传错误: {str(e)}")
        return jsonify({"error": f"初始化分块上传错误: {str(e)}"}), 500

# 上传分块
@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    try:
        # 获取参数
        upload_id = request.form.get("upload_id")
        chunk_index = int(request.form.get("chunk_index"))
        client_id = request.form.get("client_id")
        
        if not upload_id or chunk_index is None or not client_id:
            return jsonify({"error": "缺少必要参数"}), 400
            
        # 检查上传ID是否存在
        if upload_id not in chunked_uploads:
            return jsonify({"error": "无效的上传ID"}), 400
            
        # 检查客户端ID是否匹配
        if chunked_uploads[upload_id]["client_id"] != client_id:
            return jsonify({"error": "客户端ID不匹配"}), 403
            
        # 检查是否已接收该分块
        if chunk_index in chunked_uploads[upload_id]["chunk_data"]:
            return jsonify({"error": f"分块{chunk_index}已接收"}), 400
            
        # 获取文件数据
        if "chunk" not in request.files:
            return jsonify({"error": "没有文件数据"}), 400
            
        chunk_file = request.files["chunk"]
        
        # 保存分块到临时目录
        upload_info = chunked_uploads[upload_id]
        chunk_path = os.path.join(upload_info["temp_dir"], f"chunk_{chunk_index}")
        chunk_file.save(chunk_path)
        
        # 更新接收状态
        upload_info["chunk_data"][chunk_index] = chunk_path
        upload_info["received_chunks"] += 1
        
        print(f"接收分块: {chunk_index+1}/{upload_info['total_chunks']} - 上传ID: {upload_id[:8]}")
        
        return jsonify({
            "status": "success", 
            "message": f"分块 {chunk_index+1}/{upload_info['total_chunks']} 上传成功",
            "received": upload_info["received_chunks"],
            "total": upload_info["total_chunks"]
        })
    except Exception as e:
        print(f"上传分块错误: {str(e)}")
        return jsonify({"error": f"上传分块错误: {str(e)}"}), 500

# 完成分块上传
@app.route("/complete_chunked_upload", methods=["POST"])
def complete_chunked_upload():
    try:
        data = request.json
        upload_id = data.get("upload_id")
        client_id = data.get("client_id")
        timestamp = data.get("timestamp", datetime.datetime.now().isoformat())
        
        if not upload_id or not client_id:
            return jsonify({"error": "缺少必要参数"}), 400
            
        # 检查上传ID是否存在
        if upload_id not in chunked_uploads:
            return jsonify({"error": "无效的上传ID"}), 400
            
        # 检查客户端ID是否匹配
        if chunked_uploads[upload_id]["client_id"] != client_id:
            return jsonify({"error": "客户端ID不匹配"}), 403
            
        # 获取上传信息
        upload_info = chunked_uploads[upload_id]
        
        # 检查是否所有分块都已接收
        if upload_info["received_chunks"] != upload_info["total_chunks"]:
            return jsonify({
                "error": f"分块不完整，已接收 {upload_info['received_chunks']}/{upload_info['total_chunks']}"
            }), 400
            
        # 创建客户端目录
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        os.makedirs(client_dir, exist_ok=True)
        
        # 处理文件名
        filename = upload_info["filename"]
        file_type = upload_info["type"]
        
        # 根据文件类型和时间戳调整文件名
        if file_type == "screenshot":
            # 截图文件格式：screen_20231231_235959.jpg
            timestamp_obj = datetime.datetime.fromisoformat(timestamp)
            timestamp_str = timestamp_obj.strftime("%Y%m%d_%H%M%S")
            filename = f"screen_{timestamp_str}.jpg"
        elif file_type == "video":
            # 视频文件格式：record_20231231_235959.mp4
            timestamp_obj = datetime.datetime.fromisoformat(timestamp)
            timestamp_str = timestamp_obj.strftime("%Y%m%d_%H%M%S")
            if filename.endswith(".avi"):
                filename = f"record_{timestamp_str}.avi"
            else:
                filename = f"record_{timestamp_str}.mp4"
        
        # 最终文件路径
        file_path = os.path.join(client_dir, filename)
        
        # 合并分块
        with open(file_path, 'wb') as output_file:
            # 按顺序合并所有分块
            for i in range(upload_info["total_chunks"]):
                chunk_path = upload_info["chunk_data"].get(i)
                if not chunk_path:
                    return jsonify({"error": f"缺少分块 {i}"}), 400
                    
                with open(chunk_path, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
        
        # 更新元数据
        metadata = load_metadata()
        if client_id not in metadata["clients"]:
            metadata["clients"][client_id] = {
                "files": []
            }
        
        # 添加文件记录
        file_record = {
            "filename": filename,
            "type": file_type,
            "timestamp": timestamp,
            "uploaded_at": datetime.datetime.now().isoformat(),
            "chunked": True,
            "total_size": upload_info["total_size"]
        }
        metadata["clients"][client_id]["files"].append(file_record)
        save_metadata(metadata)
        
        # 清理临时文件
        try:
            shutil.rmtree(upload_info["temp_dir"])
        except Exception as e:
            print(f"清理临时文件错误: {str(e)}")
        
        # 从跟踪字典中移除
        del chunked_uploads[upload_id]
        
        print(f"分块上传完成: {filename}, 大小: {os.path.getsize(file_path)/1024/1024:.2f}MB")
        
        # 广播文件上传通知
        if file_type == "screenshot":
            socketio.emit('new_screenshot', {
                'client_id': client_id,
                'file': filename,
                'timestamp': timestamp
            }, namespace='/browser')
            
        return jsonify({
            "status": "success", 
            "message": "分块上传完成",
            "filename": filename
        })
    except Exception as e:
        print(f"完成分块上传错误: {str(e)}")
        
        # 尝试清理临时文件
        try:
            if upload_id in chunked_uploads:
                shutil.rmtree(chunked_uploads[upload_id]["temp_dir"])
                del chunked_uploads[upload_id]
        except:
            pass
            
        return jsonify({"error": f"完成分块上传错误: {str(e)}"}), 500

# 清理过期的分块上传
def cleanup_expired_uploads():
    current_time = time.time()
    expired_ids = []
    
    for upload_id, info in chunked_uploads.items():
        # 上传开始超过1小时视为过期
        if current_time - info["created_at"] > 3600:
            expired_ids.append(upload_id)
    
    for upload_id in expired_ids:
        try:
            # 清理临时目录
            shutil.rmtree(chunked_uploads[upload_id]["temp_dir"])
            del chunked_uploads[upload_id]
            print(f"已清理过期上传: {upload_id}")
        except Exception as e:
            print(f"清理过期上传错误: {upload_id}, {str(e)}")

# 启动定期清理过期上传的线程
def start_upload_cleanup_thread():
    def cleanup_thread_function():
        while True:
            try:
                cleanup_expired_uploads()
            except Exception as e:
                print(f"清理过期上传线程错误: {str(e)}")
            time.sleep(1800)  # 每30分钟检查一次
    
    thread = threading.Thread(target=cleanup_thread_function, daemon=True)
    thread.start()
    print("已启动上传清理线程")

# 在应用启动时启动清理线程
start_upload_cleanup_thread()

# 主页
@app.route('/')
def index():
    # 获取所有客户端
    clients = get_all_clients()
    return render_template("index.html", clients=clients)

# 查看特定客户端
@app.route('/client/<client_id>')
def client_detail(client_id):
    # 获取所有客户端信息
    clients_file = os.path.join(app.config["UPLOAD_FOLDER"], "clients.json")
    clients = {}
    if os.path.exists(clients_file):
        try:
            with open(clients_file, "r") as f:
                clients = json.load(f)
        except Exception as e:
            print(f"加载客户端信息错误: {str(e)}")
    
    # 获取特定客户端信息
    client_info = clients.get(client_id, {})
    
    # 获取客户端配置
    client_configs = load_client_configs()
    client_config = client_configs.get(client_id, get_default_client_config())
    
    # 获取客户端的截图文件
    client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
    screenshots = []
    videos = []
    
    if os.path.exists(client_dir):
        for file in os.listdir(client_dir):
            if file.startswith("screen_") and file.endswith((".jpg", ".jpeg", ".png")):
                screenshots.append(file)
            elif file.startswith("record_") and file.endswith((".avi", ".mp4")):
                videos.append(file)
    
    screenshots.sort(reverse=True)
    videos.sort(reverse=True)
    
    return render_template(
        "client.html",
        client_id=client_id,
        client_info=client_info,
        client_config=client_config,
        screenshots=screenshots,
        videos=videos
    )

# 查看文件
@app.route("/view/<path:filepath>")
def view_file(filepath):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filepath)

# 查看键盘记录
@app.route('/keylog/<client_id>')
def view_keylog(client_id):
    # 获取所有客户端信息
    clients_file = os.path.join(app.config["UPLOAD_FOLDER"], "clients.json")
    clients = {}
    if os.path.exists(clients_file):
        try:
            with open(clients_file, "r") as f:
                clients = json.load(f)
        except Exception as e:
            print(f"加载客户端信息错误: {str(e)}")
    
    # 获取特定客户端信息
    client_info = clients.get(client_id, {})
    # 获取客户端的键盘记录文件
    client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
    keylog_files = []
    keylog_contents = {}
    
    if os.path.exists(client_dir):
        for file in os.listdir(client_dir):
            if file.startswith("keylog_") and file.endswith(".txt"):
                keylog_files.append(file)
                
                # 读取文件内容
                try:
                    with open(os.path.join(client_dir, file), "r") as f:
                        keylog_contents[file] = f.read()
                except Exception as e:
                    keylog_contents[file] = f"无法读取文件内容: {str(e)}"
    
    keylog_files.sort(reverse=True)
    
    return render_template(
        "keylog.html",
        client_id=client_id,
        client_info=client_info,
        keylog_files=keylog_files,
        keylog_contents=keylog_contents,
        view_only_mode=True  # 添加此标志以指示仅查看模式
    )

# 客户端命令API - 获取待执行的命令
@app.route('/command', methods=['GET'])
def get_commands():
    # 获取请求参数
    client_id = request.args.get('client_id')
    hostname = request.args.get('hostname', '未知')
    username = request.args.get('username', '未知')
    
    if not client_id:
        return jsonify([]), 200
    
    # 清理过期的命令状态（超过5分钟的pending命令）
    current_time = datetime.datetime.now()
    expired_commands = []
    for cmd_id, cmd_info in command_status.items():
        if cmd_info.get("status") == "pending":
            try:
                cmd_timestamp = datetime.datetime.fromisoformat(cmd_info.get("timestamp", ""))
                if (current_time - cmd_timestamp).total_seconds() > 300:  # 5分钟
                    expired_commands.append(cmd_id)
            except:
                # 如果时间戳解析失败，也标记为过期
                expired_commands.append(cmd_id)
    
    # 清理过期命令
    for cmd_id in expired_commands:
        del command_status[cmd_id]
        print(f"清理过期命令: {cmd_id}")
    
    # 检查命令队列
    if client_id in client_commands:
        # 获取该客户端的命令队列
        commands = client_commands[client_id]
        
        # 验证命令优先级处理：将验证命令放在队列前面
        verify_commands = []
        other_commands = []
        
        for cmd in commands:
            if cmd.get("type") == "verify":
                verify_commands.append(cmd)
            else:
                other_commands.append(cmd)
        
        # 重新排序：验证命令优先
        prioritized_commands = verify_commands + other_commands
        
        # 清空命令队列
        client_commands[client_id] = []
        
        if verify_commands:
            print(f"🔑 优先发送 {len(verify_commands)} 个验证命令给客户端 {client_id}")
        
        return jsonify(prioritized_commands), 200
    
    # 检查是否有自动命令
    auto_commands = []
    
    # 如果开启了自动截图，添加截图命令
    if client_id in app.config["BACKGROUND_CAPTURE_CLIENTS"]:
        if app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id].get('enabled', False):
            # 检查是否在规定的时间内
            should_capture = should_capture_now(client_id)
            if should_capture:
                # 创建截图命令
                command_id = generate_command_id()
                screenshot_command = {
                    "id": command_id,
                    "type": "take_screenshot",
                    "timestamp": datetime.datetime.now().isoformat()
                }
                auto_commands.append(screenshot_command)
                # 记录命令状态
                command_status[command_id] = {
                    "client_id": client_id,
                    "command": screenshot_command,
                    "status": "pending",
                    "message": "自动截图命令已发送",
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
    # 检查键盘记录实时模式状态
    current_time = time.time()
    if client_id in keylog_realtime_sessions:
        session = keylog_realtime_sessions[client_id]
        # 检查会话是否过期（10秒）
        if current_time > session.get('expiry_time', 0):
            # 会话已过期，清理
            del keylog_realtime_sessions[client_id]
            print(f"客户端 {client_id} 键盘记录实时会话已过期")
        elif session.get('active', False):
            # 会话仍然活跃，发送实时键盘记录命令
            command_id = generate_command_id()
            keylog_command = {
                "id": command_id,
                "type": "send_realtime_keylog",
                "timestamp": datetime.datetime.now().isoformat(),
                "duration": 1  # 1秒内的按键
            }
            auto_commands.append(keylog_command)
            # 记录命令状态
            command_status[command_id] = {
                "client_id": client_id,
                "command": keylog_command,
                "status": "pending",
                "message": "实时键盘记录命令已发送",
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    return jsonify(auto_commands), 200

# 客户端命令结果API
@app.route('/command_result', methods=['POST'])
def command_result():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        client_id = data.get('client_id')
        command_id = data.get('command_id')
        
        if not client_id or not command_id:
            return jsonify({"status": "error", "message": "Missing client_id or command_id"}), 400
            
        # 调试输出
        print(f"收到命令结果: client_id={client_id}, command_id={command_id}, success={data.get('success')}")
        print(f"完整结果数据: {json.dumps(data, default=str)}")
        
        # 保存命令执行结果
        if client_id not in command_results:
            command_results[client_id] = {}
        
        result = {
            "success": data.get('success', False),
            "message": data.get('message', ''),
            "timestamp": data.get('timestamp', datetime.datetime.now().isoformat()),
            "attempts_left": data.get('attempts_left', 0)  # 确保总是保存attempts_left
        }
        
        command_results[client_id][command_id] = result
        
        # 检查是否是验证命令，无论命令是否在队列中
        verify_command = False
        command_type = None
        
        # 首先检查命令队列
        command_found = False
        for cmd in client_commands.get(client_id, []):
            if cmd.get('id') == command_id:
                command_found = True
                command_type = cmd.get('type')
                print(f"找到对应命令: {command_type}")
                break
                
        # 如果命令不在队列中，检查命令状态字典
        if not command_found and command_id in command_status:
            cmd_info = command_status[command_id].get('command', {})
            command_type = cmd_info.get('type')
            command_found = True
            print(f"在命令状态中找到命令: {command_type}")
        
        # 判断是否是验证命令
        if command_type == "verify" or (not command_found and "verify" in command_id.lower()):
            try:
                # 明确从结果中获取验证成功状态
                is_verified = data.get('success', False)
                
                # 获取验证结果中的尝试次数和消息
                attempts_left = data.get('attempts_left', 0)
                error_message = data.get('message', '')
                
                # 处理不同格式的响应
                if isinstance(data.get('message'), dict):
                    # 如果message是字典，尝试直接从中获取字段
                    message_dict = data.get('message', {})
                    if 'attempts_left' in message_dict:
                        attempts_left = message_dict.get('attempts_left', 0)
                    if 'message' in message_dict:
                        error_message = message_dict.get('message', '')
                    # 如果message_dict中有success字段，使用它更新is_verified
                    if 'success' in message_dict:
                        is_verified = message_dict.get('success')
                
                print(f"验证命令结果(处理后): 成功={is_verified}, 剩余尝试次数={attempts_left}, 消息={error_message}")
                
                # 无论命令是否找到，都更新命令状态
                command_status[command_id] = command_status.get(command_id, {
                    "client_id": client_id,
                    "command": {"id": command_id, "type": "verify"},
                    "timestamp": datetime.datetime.now().isoformat()
                })
                
                # 更新命令状态
                command_status[command_id].update({
                    "status": "completed",
                    "success": is_verified,
                    "message": error_message,
                    "attempts_left": attempts_left
                })
                
                # 调试输出更新后的命令状态
                print(f"更新后的命令状态: {json.dumps(command_status[command_id], default=str)}")
                
                # 如果客户端在验证状态表中，更新验证状态
                if client_id in verification_status:
                    verification_status[client_id].update({
                        "is_verified": is_verified,
                        "attempts_left": attempts_left
                    })
                    
                    if is_verified:
                        print(f"客户端 {client_id} 验证成功")
                    else:
                        print(f"客户端 {client_id} 验证失败，剩余尝试次数: {attempts_left}")
                    
                # 更新验证配置
                configs = load_verification_config()
                if client_id not in configs:
                    configs[client_id] = {"verifications": []}
                    
                # 添加验证记录
                verification_record = {
                    "time": int(time.time()),
                    "success": is_verified,
                    "ip": request.remote_addr,
                    "attempts_left": attempts_left,
                    "message": error_message
                }
                
                configs[client_id]["verifications"].append(verification_record)
                save_verification_config(configs)
            except Exception as e:
                print(f"处理验证命令结果错误: {str(e)}")
                import traceback
                traceback.print_exc()
        elif command_found:
            # 处理其他类型的命令
            if command_type == "browse_files" and data.get('success'):
                try:
                    path = None
                    for cmd in client_commands.get(client_id, []):
                        if cmd.get('id') == command_id:
                            path = cmd.get('path')
                            break
                            
                    if path:
                        # 如果message是字符串，尝试解析JSON
                        if isinstance(data["message"], str):
                            try:
                                # 解析JSON字符串为对象
                                message_obj = json.loads(data["message"])
                                # 更新结果数据
                                result["message"] = message_obj
                            except json.JSONDecodeError:
                                print(f"浏览文件结果JSON解析错误: {data['message'][:100]}...")
                        
                        # 更新文件浏览缓存
                        cache_key = f"{client_id}:{path}"
                        file_browse_cache[cache_key] = {"command_id": command_id}
                        file_browse_cache_time[cache_key] = time.time()
                        print(f"更新文件浏览缓存: {cache_key}")
                except Exception as e:
                    print(f"处理文件浏览结果缓存错误: {str(e)}")
                    import traceback
                    traceback.print_exc()
            # 处理实时键盘记录结果
            elif command_type == "send_realtime_keylog" and data.get('success'):
                try:
                    # 处理实时键盘记录命令响应
                    # 客户端应该直接通过 /api/keylog_realtime_data/<client_id> API发送数据
                    print(f"客户端 {client_id} 实时键盘记录命令执行成功")
                except Exception as e:
                    print(f"处理实时键盘记录命令响应错误: {str(e)}")
        
        if not command_found:
            print(f"警告: 未找到对应的命令 {command_id}，但已处理结果数据")
        
        # 检查是否是系统信息命令，如果是则保存到缓存
        if data.get('success') and 'message' in data:
            try:
                # 尝试解析消息内容
                if isinstance(data["message"], str) and ("cpu_usage" in data["message"] or "memory" in data["message"]):
                    # 可能是系统信息JSON
                    try:
                        system_info = json.loads(data["message"])
                        if "cpu_usage" in system_info and "memory" in system_info and "disk" in system_info:
                            # 确认是系统信息
                            sysinfo_cache[client_id] = system_info
                            print(f"已更新客户端 {client_id} 的系统信息缓存")
                    except json.JSONDecodeError as e:
                        print(f"解析系统信息JSON出错: {str(e)}")
                    except Exception as e:
                        print(f"处理系统信息异常: {str(e)}")
                elif isinstance(data["message"], dict):
                    # 消息已经是对象
                    system_info = data["message"]
                    if "cpu_usage" in system_info and "memory" in system_info and "disk" in system_info:
                        # 确认是系统信息
                        sysinfo_cache[client_id] = system_info
                        print(f"已更新客户端 {client_id} 的系统信息缓存")
            except Exception as e:
                print(f"处理系统信息失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return jsonify({"status": "success", "message": "Command result received"})
    except Exception as e:
        print(f"处理命令结果出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"处理命令结果错误: {str(e)}"}), 500

# 专门用于系统性能文件上传结果的API
@app.route('/api/system_performance_result', methods=['POST'])
def system_performance_result():
    """处理系统性能文件上传结果的专用API"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        client_id = data.get('client_id')
        command_id = data.get('command_id')
        success = data.get('success', False)
        result = data.get('result', {})
        
        if not client_id or not command_id:
            return jsonify({"status": "error", "message": "Missing client_id or command_id"}), 400
            
        # 调试输出
        print(f"收到系统性能结果: client_id={client_id}, command_id={command_id}, success={success}")
        print(f"结果详情: {json.dumps(result, default=str)}")
        
        # 保存到专门的系统性能结果存储
        if client_id not in command_results:
            command_results[client_id] = {}
            
        # 创建标准化的结果结构
        standardized_result = {
            "success": success,
            "timestamp": data.get('timestamp', datetime.datetime.now().isoformat()),
            "result_type": "system_performance",
            "upload_type": result.get('upload_type', 'unknown'),
            "files_processed": result.get('files_processed', 0),
            "files_uploaded": result.get('files_uploaded', 0),
            "system_info": result.get('system_info'),
            "errors": result.get('errors', []),
            "message": result.get('message', 'System performance upload completed')
        }
        
        command_results[client_id][command_id] = standardized_result
        
        # 如果结果包含系统信息，更新缓存
        if success and result.get('system_info'):
            try:
                system_info = result['system_info']
                if "cpu_usage" in system_info and "memory" in system_info:
                    sysinfo_cache[client_id] = system_info
                    print(f"通过系统性能上传更新了客户端 {client_id} 的系统信息缓存")
            except Exception as e:
                print(f"更新系统信息缓存时出错: {str(e)}")
        
        # 记录性能统计
        perf_stats = {
            "client_id": client_id,
            "command_id": command_id,
            "timestamp": data.get('timestamp'),
            "success": success,
            "files_count": result.get('files_uploaded', 0),
            "upload_type": result.get('upload_type', 'unknown')
        }
        
        # 可以在这里添加性能统计存储逻辑
        print(f"系统性能上传统计: {json.dumps(perf_stats, default=str)}")
        
        return jsonify({
            "status": "success", 
            "message": "System performance result received",
            "processed_files": result.get('files_uploaded', 0)
        })
        
    except Exception as e:
        print(f"处理系统性能结果出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"处理系统性能结果错误: {str(e)}"}), 500

# 管理API - 发送录屏命令
@app.route('/api/record/<client_id>', methods=['POST'])
def start_recording(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "Client not found"}), 404
    
    # 从请求中获取参数
    duration = request.form.get('duration', 60)
    try:
        duration = int(duration)
    except:
        duration = 60
    
    fps = request.form.get('fps', 10)
    try:
        fps = int(fps)
    except:
        fps = 10
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "start_recording",
        "timestamp": datetime.datetime.now().isoformat(),
        "duration": duration,
        "fps": fps
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": f"录屏命令已发送，持续时间: {duration}秒, 帧率: {fps}fps",
        "command_id": command_id
    })

# 管理API - 停止录屏
@app.route('/api/stop_record/<client_id>', methods=['POST'])
def stop_recording(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "Client not found"}), 404
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "stop_recording",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": "停止录屏命令已发送",
        "command_id": command_id
    })

# 管理API - 请求截图
@app.route('/api/screenshot/<client_id>', methods=['POST'])
def take_screenshot(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "Client not found"}), 404
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "take_screenshot",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": "截图命令已发送",
        "command_id": command_id
    })

# 管理API - 发送系统性能文件上传命令
@app.route('/api/system_performance/<client_id>', methods=['POST'])
def upload_system_performance(client_id):
    """发送系统性能文件上传命令给指定客户端"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 获取请求参数
        data = request.json if request.json else {}
        upload_type = data.get('upload_type', 'current')  # current, historical, both
        include_system_info = data.get('include_system_info', True)
        max_files = data.get('max_files', 10)
        
        # 验证参数
        if upload_type not in ['current', 'historical', 'both']:
            return jsonify({"status": "error", "message": "无效的上传类型"}), 400
            
        if not isinstance(max_files, int) or max_files < 1 or max_files > 50:
            return jsonify({"status": "error", "message": "文件数量应在1-50之间"}), 400
        
        # 生成命令ID
        command_id = f"sysperf_{generate_command_id()}"
        
        # 创建命令
        command = {
            "id": command_id,
            "type": "upload_system_performance",
            "upload_type": upload_type,
            "include_system_info": include_system_info,
            "max_files": max_files,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        client_commands[client_id].append(command)
        
        # 添加命令跟踪记录
        command_tracking[command_id] = {
            "client_id": client_id,
            "command_type": "upload_system_performance",
            "created_time": time.time(),
            "upload_type": upload_type,
            "max_files": max_files
        }
        
        print(f"系统性能上传命令已发送给客户端 {client_id}: {command_id}")
        print(f"命令详情: {json.dumps(command, default=str)}")
        
        return jsonify({
            "status": "success", 
            "message": "系统性能上传命令已发送",
            "command_id": command_id,
            "upload_type": upload_type,
            "max_files": max_files
        })
        
    except Exception as e:
        print(f"发送系统性能上传命令出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送命令失败: {str(e)}"}), 500

# 发送键盘记录上传命令
@app.route('/api/keylog_upload/<client_id>', methods=['POST'])
def upload_keylog_files(client_id):
    """发送键盘记录文件上传命令给指定客户端"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 获取请求参数
        data = request.json if request.json else {}
        upload_type = data.get('upload_type', 'recent')  # recent, all
        max_files = data.get('max_files', 10)
        
        # 验证参数
        if upload_type not in ['recent', 'all']:
            return jsonify({"status": "error", "message": "无效的上传类型"}), 400
            
        if not isinstance(max_files, int) or max_files < 1 or max_files > 50:
            return jsonify({"status": "error", "message": "文件数量应在1-50之间"}), 400
        
        # 生成命令ID
        command_id = f"keylog_{generate_command_id()}"
        
        # 创建命令
        command = {
            "id": command_id,
            "type": "upload_keylog_files",
            "upload_type": upload_type,
            "max_files": max_files,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        client_commands[client_id].append(command)
        
        # 添加命令跟踪记录
        command_tracking[command_id] = {
            "client_id": client_id,
            "command_type": "upload_keylog_files",
            "created_time": time.time(),
            "upload_type": upload_type,
            "max_files": max_files
        }
        
        print(f"键盘记录上传命令已发送给客户端 {client_id}: {command_id}")
        print(f"命令详情: {json.dumps(command, default=str)}")
        
        return jsonify({
            "status": "success", 
            "message": "键盘记录上传命令已发送",
            "command_id": command_id,
            "upload_type": upload_type,
            "max_files": max_files
        })
        
    except Exception as e:
        print(f"发送键盘记录上传命令出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送命令失败: {str(e)}"}), 500

# 发送实时键盘记录命令
@app.route('/api/send_realtime_keylog/<client_id>', methods=['POST'])
def send_realtime_keylog_command(client_id):
    """发送实时键盘记录命令给指定客户端"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 获取请求参数
        data = request.json if request.json else {}
        duration = data.get('duration', 1)  # 获取多少秒内的按键
        
        # 验证参数
        if not isinstance(duration, int) or duration < 1 or duration > 60:
            return jsonify({"status": "error", "message": "时间范围应在1-60秒之间"}), 400
        
        # 生成命令ID
        command_id = f"realtime_keylog_{generate_command_id()}"
        
        # 创建命令
        command = {
            "id": command_id,
            "type": "send_realtime_keylog",
            "duration": duration,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        client_commands[client_id].append(command)
        
        # 添加命令跟踪记录
        command_tracking[command_id] = {
            "client_id": client_id,
            "command_type": "send_realtime_keylog",
            "created_time": time.time(),
            "duration": duration
        }
        
        print(f"实时键盘记录命令已发送给客户端 {client_id}: {command_id}")
        
        return jsonify({
            "status": "success", 
            "message": "实时键盘记录命令已发送",
            "command_id": command_id,
            "duration": duration
        })
        
    except Exception as e:
        print(f"发送实时键盘记录命令出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送命令失败: {str(e)}"}), 500

# 管理API - 获取命令执行结果
@app.route('/api/command_status/<client_id>/<command_id>', methods=['GET'])
def get_command_status(client_id, command_id):
    try:
        print(f"查询命令状态: client_id={client_id}, command_id={command_id}")
        
        # 检查是否是系统信息命令
        # 注意：命令可能已经从队列中移除
        is_sysinfo_command = False
        is_download_command = False
        
        # 1. 先查找命令队列
        for cmd in client_commands.get(client_id, []):
            if cmd.get('id') == command_id:
                cmd_type = cmd.get('type')
                print(f"在队列中找到命令: {cmd_type}")
                if cmd_type == "get_system_info":
                    is_sysinfo_command = True
                elif cmd_type == "download_file":
                    is_download_command = True
                break
                
        # 2. 如果没找到，尝试根据命令ID的前缀判断
        if not is_sysinfo_command and command_id.startswith("sysinfo_"):
            is_sysinfo_command = True
            print(f"根据ID前缀判断为系统信息命令: {command_id}")
            
        # 3. 检查结果是否已经返回
        if client_id in command_results and command_id in command_results[client_id]:
            print(f"命令已完成，返回结果: {command_id}")
            result = command_results[client_id][command_id]
            
            # 为下载命令添加特殊处理
            if is_download_command:
                # 确保下载文件的命令结果有正确的结构
                if result.get('success') == True and not result.get('from_cache', False):
                    print(f"文件下载命令已完成: {command_id}")
            
            return jsonify({
                "status": "complete",
                "result": result
            })
            
        # 4. 如果是系统信息命令，尝试使用缓存
        if is_sysinfo_command and client_id in sysinfo_cache:
            print(f"使用缓存的系统信息返回给客户端 {client_id}")
            return jsonify({
                "status": "complete",
                "result": {
                    "success": True,
                    "message": sysinfo_cache[client_id],
                    "timestamp": datetime.datetime.now().isoformat(),
                    "from_cache": True
                }
            })

        # 5. 如果以上都不符合，则命令仍在等待执行或结果
        print(f"命令仍在等待执行或结果: {command_id}")
        return jsonify({
            "status": "pending", 
            "message": "Command still pending or not found"
        })
    except Exception as e:
        print(f"获取命令状态出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"获取命令状态出错: {str(e)}"
        }), 500

# 专用的命令状态跟踪字典
command_tracking = {}

# 管理API - 获取系统性能命令执行结果
@app.route('/api/system_performance_status/<client_id>/<command_id>', methods=['GET'])
def get_system_performance_status(client_id, command_id):
    """获取系统性能文件上传命令的执行状态"""
    try:
        print(f"查询系统性能命令状态: client_id={client_id}, command_id={command_id}")
        
        # 1. 检查结果是否已经返回
        if client_id in command_results and command_id in command_results[client_id]:
            result = command_results[client_id][command_id]
            print(f"系统性能命令已完成，返回结果: {command_id}")
            
            # 清理跟踪记录
            if command_id in command_tracking:
                del command_tracking[command_id]
            
            # 确保返回的是标准格式
            return jsonify({
                "status": "complete",
                "result": result
            })
            
        # 2. 检查命令是否在队列中
        command_found = False
        for cmd in client_commands.get(client_id, []):
            if cmd.get('id') == command_id and cmd.get('type') == 'upload_system_performance':
                command_found = True
                print(f"系统性能命令仍在队列中: {command_id}")
                break
                
        if command_found:
            return jsonify({
                "status": "pending", 
                "message": "System performance upload command is still pending"
            })
            
        # 3. 检查命令跟踪记录
        if command_id in command_tracking:
            tracking_info = command_tracking[command_id]
            elapsed_time = time.time() - tracking_info['created_time']
            
            print(f"命令 {command_id} 已发送 {elapsed_time:.1f} 秒")
            
            # 如果命令发送时间不长，继续等待
            if elapsed_time < 30:  # 30秒内认为还在处理中
                return jsonify({
                    "status": "pending", 
                    "message": f"System performance command is being processed (elapsed: {elapsed_time:.1f}s)"
                })
            else:
                # 超时，可能是客户端不支持该命令
                print(f"命令 {command_id} 可能超时或客户端不支持")
                
                # 尝试回退到旧的系统信息API
                return handle_fallback_system_info(client_id, command_id)
        
        # 4. 命令ID格式检查 - 如果不是我们的系统性能命令ID格式，也回退
        if not command_id.startswith("sysperf_"):
            print(f"命令ID格式不正确: {command_id}")
            return jsonify({
                "status": "error", 
                "message": "Invalid system performance command ID format"
            })
            
        # 5. 完全找不到命令，回退到旧API
        return handle_fallback_system_info(client_id, command_id)
            
    except Exception as e:
        print(f"获取系统性能命令状态出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"获取系统性能命令状态出错: {str(e)}"
        }), 500

def handle_fallback_system_info(client_id, command_id):
    """回退处理：使用旧的系统信息API获取数据"""
    print(f"回退到旧的系统信息获取方式: client_id={client_id}")
    
    try:
        # 清理跟踪记录
        if command_id in command_tracking:
            del command_tracking[command_id]
            
        # 检查系统信息缓存
        if client_id in sysinfo_cache:
            print(f"使用缓存的系统信息返回给客户端 {client_id}")
            return jsonify({
                "status": "complete",
                "result": {
                    "success": True,
                    "system_info": sysinfo_cache[client_id],
                    "timestamp": datetime.datetime.now().isoformat(),
                    "result_type": "system_performance",
                    "upload_type": "current",
                    "files_processed": 0,
                    "files_uploaded": 0,
                    "from_cache": True,
                    "message": "Using cached system information (client may not support new performance upload feature)"
                }
            })
        else:
            # 发送传统的系统信息获取命令
            old_command_id = f"sysinfo_{generate_command_id()}"
            
            # 创建传统的系统信息命令
            command = {
                "id": old_command_id,
                "type": "get_system_info",
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # 添加到命令队列
            if client_id not in client_commands:
                client_commands[client_id] = []
            client_commands[client_id].append(command)
            
            print(f"回退：发送传统系统信息命令 {old_command_id}")
            
            return jsonify({
                "status": "fallback_pending", 
                "message": "Falling back to legacy system info command",
                "fallback_command_id": old_command_id,
                "original_command_id": command_id
            })
            
    except Exception as e:
        print(f"回退处理出错: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Fallback handling failed: {str(e)}"
        }), 500

# 查看客户端文件
@app.route('/uploads/<client_id>/<filename>')
def uploaded_file(client_id, filename):
    client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
    return send_from_directory(client_dir, filename)

# 加载客户端配置
def load_client_configs():
    try:
        with open(client_configs_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取客户端配置错误: {str(e)}")
        return {}

# 保存客户端配置
def save_client_configs(configs):
    try:
        with open(client_configs_file, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except Exception as e:
        print(f"保存客户端配置错误: {str(e)}")
        return False

# 获取默认客户端配置
def get_default_client_config():
    return {
        "screenshot_interval": 15,  # 截图间隔(秒)，默认15秒一次
        "upload_interval": 60,      # 上传间隔(秒)
        "check_command_interval": 3,  # 检查服务端命令的间隔(秒)
        "recording_duration": 60,   # 录屏持续时间(秒)
        "recording_fps": 10,        # 录屏帧率
        "keylogger_interval": 1,    # 键盘记录间隔(秒)，默认1秒一次
        "keylogger_interval_recording": 0.5,  # 录屏时键盘记录间隔(秒)，默认500毫秒一次
        "enable_screenshot": True,  # 是否启用截图
        "enable_keylogger": True,   # 是否启用键盘记录
        "enable_upload": True,      # 是否启用上传
        "enable_realtime_keylog": True, # 是否启用实时键盘记录
        "enable_historical_keylog": True, # 是否启用历史键盘记录
        "screenshot_paused": False,  # 新增：是否暂停截屏
        "config_sync_interval": 30, # 配置同步间隔(秒)，默认30s
    }

# 配置同步API
@app.route('/config', methods=['GET'])
def get_client_config():
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({"error": "没有提供客户端ID"}), 400
    
    # 更新客户端信息
    client_info = {
        "client_id": client_id,
        "hostname": request.args.get('hostname', '未知'),
        "username": request.args.get('username', '未知')
    }
    save_client_info(client_info)
    
    # 获取该客户端的配置
    client_configs = load_client_configs()
    
    # 如果该客户端没有配置，则使用默认配置
    if client_id not in client_configs:
        client_configs[client_id] = get_default_client_config()
        save_client_configs(client_configs)
    
    return jsonify(client_configs[client_id])

# 配置更新API - 管理员用于更新客户端配置
@app.route('/api/config/<client_id>', methods=['POST'])
def update_client_config(client_id):
    try:
        # 获取请求数据
        config_data = request.json
        if not config_data:
            return jsonify({"status": "error", "message": "没有提供配置数据"}), 400
        
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 加载当前配置
        client_configs = load_client_configs()
        
        # 如果该客户端没有配置，则使用默认配置
        if client_id not in client_configs:
            client_configs[client_id] = get_default_client_config()
        
        # 更新配置
        for key, value in config_data.items():
            # 只更新合法的配置项
            if key in get_default_client_config():
                # 对布尔值进行特殊处理
                if isinstance(get_default_client_config()[key], bool):
                    client_configs[client_id][key] = bool(value)
                # 对数字进行特殊处理
                elif isinstance(get_default_client_config()[key], (int, float)):
                    try:
                        client_configs[client_id][key] = type(get_default_client_config()[key])(value)
                    except:
                        pass
                else:
                    client_configs[client_id][key] = value
        
        # 保存配置
        if save_client_configs(client_configs):
            return jsonify({
                "status": "success", 
                "message": "客户端配置已更新",
                "config": client_configs[client_id]
            })
        else:
            return jsonify({"status": "error", "message": "保存配置失败"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 批量配置更新API - 管理员用于更新多个客户端配置
@app.route('/api/config/batch', methods=['POST'])
def update_batch_config():
    try:
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "没有提供数据"}), 400
        
        config_data = data.get('config', {})
        client_ids = data.get('client_ids', [])
        
        if not config_data or not client_ids:
            return jsonify({"status": "error", "message": "没有提供配置数据或客户端ID"}), 400
        
        # 验证客户端是否存在
        clients = get_all_clients()
        valid_clients = [cid for cid in client_ids if cid in clients]
        
        if not valid_clients:
            return jsonify({"status": "error", "message": "没有有效的客户端ID"}), 404
        
        # 加载当前配置
        client_configs = load_client_configs()
        
        # 更新每个客户端的配置
        for client_id in valid_clients:
            # 如果该客户端没有配置，则使用默认配置
            if client_id not in client_configs:
                client_configs[client_id] = get_default_client_config()
            
            # 更新配置
            for key, value in config_data.items():
                # 只更新合法的配置项
                if key in get_default_client_config():
                    # 对布尔值进行特殊处理
                    if isinstance(get_default_client_config()[key], bool):
                        client_configs[client_id][key] = bool(value)
                    # 对数字进行特殊处理
                    elif isinstance(get_default_client_config()[key], (int, float)):
                        try:
                            client_configs[client_id][key] = type(get_default_client_config()[key])(value)
                        except:
                            pass
                    else:
                        client_configs[client_id][key] = value
        
        # 保存配置
        if save_client_configs(client_configs):
            return jsonify({
                "status": "success", 
                "message": f"已更新 {len(valid_clients)} 个客户端配置",
                "updated_clients": valid_clients
            })
        else:
            return jsonify({"status": "error", "message": "保存配置失败"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 配置管理页面
@app.route('/config_management')
def config_management():
    return render_template('config_management.html')

# 自动清理配置页面
@app.route('/auto_cleanup')
def auto_cleanup_page():
    return render_template('auto_cleanup.html')

# 获取所有客户端API
@app.route('/api/clients', methods=['GET'])
def get_clients_api():
    return jsonify(get_all_clients())

# 获取单个客户端配置
@app.route('/api/config/<client_id>', methods=['GET'])
def get_single_client_config(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 加载当前配置
    client_configs = load_client_configs()
    
    # 如果该客户端没有配置，则使用默认配置
    if client_id not in client_configs:
        client_configs[client_id] = get_default_client_config()
        save_client_configs(client_configs)
    
    return jsonify(client_configs[client_id])

# 请求系统信息
@app.route('/api/sysinfo/<client_id>', methods=['POST'])
def get_system_info(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 创建命令，使用特殊前缀
    command_id = f"sysinfo_{generate_command_id()}"
    command = {
        "id": command_id,
        "type": "get_system_info",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": "系统信息请求已发送",
        "command_id": command_id
    })

# 浏览文件
@app.route('/api/browse_files/<client_id>', methods=['POST'])
def browse_files(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            print(f"文件浏览错误: 客户端 {client_id} 不存在")
            return jsonify({
                "status": "error",
                "message": "客户端不存在"
            }), 404
            
        # 获取请求数据
        data = request.json
        path = data.get('path')
        print(f"收到文件浏览请求: 客户端={client_id}, 路径={path}")
        
        # 检查缓存
        cache_key = f"{client_id}:{path}"
        current_time = time.time()
        if (cache_key in file_browse_cache and 
            cache_key in file_browse_cache_time and
            current_time - file_browse_cache_time[cache_key] < FILE_BROWSE_CACHE_EXPIRY):
            print(f"使用缓存的文件浏览结果: {cache_key}")
            return jsonify({
                "status": "success", 
                "message": "命令已加入队列", 
                "command_id": file_browse_cache[cache_key]["command_id"],
                "cached": True
            }), 200
        
        # 生成命令ID
        command_id = generate_command_id()
        print(f"为文件浏览请求生成命令ID: {command_id}")
        
        # 保存命令到队列
        client_commands[client_id] = client_commands.get(client_id, [])
        command = {
            "id": command_id,
            "type": "browse_files",
            "path": path,
            "timestamp": datetime.datetime.now().isoformat()
        }
        client_commands[client_id].append(command)
        print(f"文件浏览命令已添加到队列: {command}")
        
        # 保存到缓存
        file_browse_cache[cache_key] = {"command_id": command_id}
        file_browse_cache_time[cache_key] = current_time
        
        return jsonify({
            "status": "success", 
            "message": "命令已加入队列", 
            "command_id": command_id
        }), 200
    except Exception as e:
        print(f"文件浏览请求处理错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"请求处理错误: {str(e)}"
        }), 500

# 读取文件
@app.route('/api/read_file/<client_id>', methods=['POST'])
def read_file(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({
                "status": "error",
                "message": "客户端不存在"
            }), 404
            
        # 获取请求数据
        data = request.json
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                "status": "error",
                "message": "未提供文件路径"
            }), 400
            
        # 检查缓存
        cache_key = f"{client_id}:{file_path}"
        current_time = time.time()
        if (cache_key in file_read_cache and 
            cache_key in file_read_cache_time and
            current_time - file_read_cache_time[cache_key] < FILE_READ_CACHE_EXPIRY):
            return jsonify({
                "status": "success", 
                "message": "命令已加入队列", 
                "command_id": file_read_cache[cache_key]["command_id"],
                "cached": True
            }), 200
        
        # 生成命令ID
        command_id = generate_command_id()
        
        # 保存命令到队列
        client_commands[client_id] = client_commands.get(client_id, [])
        command = {
            "id": command_id,
            "type": "read_file",
            "file_path": file_path,
            "timestamp": datetime.datetime.now().isoformat()
        }
        client_commands[client_id].append(command)
        
        # 保存到缓存
        file_read_cache[cache_key] = {"command_id": command_id}
        file_read_cache_time[cache_key] = current_time
        
        return jsonify({
            "status": "success", 
            "message": "命令已加入队列", 
            "command_id": command_id
        }), 200
    except Exception as e:
        print(f"文件读取请求错误: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"请求处理错误: {str(e)}"
        }), 500

# 实时按键记录API
@app.route('/realtime_keylog', methods=['POST'])
def realtime_keylog():
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
            
        # 检查必要字段
        if 'client_id' not in data:
            return jsonify({'error': '缺少客户端ID'}), 400
            
        if 'key_data' not in data:
            return jsonify({'error': '缺少按键数据'}), 400
            
        client_id = data['client_id']
        key_data_list = data['key_data']
        
        # 保存按键记录
        if client_id not in realtime_keylog_buffer:
            realtime_keylog_buffer[client_id] = []
        
        # 添加到缓冲区 - 支持列表或单个值
        if isinstance(key_data_list, list):
            # 如果是列表，添加全部项
            realtime_keylog_buffer[client_id].extend(key_data_list)
        else:
            # 兼容旧版，如果是单个值，就添加这个值
            realtime_keylog_buffer[client_id].append(key_data_list)
        
        # 限制缓冲区大小
        if len(realtime_keylog_buffer[client_id]) > max_buffer_size:
            realtime_keylog_buffer[client_id] = realtime_keylog_buffer[client_id][-max_buffer_size:]
            
        # 通过WebSocket广播按键事件
        try:
            # 如果是列表，发送最后一个按键作为实时事件
            if isinstance(key_data_list, list) and key_data_list:
                latest_key = key_data_list[-1]
            else:
                latest_key = key_data_list
                
            socketio.emit('keylog_event', {
                'client_id': client_id, 
                'key_data': latest_key,
                'hostname': data.get('hostname', '未知'),
                'username': data.get('username', '未知')
            }, namespace='/keylog')
        except Exception as e:
            print(f"WebSocket发送键盘记录错误: {str(e)}")
            # 即使WebSocket发送失败，仍然继续处理
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"实时按键记录错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 获取实时按键记录历史
@app.route('/api/keylog_history/<client_id>', methods=['GET'])
def get_keylog_history(client_id):
    try:
        # 返回缓冲区中的按键记录
        if client_id in realtime_keylog_buffer:
            return jsonify({
                'client_id': client_id,
                'keylog': realtime_keylog_buffer[client_id]
            }), 200
        else:
            return jsonify({
                'client_id': client_id,
                'keylog': []
            }), 200
    except Exception as e:
        print(f"获取按键记录历史错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 启动键盘记录实时模式API
@app.route('/api/keylog_realtime/<client_id>/start', methods=['POST'])
def start_keylog_realtime(client_id):
    try:
        current_time = time.time()
        
        # 启动实时模式会话（10秒有效期）
        keylog_realtime_sessions[client_id] = {
            'active': True,
            'last_request_time': current_time,
            'expiry_time': current_time + 10  # 10秒后过期
        }
        
        # 重置已发送索引，从头开始发送数据
        realtime_keylog_sent_index[client_id] = 0
        
        print(f"启动客户端 {client_id} 键盘记录实时模式")
        return jsonify({'status': 'success', 'message': '实时模式已启动', 'expiry_time': current_time + 10}), 200
        
    except Exception as e:
        print(f"启动键盘记录实时模式错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 停止键盘记录实时模式API
@app.route('/api/keylog_realtime/<client_id>/stop', methods=['POST'])
def stop_keylog_realtime(client_id):
    try:
        if client_id in keylog_realtime_sessions:
            del keylog_realtime_sessions[client_id]
            print(f"停止客户端 {client_id} 键盘记录实时模式")
        
        # 清理已发送索引
        if client_id in realtime_keylog_sent_index:
            del realtime_keylog_sent_index[client_id]
        
        return jsonify({'status': 'success', 'message': '实时模式已停止'}), 200
        
    except Exception as e:
        print(f"停止键盘记录实时模式错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 刷新键盘记录实时模式API（延长有效期）
@app.route('/api/keylog_realtime/<client_id>/refresh', methods=['POST'])
def refresh_keylog_realtime(client_id):
    try:
        current_time = time.time()
        
        if client_id in keylog_realtime_sessions:
            # 延长会话有效期
            keylog_realtime_sessions[client_id]['expiry_time'] = current_time + 10
            keylog_realtime_sessions[client_id]['last_request_time'] = current_time
            
            return jsonify({'status': 'success', 'message': '实时模式已刷新', 'expiry_time': current_time + 10}), 200
        else:
            return jsonify({'status': 'error', 'message': '实时模式未启动'}), 404
        
    except Exception as e:
        print(f"刷新键盘记录实时模式错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 接收实时键盘记录数据API (POST - 客户端上传数据)
@app.route('/api/keylog_realtime_data/<client_id>', methods=['POST'])
def receive_realtime_keylog_data(client_id):
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
            
        key_data_list = data.get('key_data', [])
        
        # 保存按键记录到实时缓冲区
        if client_id not in realtime_keylog_buffer:
            realtime_keylog_buffer[client_id] = []
        
        # 添加到缓冲区
        if isinstance(key_data_list, list):
            realtime_keylog_buffer[client_id].extend(key_data_list)
        else:
            realtime_keylog_buffer[client_id].append(key_data_list)
        
        # 限制缓冲区大小
        if len(realtime_keylog_buffer[client_id]) > max_buffer_size:
            realtime_keylog_buffer[client_id] = realtime_keylog_buffer[client_id][-max_buffer_size:]
        
        print(f"接收到客户端 {client_id} 实时键盘数据: {len(key_data_list)} 条记录")
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"接收实时键盘记录数据错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 获取实时键盘记录数据API (GET - 前端获取数据)
@app.route('/api/keylog_realtime_data/<client_id>', methods=['GET'])
def get_realtime_keylog_data(client_id):
    try:
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({'error': '客户端不存在'}), 404
        
        # 检查是否有活跃的实时会话
        current_time = time.time()
        if client_id not in keylog_realtime_sessions:
            return jsonify({
                'status': 'success',
                'keylog_data': [],
                'session_active': False
            }), 200
        
        session = keylog_realtime_sessions[client_id]
        if current_time > session.get('expiry_time', 0):
            # 会话已过期，清理
            del keylog_realtime_sessions[client_id]
            if client_id in realtime_keylog_sent_index:
                del realtime_keylog_sent_index[client_id]
            return jsonify({
                'status': 'success',
                'keylog_data': [],
                'session_active': False
            }), 200
        
        # 获取新的实时键盘数据（只返回未发送的数据）
        keylog_data = []
        if client_id in realtime_keylog_buffer:
            buffer = realtime_keylog_buffer[client_id]
            last_sent_index = realtime_keylog_sent_index.get(client_id, 0)
            
            # 获取新数据（从上次发送位置开始）
            if len(buffer) > last_sent_index:
                keylog_data = buffer[last_sent_index:]
                # 更新已发送索引
                realtime_keylog_sent_index[client_id] = len(buffer)
        
        return jsonify({
            'status': 'success',
            'keylog_data': keylog_data,
            'session_active': True,
            'session_expiry': session.get('expiry_time', 0)
        }), 200
        
    except Exception as e:
        print(f"获取实时键盘数据错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 注意：WebSocket相关代码已移除，改用纯HTTP轮询方式



# 实时日志API
@app.route('/realtime_log', methods=['POST'])
def realtime_log():
    try:
        data = request.get_json()
        if not data or 'client_id' not in data or 'log_entry' not in data:
            return jsonify({'error': '无效的请求数据'}), 400
            
        client_id = data['client_id']
        log_entry = data['log_entry']
        
        # 保存日志
        if client_id not in realtime_log_buffer:
            realtime_log_buffer[client_id] = []
        
        # 添加到缓冲区
        realtime_log_buffer[client_id].append(log_entry)
        
        # 限制缓冲区大小
        if len(realtime_log_buffer[client_id]) > max_log_buffer_size:
            realtime_log_buffer[client_id] = realtime_log_buffer[client_id][-max_log_buffer_size:]
        
        # 注意：WebSocket广播已移除，现在使用HTTP轮询方式获取日志
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"实时日志接收错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 获取实时日志历史
@app.route('/api/log_history/<client_id>', methods=['GET'])
def get_log_history(client_id):
    try:
        # 返回缓冲区中的日志记录
        if client_id in realtime_log_buffer:
            return jsonify({
                'client_id': client_id,
                'logs': realtime_log_buffer[client_id]
            }), 200
        else:
            return jsonify({
                'client_id': client_id,
                'logs': []
            }), 200
    except Exception as e:
        print(f"获取日志记录历史错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 查看客户端日志页面
@app.route('/logs/<client_id>')
def view_logs(client_id):
    # 获取所有客户端信息
    clients_file = os.path.join(app.config["UPLOAD_FOLDER"], "clients.json")
    clients = {}
    if os.path.exists(clients_file):
        try:
            with open(clients_file, "r") as f:
                clients = json.load(f)
        except Exception as e:
            print(f"加载客户端信息错误: {str(e)}")
    
    # 获取特定客户端信息
    client_info = clients.get(client_id, {})
    
    return render_template(
        "logs.html",
        client_id=client_id,
        client_info=client_info
    )

# 文件下载命令
@app.route('/api/download_file/<client_id>', methods=['POST'])
def download_file(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 获取请求参数
    data = request.json or {}
    file_path = data.get("file_path")
    
    if not file_path:
        return jsonify({"status": "error", "message": "未提供文件路径"}), 400
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "download_file",
        "file_path": file_path,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": "文件下载请求已发送",
        "command_id": command_id
    })

# 增加新路由处理下载目录中的文件
@app.route('/downloads/<client_id>/<path:filename>')
def download_file_direct(client_id, filename):
    download_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id, "download")
    if not os.path.exists(download_dir):
        return "下载目录不存在", 404
    
    # 文件名可能包含特殊字符，使用path:filename参数接收，不做额外处理
    return send_from_directory(download_dir, filename)

# API获取已下载文件
@app.route('/api/downloaded_files/<client_id>')
def get_downloaded_files(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"error": "客户端不存在"}), 404
            
        # 检查缓存
        current_time = time.time()
        if (client_id in downloaded_files_cache and 
            client_id in downloaded_files_cache_time and
            current_time - downloaded_files_cache_time[client_id] < CACHE_EXPIRY):
            return jsonify({
                "files": downloaded_files_cache[client_id], 
                "cached": True,
                "total_count": len(downloaded_files_cache[client_id])
            }), 200
        
        # 获取请求参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)  # 默认每页100个文件
        file_type = request.args.get('type')  # 可选的文件类型筛选
        
        # 限制每页最大数量
        if per_page > 500:
            per_page = 500
        
        # 获取客户端的下载文件
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        downloaded_files = []
        total_count = 0
        
        if os.path.exists(client_dir):
            try:
                # 只获取文件名，不获取详情
                all_files = []
                
                # 根据文件类型筛选
                if file_type == "screenshot":
                    file_prefix = "screen_"
                elif file_type == "video":
                    file_prefix = "record_"
                elif file_type == "keylog":
                    file_prefix = "keylog_"
                elif file_type == "sysinfo":
                    file_prefix = "sysinfo_"
                elif file_type == "download":
                    # 获取除了系统文件外的所有文件
                    all_files = [f for f in os.listdir(client_dir) 
                           if os.path.isfile(os.path.join(client_dir, f)) and 
                           not f.startswith(("screen_", "record_", "keylog_", "sysinfo_"))]
                else:
                    # 获取所有文件
                    all_files = [f for f in os.listdir(client_dir) if os.path.isfile(os.path.join(client_dir, f))]
                
                # 如果指定了类型但不是download
                if file_type and file_type != "download" and file_type != "all":
                    all_files = [f for f in os.listdir(client_dir) 
                                if os.path.isfile(os.path.join(client_dir, f)) and f.startswith(file_prefix)]
                
                # 记录总数量
                total_count = len(all_files)
                
                # 按修改时间排序前N个文件
                files_with_time = []
                for file in all_files:
                    try:
                        file_path = os.path.join(client_dir, file)
                        mtime = os.path.getmtime(file_path)
                        files_with_time.append((file, mtime))
                    except Exception:
                        # 忽略无法获取时间的文件
                        pass
                
                # 排序并分页
                files_with_time.sort(key=lambda x: x[1], reverse=True)
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paged_files = files_with_time[start_idx:end_idx]
                
                # 获取文件详情
                for file, mtime in paged_files:
                    try:
                        file_path = os.path.join(client_dir, file)
                        file_info = {
                            "name": file,
                            "path": f"{client_id}/{file}",
                            "size": os.path.getsize(file_path),
                            "modified": datetime.datetime.fromtimestamp(mtime).isoformat()
                        }
                        downloaded_files.append(file_info)
                    except Exception as e:
                        print(f"获取文件信息错误: {str(e)}")
        
            except Exception as e:
                print(f"列出目录内容错误: {str(e)}")
                return jsonify({"error": f"获取文件列表失败: {str(e)}"}), 500
        
        # 更新缓存
        if page == 1:  # 只缓存第一页
            downloaded_files_cache[client_id] = downloaded_files
            downloaded_files_cache_time[client_id] = current_time
        
        return jsonify({
            "files": downloaded_files,
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page
        }), 200
        
    except Exception as e:
        print(f"获取已下载文件出错: {str(e)}")
        return jsonify({"error": f"获取文件列表失败: {str(e)}"}), 500

# 批量删除文件API
@app.route('/api/batch_delete/<client_id>', methods=['POST'])
def batch_delete_files(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 获取要删除的文件列表
        data = request.json
        if not data or 'files' not in data:
            return jsonify({"status": "error", "message": "未提供文件列表"}), 400
            
        # 获取文件类型(可选)
        file_type = data.get('file_type', None)  # 'screenshot', 'video', 或 None(全部)
        
        files_to_delete = data['files']
        if not files_to_delete:
            return jsonify({"status": "error", "message": "文件列表为空"}), 400
        
        # 客户端目录
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        if not os.path.exists(client_dir):
            return jsonify({"status": "error", "message": "客户端目录不存在"}), 404
        
        # 删除结果
        results = {
            "success": [],
            "failed": []
        }
        
        # 删除文件
        for filename in files_to_delete:
            # 安全检查：确保文件名不包含路径分隔符
            if os.path.sep in filename:
                results["failed"].append({"file": filename, "reason": "无效的文件名"})
                continue
                
            # 如果指定了文件类型，进行检查
            if file_type == "screenshot" and not filename.startswith("screen_"):
                results["failed"].append({"file": filename, "reason": "不是截图文件"})
                continue
                
            if file_type == "video" and not filename.startswith("record_"):
                results["failed"].append({"file": filename, "reason": "不是录屏文件"})
                continue
            
            # 删除文件
            file_path = os.path.join(client_dir, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    results["success"].append(filename)
                else:
                    results["failed"].append({"file": filename, "reason": "文件不存在"})
            except Exception as e:
                results["failed"].append({"file": filename, "reason": str(e)})
        
        # 更新元数据
        try:
            metadata = load_metadata()
            if "clients" in metadata and client_id in metadata["clients"]:
                # 过滤元数据中的文件列表
                metadata["clients"][client_id]["files"] = [
                    file for file in metadata["clients"][client_id].get("files", [])
                    if file.get("filename") not in files_to_delete
                ]
                save_metadata(metadata)
        except Exception as e:
            print(f"更新元数据错误: {str(e)}")
            # 不影响删除操作的结果
        
        # 返回结果
        return jsonify({
            "status": "success", 
            "message": f"成功删除 {len(results['success'])} 个文件，失败 {len(results['failed'])} 个",
            "results": results
        })
        
    except Exception as e:
        print(f"批量删除文件错误: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败: {str(e)}"}), 500

# 设置自动清理配置API
@app.route('/api/auto_cleanup/config', methods=['POST'])
def set_auto_cleanup_config():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "未提供配置数据"}), 400
            
        # 更新配置
        if 'enabled' in data:
            app.config["AUTO_CLEANUP_ENABLED"] = bool(data['enabled'])
            
        if 'days' in data:
            try:
                days = int(data['days'])
                if days < 1:
                    days = 1  # 至少保留1单位
                app.config["AUTO_CLEANUP_DAYS"] = days
            except:
                return jsonify({"status": "error", "message": "保留时间必须是整数"}), 400
                
        if 'interval' in data:
            try:
                interval = int(data['interval'])
                if interval < 1:
                    interval = 1  # 至少每1小时执行一次
                app.config["AUTO_CLEANUP_INTERVAL"] = interval
            except:
                return jsonify({"status": "error", "message": "清理间隔必须是整数"}), 400
                
        if 'unit' in data:
            unit = data['unit']
            if unit in ["days", "hours", "minutes"]:
                app.config["AUTO_CLEANUP_UNIT"] = unit
            else:
                return jsonify({"status": "error", "message": "单位必须是 days、hours 或 minutes"}), 400
        
        # 保存配置到文件
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleanup_config.json")
        with open(config_path, "w") as f:
            json.dump({
                "enabled": app.config["AUTO_CLEANUP_ENABLED"],
                "days": app.config["AUTO_CLEANUP_DAYS"],
                "interval": app.config["AUTO_CLEANUP_INTERVAL"],
                "unit": app.config["AUTO_CLEANUP_UNIT"]
            }, f)
        
        # 重启清理定时任务
        if hasattr(app, 'cleanup_thread') and app.cleanup_thread:
            app.cleanup_thread_stop.set()
            app.cleanup_thread.join(timeout=5)
            
        if app.config["AUTO_CLEANUP_ENABLED"]:
            start_cleanup_thread()
            
        return jsonify({
            "status": "success",
            "message": "自动清理配置已更新",
            "config": {
                "enabled": app.config["AUTO_CLEANUP_ENABLED"],
                "days": app.config["AUTO_CLEANUP_DAYS"],
                "interval": app.config["AUTO_CLEANUP_INTERVAL"],
                "unit": app.config["AUTO_CLEANUP_UNIT"]
            }
        })
        
    except Exception as e:
        print(f"设置自动清理配置错误: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败: {str(e)}"}), 500

# 获取自动清理配置API
@app.route('/api/auto_cleanup/config', methods=['GET'])
def get_auto_cleanup_config():
    return jsonify({
        "status": "success",
        "config": {
            "enabled": app.config["AUTO_CLEANUP_ENABLED"],
            "days": app.config["AUTO_CLEANUP_DAYS"],
            "interval": app.config["AUTO_CLEANUP_INTERVAL"],
            "unit": app.config.get("AUTO_CLEANUP_UNIT", "days")
        }
    })

# 手动执行清理API
@app.route('/api/auto_cleanup/run', methods=['POST'])
def run_auto_cleanup():
    try:
        # 获取请求参数
        data = request.json or {}
        days = data.get('days', app.config["AUTO_CLEANUP_DAYS"])
        unit = data.get('unit', app.config.get("AUTO_CLEANUP_UNIT", "days"))
        
        try:
            days = int(days)
            if days < 0:
                days = 0  # 0表示清理所有
        except:
            return jsonify({"status": "error", "message": "时间值必须是整数"}), 400
        
        # 根据单位转换为天数
        if unit == "hours":
            days = days / 24
        elif unit == "minutes":
            days = days / (24 * 60)
            
        # 执行清理
        result = perform_cleanup(days)
        
        return jsonify({
            "status": "success",
            "message": f"清理操作已完成，已删除 {result['total_deleted']} 个文件",
            "details": result
        })
        
    except Exception as e:
        print(f"手动执行清理错误: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败: {str(e)}"}), 500

# 清理线程函数
def cleanup_thread_function(stop_event):
    while not stop_event.is_set():
        try:
            if app.config["AUTO_CLEANUP_ENABLED"]:
                print(f"执行自动清理，保留 {app.config['AUTO_CLEANUP_DAYS']} 天数据")
                result = perform_cleanup(app.config["AUTO_CLEANUP_DAYS"])
                print(f"自动清理完成，已删除 {result['total_deleted']} 个文件")
        except Exception as e:
            print(f"自动清理错误: {str(e)}")
            
        # 等待指定时间，或者直到收到停止信号
        for _ in range(app.config["AUTO_CLEANUP_INTERVAL"] * 60 * 60):  # 转换为秒
            if stop_event.is_set():
                break
            time.sleep(1)

# 执行清理操作    
def perform_cleanup(days):
    # 根据单位转换为天数
    unit = app.config.get("AUTO_CLEANUP_UNIT", "days")
    if unit == "hours":
        days = days / 24
    elif unit == "minutes":
        days = days / (24 * 60)
    
    # 计算截止日期
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    cutoff_timestamp = cutoff_date.isoformat()
    
    result = {
        "total_deleted": 0,
        "screenshots_deleted": 0,
        "videos_deleted": 0,
        "keylogs_deleted": 0,
        "other_deleted": 0,
        "by_client": {}
    }
    
    # 加载元数据
    metadata = load_metadata()
    if "clients" not in metadata:
        return result
    
    # 遍历所有客户端
    for client_id, client_data in metadata["clients"].items():
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        if not os.path.exists(client_dir):
            continue
            
        result["by_client"][client_id] = {
            "screenshots_deleted": 0,
            "videos_deleted": 0,
            "keylogs_deleted": 0,
            "other_deleted": 0
        }
            
        # 过滤出要保留的文件
        files_to_keep = []
        files_to_delete = []
        
        for file_record in client_data.get("files", []):
            if "timestamp" in file_record and file_record["timestamp"] > cutoff_timestamp:
                files_to_keep.append(file_record)
            else:
                files_to_delete.append(file_record)
                
                # 删除文件
                filename = file_record.get("filename")
                if filename:
                    file_path = os.path.join(client_dir, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            result["total_deleted"] += 1
                            
                            # 统计不同类型的文件
                            if filename.startswith("screen_"):
                                result["screenshots_deleted"] += 1
                                result["by_client"][client_id]["screenshots_deleted"] += 1
                            elif filename.startswith("record_"):
                                result["videos_deleted"] += 1
                                result["by_client"][client_id]["videos_deleted"] += 1
                            elif filename.startswith("keylog_"):
                                result["keylogs_deleted"] += 1
                                result["by_client"][client_id]["keylogs_deleted"] += 1
                            else:
                                result["other_deleted"] += 1
                                result["by_client"][client_id]["other_deleted"] += 1
                    except Exception as e:
                        print(f"删除文件错误 {file_path}: {str(e)}")
        
        # 更新元数据
        client_data["files"] = files_to_keep
    
    # 保存更新后的元数据
    save_metadata(metadata)
    
    # 删除孤立文件（不在元数据中但存在于文件系统的文件）
    for client_id in os.listdir(app.config["UPLOAD_FOLDER"]):
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        if not os.path.isdir(client_dir):
            continue
            
        # 如果客户端不在元数据中，跳过
        if client_id not in metadata.get("clients", {}):
            continue
            
        # 获取元数据中的文件名列表
        metadata_files = [file.get("filename") for file in metadata["clients"][client_id].get("files", [])]
        
        # 检查目录中的文件
        for filename in os.listdir(client_dir):
            # 如果文件不在元数据中，删除它
            if filename not in metadata_files and not filename.startswith("."):
                try:
                    file_path = os.path.join(client_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        result["total_deleted"] += 1
                        # 统计不同类型的文件
                        if filename.startswith("screen_"):
                            result["screenshots_deleted"] += 1
                            result["by_client"].setdefault(client_id, {})
                            result["by_client"][client_id].setdefault("screenshots_deleted", 0)
                            result["by_client"][client_id]["screenshots_deleted"] += 1
                        elif filename.startswith("record_"):
                            result["videos_deleted"] += 1
                            result["by_client"].setdefault(client_id, {})
                            result["by_client"][client_id].setdefault("videos_deleted", 0)
                            result["by_client"][client_id]["videos_deleted"] += 1
                        elif filename.startswith("keylog_"):
                            result["keylogs_deleted"] += 1
                            result["by_client"].setdefault(client_id, {})
                            result["by_client"][client_id].setdefault("keylogs_deleted", 0)
                            result["by_client"][client_id]["keylogs_deleted"] += 1
                        else:
                            result["other_deleted"] += 1
                            result["by_client"].setdefault(client_id, {})
                            result["by_client"][client_id].setdefault("other_deleted", 0)
                            result["by_client"][client_id]["other_deleted"] += 1
                except Exception as e:
                    print(f"删除孤立文件错误 {file_path}: {str(e)}")
    
    return result

# 启动清理线程
def start_cleanup_thread():
    if not app.config["AUTO_CLEANUP_ENABLED"]:
        return
        
    # 创建停止事件和线程
    app.cleanup_thread_stop = threading.Event()
    app.cleanup_thread = threading.Thread(
        target=cleanup_thread_function, 
        args=(app.cleanup_thread_stop,),
        daemon=True
    )
    app.cleanup_thread.start()
    print(f"自动清理线程已启动，保留 {app.config['AUTO_CLEANUP_DAYS']} 天数据，每 {app.config['AUTO_CLEANUP_INTERVAL']} 小时执行一次")

# 后台截图任务线程
def background_capture_thread(stop_event):
    while not stop_event.is_set():
        try:
            if app.config["BACKGROUND_CAPTURE_ENABLED"]:
                clients_to_capture = list(app.config["BACKGROUND_CAPTURE_CLIENTS"].keys())
                
                if clients_to_capture:
                    print(f"执行后台截图，目标客户端：{len(clients_to_capture)}个")
                    
                    for client_id in clients_to_capture:
                        try:
                            client_config = app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id]
                            if not client_config.get("enabled", False):
                                continue
                                
                            # 获取上次捕获的时间
                            last_capture_time = client_config.get("last_capture_time", 0)
                            current_time = time.time()
                            interval = client_config.get("interval", app.config["BACKGROUND_CAPTURE_INTERVAL"])
                            
                            # 检查是否需要执行捕获
                            if current_time - last_capture_time < interval:
                                continue
                                
                            # 根据配置执行不同类型的捕获
                            capture_types = client_config.get("capture_types", ["screenshot"])
                            
                            if "screenshot" in capture_types:
                                # 创建截图命令
                                command_id = generate_command_id()
                                command = {
                                    "id": command_id,
                                    "type": "take_screenshot",
                                    "source": "background_capture",
                                    "timestamp": datetime.datetime.now().isoformat()
                                }
                                
                                # 添加到命令队列
                                if client_id not in client_commands:
                                    client_commands[client_id] = []
                                
                                client_commands[client_id].append(command)
                                print(f"已为客户端 {client_id} 创建后台截图命令: {command_id}")
                            
                            if "record" in capture_types and client_config.get("record_duration"):
                                # 创建录屏命令
                                command_id = generate_command_id()
                                command = {
                                    "id": command_id,
                                    "type": "start_recording",
                                    "source": "background_capture",
                                    "timestamp": datetime.datetime.now().isoformat(),
                                    "duration": client_config.get("record_duration", 60),
                                    "fps": client_config.get("record_fps", 10)
                                }
                                
                                # 添加到命令队列
                                if client_id not in client_commands:
                                    client_commands[client_id] = []
                                
                                client_commands[client_id].append(command)
                                print(f"已为客户端 {client_id} 创建后台录屏命令: {command_id}")
                                
                            # 更新最后捕获时间
                            client_config["last_capture_time"] = current_time
                            app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id] = client_config
                            
                        except Exception as e:
                            print(f"为客户端 {client_id} 执行后台捕获时出错: {str(e)}")
                
        except Exception as e:
            print(f"后台捕获线程错误: {str(e)}")
            
        # 每5秒检查一次
        for _ in range(5):
            if stop_event.is_set():
                break
            time.sleep(1)

# 启动后台捕获线程
def start_background_capture_thread():
    if not app.config["BACKGROUND_CAPTURE_ENABLED"]:
        return
        
    # 创建停止事件和线程
    app.background_capture_thread_stop = threading.Event()
    app.background_capture_thread = threading.Thread(
        target=background_capture_thread, 
        args=(app.background_capture_thread_stop,),
        daemon=True
    )
    app.background_capture_thread.start()
    print(f"后台捕获线程已启动")

# 后台捕获配置API
@app.route('/api/background_capture/config', methods=['GET'])
def get_background_capture_config():
    return jsonify({
        "status": "success",
        "config": {
            "enabled": app.config["BACKGROUND_CAPTURE_ENABLED"],
            "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"],
            "clients": app.config["BACKGROUND_CAPTURE_CLIENTS"]
        }
    })

# 设置后台捕获全局配置
@app.route('/api/background_capture/config', methods=['POST'])
def set_background_capture_config():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "未提供配置数据"}), 400
            
        # 更新配置
        if 'enabled' in data:
            app.config["BACKGROUND_CAPTURE_ENABLED"] = bool(data['enabled'])
            
        if 'interval' in data:
            try:
                interval = int(data['interval'])
                if interval < 5:
                    interval = 5  # 最小5秒
                app.config["BACKGROUND_CAPTURE_INTERVAL"] = interval
            except:
                return jsonify({"status": "error", "message": "间隔必须是整数"}), 400
        
        # 保存配置到文件
        capture_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background_capture_config.json")
        with open(capture_config_path, "w") as f:
            json.dump({
                "enabled": app.config["BACKGROUND_CAPTURE_ENABLED"],
                "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"],
                "clients": app.config["BACKGROUND_CAPTURE_CLIENTS"]
            }, f)
        
        # 重启捕获线程
        if hasattr(app, 'background_capture_thread') and app.background_capture_thread:
            app.background_capture_thread_stop.set()
            app.background_capture_thread.join(timeout=5)
            
        if app.config["BACKGROUND_CAPTURE_ENABLED"]:
            start_background_capture_thread()
            
        return jsonify({
            "status": "success",
            "message": "后台捕获配置已更新",
            "config": {
                "enabled": app.config["BACKGROUND_CAPTURE_ENABLED"],
                "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"]
            }
        })
        
    except Exception as e:
        print(f"设置后台捕获配置错误: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败: {str(e)}"}), 500

# 配置客户端的后台捕获设置
@app.route('/api/background_capture/client/<client_id>', methods=['POST'])
def set_client_background_capture(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "未提供配置数据"}), 400
            
        # 更新客户端配置
        client_config = app.config["BACKGROUND_CAPTURE_CLIENTS"].get(client_id, {
            "enabled": False,
            "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"],
            "capture_types": ["screenshot"],
            "record_duration": 60,
            "record_fps": 10,
            "last_capture_time": 0
        })
        
        # 更新配置
        for key in ["enabled", "interval", "capture_types", "record_duration", "record_fps"]:
            if key in data:
                client_config[key] = data[key]
        
        # 重置最后捕获时间，确保下次检查时立即执行捕获
        if data.get("reset_timer", False):
            client_config["last_capture_time"] = 0
        
        # 保存回全局配置
        app.config["BACKGROUND_CAPTURE_CLIENTS"][client_id] = client_config
        
        # 保存配置到文件
        capture_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background_capture_config.json")
        with open(capture_config_path, "w") as f:
            json.dump({
                "enabled": app.config["BACKGROUND_CAPTURE_ENABLED"],
                "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"],
                "clients": app.config["BACKGROUND_CAPTURE_CLIENTS"]
            }, f)
        
        return jsonify({
            "status": "success",
            "message": "客户端后台捕获配置已更新",
            "config": client_config
        })
        
    except Exception as e:
        print(f"设置客户端后台捕获配置错误: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败: {str(e)}"}), 500

# 获取客户端的后台捕获设置
@app.route('/api/background_capture/client/<client_id>', methods=['GET'])
def get_client_background_capture(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
    # 获取客户端配置
    client_config = app.config["BACKGROUND_CAPTURE_CLIENTS"].get(client_id, {
        "enabled": False,
        "interval": app.config["BACKGROUND_CAPTURE_INTERVAL"],
        "capture_types": ["screenshot"],
        "record_duration": 60,
        "record_fps": 10,
        "last_capture_time": 0
    })
    
    return jsonify({
        "status": "success",
        "config": client_config,
        "global_enabled": app.config["BACKGROUND_CAPTURE_ENABLED"]
    })

# 加载后台键盘捕获配置
def load_background_keylog_config():
    try:
        with open(background_keylog_config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取后台键盘捕获配置错误: {str(e)}")
        return {}

# 保存后台键盘捕获配置
def save_background_keylog_config(configs):
    try:
        with open(background_keylog_config_file, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except Exception as e:
        print(f"保存后台键盘捕获配置错误: {str(e)}")
        return False

# 获取后台键盘捕获状态
@app.route('/api/background_keylog/status/<client_id>', methods=['GET'])
def get_background_keylog_status(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 获取配置
    configs = load_background_keylog_config()
    enabled = configs.get(client_id, {}).get("enabled", False)
    
    return jsonify({
        "status": "success", 
        "enabled": enabled
    })

# 切换后台键盘捕获
@app.route('/api/background_keylog/toggle/<client_id>', methods=['POST'])
def toggle_background_keylog(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 获取请求数据
    data = request.json
    if not data or "enabled" not in data:
        return jsonify({"status": "error", "message": "无效的请求数据"}), 400
    
    enabled = data["enabled"]
    
    # 更新配置
    configs = load_background_keylog_config()
    
    if client_id not in configs:
        configs[client_id] = {}
    
    # 更新启用状态
    configs[client_id]["enabled"] = enabled
    
    # 如果启用，则设置默认配置参数
    if enabled:
        configs[client_id]["interval"] = configs[client_id].get("interval", 0.5)  # 默认0.5秒间隔
        configs[client_id]["buffer_size"] = configs[client_id].get("buffer_size", 100)  # 默认缓冲区大小
        
        # 添加命令到客户端队列
        command_id = generate_command_id()
        command = {
            "command": "start_background_keylog",
            "params": {
                "interval": configs[client_id]["interval"],
                "buffer_size": configs[client_id]["buffer_size"]
            }
        }
        
        if client_id not in client_commands:
            client_commands[client_id] = []
            
        client_commands[client_id].append({"id": command_id, "command": command})
        
        message = "后台键盘捕获已启用"
    else:
        # 添加停止命令到客户端队列
        command_id = generate_command_id()
        command = {
            "command": "stop_background_keylog"
        }
        
        if client_id not in client_commands:
            client_commands[client_id] = []
            
        client_commands[client_id].append({"id": command_id, "command": command})
        
        message = "后台键盘捕获已禁用"
    
    # 保存配置
    if save_background_keylog_config(configs):
        return jsonify({
            "status": "success", 
            "message": message,
            "command_id": command_id
        })
    else:
        return jsonify({"status": "error", "message": "保存配置失败"}), 500

# 暂停/恢复截屏API
@app.route('/api/pause_screenshot/<client_id>', methods=['POST'])
def pause_screenshot(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
    # 获取请求数据
    data = request.json or {}
    paused = data.get('paused', True)  # 默认暂停
    save_persistent = data.get('save_persistent', True)  # 默认持久化保存设置
    
    # 加载当前配置
    client_configs = load_client_configs()
    
    # 如果该客户端没有配置，则使用默认配置
    if client_id not in client_configs:
        client_configs[client_id] = get_default_client_config()
    
    # 更新暂停状态
    client_configs[client_id]["screenshot_paused"] = paused
    
    # 保存配置到客户端配置
    config_saved = save_client_configs(client_configs)
    
    # 保存到暂停配置文件（用于客户端轮询检查）
    pause_configs = load_pause_config()
    pause_configs[client_id] = {
        "paused": paused,
        "updated_at": datetime.datetime.now().isoformat()
    }
    pause_config_saved = save_pause_config(pause_configs)
    
    if config_saved and pause_config_saved:
        # 创建命令通知客户端
        command_id = generate_command_id()
        command = {
            "id": command_id,
            "type": "update_config",
            "config": {"screenshot_paused": paused},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        
        # 如果需要持久化保存设置则发送命令
        if save_persistent:
            client_commands[client_id].append(command)
        
        return jsonify({
            "status": "success", 
            "message": "截屏已" + ("暂停" if paused else "恢复"),
            "config": {"screenshot_paused": paused},
            "command_id": command_id
        })
    else:
        return jsonify({"status": "error", "message": "保存配置失败"}), 500

# 设置历史键盘记录状态API
@app.route('/api/historical_keylog/<client_id>', methods=['POST'])
def set_historical_keylog(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
    # 获取请求数据
    data = request.json or {}
    enabled = data.get('enabled', True)  # 默认启用
    
    # 加载当前配置
    client_configs = load_client_configs()
    
    # 如果该客户端没有配置，则使用默认配置
    if client_id not in client_configs:
        client_configs[client_id] = get_default_client_config()
    
    # 更新状态
    client_configs[client_id]["enable_historical_keylog"] = enabled
    
    # 保存配置
    if save_client_configs(client_configs):
        # 创建命令通知客户端
        command_id = generate_command_id()
        command = {
            "id": command_id,
            "type": "update_config",
            "config": {"enable_historical_keylog": enabled},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        
        client_commands[client_id].append(command)
        
        return jsonify({
            "status": "success", 
            "message": "历史键盘记录已" + ("启用" if enabled else "禁用"),
            "config": {"enable_historical_keylog": enabled},
            "command_id": command_id
        })
    else:
        return jsonify({"status": "error", "message": "保存配置失败"}), 500

# 键盘记录设置API
@app.route('/api/keylog_settings/<client_id>', methods=['POST'])
def update_keylog_settings(client_id):
    # 验证客户端是否存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
    # 获取请求数据
    data = request.json or {}
    enable_realtime_keylog = data.get('enable_realtime_keylog')
    enable_historical_keylog = data.get('enable_historical_keylog')
    save_persistent = data.get('save_persistent', False)  # 是否持久化保存设置
    
    # 加载当前配置
    client_configs = load_client_configs()
    
    # 如果该客户端没有配置，则使用默认配置
    if client_id not in client_configs:
        client_configs[client_id] = get_default_client_config()
    
    # 更新配置
    updated_config = {}
    
    if enable_realtime_keylog is not None:
        client_configs[client_id]["enable_realtime_keylog"] = enable_realtime_keylog
        updated_config["enable_realtime_keylog"] = enable_realtime_keylog
    
    if enable_historical_keylog is not None:
        client_configs[client_id]["enable_historical_keylog"] = enable_historical_keylog
        updated_config["enable_historical_keylog"] = enable_historical_keylog
    
    # 保存配置
    if save_client_configs(client_configs):
        # 创建命令通知客户端
        command_id = generate_command_id()
        command = {
            "id": command_id,
            "type": "update_config",
            "config": updated_config,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        
        # 只有在需要持久化保存设置时才发送命令
        if save_persistent:
            client_commands[client_id].append(command)
        
        messages = []
        if enable_realtime_keylog is not None:
            messages.append("实时键盘记录已" + ("启用" if enable_realtime_keylog else "禁用"))
        if enable_historical_keylog is not None:
            messages.append("历史键盘记录已" + ("启用" if enable_historical_keylog else "禁用"))
        
        return jsonify({
            "status": "success", 
            "message": "、".join(messages),
            "config": updated_config,
            "command_id": command_id
        })
    else:
        return jsonify({"status": "error", "message": "保存配置失败"}), 500

# 运行服务器
if __name__ == "__main__":
    try:
        # 启动清理线程
        start_cleanup_thread()
        
        # 启动后台捕获线程
        start_background_capture_thread()
        
        # 启动分块上传清理线程
        start_upload_cleanup_thread()
        
        # 启动服务器 (移除SocketIO依赖，使用普通Flask)
        app.run(debug=True, host="0.0.0.0", port=5000)
    except Exception as e:
        print(f"服务启动失败: {str(e)}")
    finally:
        cleanup_stop_event.set()
        capture_stop_event.set() 

# 获取暂停状态API
@app.route('/api/pause_status/<client_id>', methods=['GET'])
def get_pause_status(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 从暂停配置文件获取状态
        pause_configs = load_pause_config()
        
        # 获取暂停状态，默认为不暂停
        pause_info = pause_configs.get(client_id, {"paused": False, "updated_at": datetime.datetime.now().isoformat()})
        
        # 同时获取客户端配置，确保两处配置一致
        client_configs = load_client_configs()
        
        # 如果客户端配置中有暂停状态，优先使用
        if client_id in client_configs and "screenshot_paused" in client_configs[client_id]:
            # 检查配置是否一致，如果不一致则更新暂停配置文件
            client_paused = client_configs[client_id]["screenshot_paused"]
            if client_paused != pause_info["paused"]:
                pause_configs[client_id] = {
                    "paused": client_paused,
                    "updated_at": datetime.datetime.now().isoformat()
                }
                save_pause_config(pause_configs)
                pause_info = pause_configs[client_id]
        
        return jsonify({
            "status": "success",
            "paused": pause_info["paused"],
            "updated_at": pause_info["updated_at"]
        })
    except Exception as e:
        print(f"获取暂停状态错误: {str(e)}")
        return jsonify({"status": "error", "message": f"获取暂停状态失败: {str(e)}"}), 500

# 获取下载文件夹中的文件API
@app.route('/api/download_folder_files/<client_id>', methods=['GET'])
def get_download_folder_files(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 获取下载目录
        download_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id, "download")
        if not os.path.exists(download_dir):
            # 如果目录不存在，创建它并返回空列表
            os.makedirs(download_dir, exist_ok=True)
            return jsonify({"status": "success", "files": []})
        
        # 获取目录中的所有文件
        files = []
        for filename in os.listdir(download_dir):
            file_path = os.path.join(download_dir, filename)
            if os.path.isfile(file_path):
                # 获取文件信息
                file_info = {
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                    "download_url": f"/downloads/{client_id}/{filename}"
                }
                files.append(file_info)
        
        # 按修改时间排序，最新的在前面
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return jsonify({
            "status": "success",
            "files": files
        })
        
    except Exception as e:
        print(f"获取下载文件夹内容出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"获取文件列表失败: {str(e)}"}), 500

# 文件有效期配置文件路径
download_expiry_config_file = os.path.join(app.config["UPLOAD_FOLDER"], "download_expiry_config.json")
if not os.path.exists(download_expiry_config_file):
    with open(download_expiry_config_file, "w") as f:
        json.dump({}, f)

# 加载下载文件有效期配置
def load_download_expiry_config():
    try:
        with open(download_expiry_config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载下载文件有效期配置错误: {str(e)}")
        return {}

# 保存下载文件有效期配置
def save_download_expiry_config(configs):
    try:
        with open(download_expiry_config_file, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except Exception as e:
        print(f"保存下载文件有效期配置错误: {str(e)}")
        return False

# 设置下载文件有效期API
@app.route('/api/download_expiry/<client_id>', methods=['POST'])
def set_download_expiry(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 获取请求数据
        data = request.json or {}
        expiry_value = data.get('expiry_value', 5)  # 默认5
        expiry_unit = data.get('expiry_unit', 'minutes')  # 默认分钟
        
        # 验证单位
        valid_units = ['minutes', 'hours', 'days']
        if expiry_unit not in valid_units:
            return jsonify({"status": "error", "message": f"无效的时间单位，只支持: {', '.join(valid_units)}"}), 400
        
        # 确保expiry_value是正整数或0(表示永不过期)
        try:
            expiry_value = int(expiry_value)
            if expiry_value < 0:
                return jsonify({"status": "error", "message": "有效期数值必须大于或等于0"}), 400
        except:
            return jsonify({"status": "error", "message": "有效期数值必须是整数"}), 400
        
        # 加载当前配置
        configs = load_download_expiry_config()
        
        # 更新配置
        configs[client_id] = {
            "expiry_value": expiry_value,
            "expiry_unit": expiry_unit,
            "updated_at": datetime.datetime.now().isoformat()
        }
        
        # 保存配置
        if save_download_expiry_config(configs):
            # 如果设置了有效期，立即执行一次清理
            if expiry_value > 0:
                clean_result = clean_expired_downloads(client_id)
                unit_text = {"minutes": "分钟", "hours": "小时", "days": "天"}[expiry_unit]
                return jsonify({
                    "status": "success",
                    "message": f"已设置下载文件有效期为{expiry_value}{unit_text}，并清理了{clean_result['deleted_count']}个过期文件",
                    "expiry_value": expiry_value,
                    "expiry_unit": expiry_unit,
                    "clean_result": clean_result
                })
            else:
                return jsonify({
                    "status": "success",
                    "message": "已设置下载文件永不过期",
                    "expiry_value": 0,
                    "expiry_unit": expiry_unit
                })
        else:
            return jsonify({"status": "error", "message": "保存配置失败"}), 500
    
    except Exception as e:
        print(f"设置下载文件有效期错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"设置有效期失败: {str(e)}"}), 500

# 获取下载文件有效期设置
@app.route('/api/download_expiry/<client_id>', methods=['GET'])
def get_download_expiry(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 加载配置
        configs = load_download_expiry_config()
        
        # 获取该客户端的配置，默认5分钟
        config = configs.get(client_id, {"expiry_value": 5, "expiry_unit": "minutes", "updated_at": None})
        
        return jsonify({
            "status": "success",
            "expiry_value": config["expiry_value"],
            "expiry_unit": config["expiry_unit"],
            "updated_at": config["updated_at"]
        })
        
    except Exception as e:
        print(f"获取下载文件有效期配置错误: {str(e)}")
        return jsonify({"status": "error", "message": f"获取配置失败: {str(e)}"}), 500

# 清理过期的下载文件
def clean_expired_downloads(client_id=None):
    try:
        # 加载配置
        configs = load_download_expiry_config()
        
        # 处理结果
        result = {
            "deleted_count": 0,
            "deleted_files": [],
            "error_files": []
        }
        
        # 如果指定了客户端ID，只清理该客户端
        if client_id:
            client_ids = [client_id] if client_id in configs else []
        else:
            # 清理所有客户端
            client_ids = list(configs.keys())
        
        # 逐个处理客户端
        for cid in client_ids:
            config = configs.get(cid, {})
            expiry_value = config.get("expiry_value", 5)
            expiry_unit = config.get("expiry_unit", "minutes")
            
            # 如果有效期为0，表示永不过期
            if expiry_value <= 0:
                continue
            
            # 根据单位计算截止日期
            if expiry_unit == "minutes":
                cutoff_date = datetime.datetime.now() - datetime.timedelta(minutes=expiry_value)
            elif expiry_unit == "hours":
                cutoff_date = datetime.datetime.now() - datetime.timedelta(hours=expiry_value)
            else:  # 默认按天计算
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=expiry_value)
                
            # 获取下载目录
            download_dir = os.path.join(app.config["UPLOAD_FOLDER"], cid, "download")
            if not os.path.exists(download_dir):
                continue
                
            # 遍历目录中的所有文件
            for filename in os.listdir(download_dir):
                file_path = os.path.join(download_dir, filename)
                if not os.path.isfile(file_path):
                    continue
                    
                # 获取文件最后修改时间
                file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # 如果超过有效期，删除文件
                if file_mtime < cutoff_date:
                    try:
                        os.remove(file_path)
                        result["deleted_count"] += 1
                        result["deleted_files"].append(filename)
                    except Exception as e:
                        result["error_files"].append({
                            "file": filename,
                            "error": str(e)
                        })
        
        return result
        
    except Exception as e:
        print(f"清理过期下载文件错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "deleted_count": 0,
            "deleted_files": [],
            "error_files": [{"file": "系统错误", "error": str(e)}]
        }

# 添加定期清理下载文件的任务
def start_download_cleanup_thread():
    def cleanup_thread_function():
        while True:
            try:
                # 每天执行一次清理
                print("执行下载文件过期清理...")
                result = clean_expired_downloads()
                print(f"清理完成，删除了{result['deleted_count']}个过期文件")
            except Exception as e:
                print(f"下载文件清理线程错误: {str(e)}")
            
            # 等待24小时
            time.sleep(24 * 60 * 60)
    
    thread = threading.Thread(target=cleanup_thread_function, daemon=True)
    thread.start()
    print("已启动下载文件清理线程")

# 在应用启动时启动清理线程
start_download_cleanup_thread()

# 录屏状态跟踪
recording_status = {}  # 格式: {client_id: {"status": "recording/idle", "start_time": timestamp, "type": "timed/realtime"}}

# 获取客户端录屏状态
@app.route('/api/recording_status/<client_id>', methods=['GET'])
def get_recording_status(client_id):
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 返回录屏状态，如果不存在则表示未录屏
        status = recording_status.get(client_id, {"status": "idle", "start_time": None, "type": None})
        
        return jsonify({
            "status": "success",
            "recording": status["status"] == "recording",
            "recording_status": status
        })
    
    except Exception as e:
        print(f"获取录屏状态错误: {str(e)}")
        return jsonify({"status": "error", "message": f"获取状态失败: {str(e)}"}), 500

# 实时录屏API - 开始
@app.route('/api/realtime_record/<client_id>', methods=['POST'])
def start_realtime_recording(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 获取录屏参数
    data = request.json or {}
    fps = data.get('fps', 10)
    
    try:
        fps = int(fps)
        if fps < 1:
            fps = 10
    except:
        fps = 10
    
    # 检查是否已经在录制
    current_status = recording_status.get(client_id, {}).get("status")
    if current_status == "recording":
        return jsonify({"status": "error", "message": "客户端已在录屏中"}), 400
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "start_realtime_recording",
        "timestamp": datetime.datetime.now().isoformat(),
        "fps": fps
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    # 更新录屏状态
    recording_status[client_id] = {
        "status": "recording",
        "start_time": datetime.datetime.now().isoformat(),
        "type": "realtime",
        "command_id": command_id
    }
    
    return jsonify({
        "status": "success", 
        "message": f"实时录屏命令已发送，帧率: {fps}fps",
        "command_id": command_id
    })

# 实时录屏API - 停止
@app.route('/api/stop_realtime_record/<client_id>', methods=['POST'])
def stop_realtime_recording(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 检查是否在录制
    current_status = recording_status.get(client_id, {}).get("status")
    if current_status != "recording":
        return jsonify({"status": "error", "message": "客户端没有在录屏中"}), 400
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "stop_recording",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    # 更新录屏状态
    recording_status[client_id] = {
        "status": "idle",
        "start_time": None,
        "type": None
    }
    
    return jsonify({
        "status": "success", 
        "message": "停止实时录屏命令已发送",
        "command_id": command_id
    })

# 强制停止所有录屏
@app.route('/api/force_stop_all_recordings/<client_id>', methods=['POST'])
def force_stop_all_recordings(client_id):
    if client_id not in get_all_clients():
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 创建命令
    command_id = generate_command_id()
    command = {
        "id": command_id,
        "type": "force_stop_all_recordings",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加到命令队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    
    client_commands[client_id].append(command)
    
    # 更新录屏状态
    recording_status[client_id] = {
        "status": "idle",
        "start_time": None,
        "type": None
    }
    
    return jsonify({
        "status": "success", 
        "message": "强制停止所有录屏命令已发送",
        "command_id": command_id
    })

# 客户端状态上报API
@app.route('/api/client_status/<client_id>', methods=['POST'])
def update_client_status(client_id):
    try:
        data = request.json or {}
        recording = data.get('recording', False)
        
        # 更新客户端信息
        client_info = {
            "client_id": client_id,
            "hostname": data.get('hostname', '未知'),
            "username": data.get('username', '未知'),
            "last_seen": datetime.datetime.now().isoformat()
        }
        save_client_info(client_info)
        
        # 更新录屏状态
        if recording:
            # 如果服务器没记录但客户端报告正在录制，更新状态
            if client_id not in recording_status or recording_status[client_id]["status"] != "recording":
                recording_status[client_id] = {
                    "status": "recording",
                    "start_time": data.get('recording_start_time', datetime.datetime.now().isoformat()),
                    "type": data.get('recording_type', 'unknown')
                }
        else:
            # 如果服务器记录正在录制但客户端报告没有，更新状态
            if client_id in recording_status and recording_status[client_id]["status"] == "recording":
                recording_status[client_id] = {
                    "status": "idle",
                    "start_time": None,
                    "type": None
                }
        
        return jsonify({
            "status": "success",
            "message": "状态更新成功"
        })
        
    except Exception as e:
        print(f"更新客户端状态错误: {str(e)}")
        return jsonify({"status": "error", "message": f"状态更新失败: {str(e)}"}), 500

# 添加API路由 - 获取截图列表
@app.route('/api/screenshot_list/<client_id>', methods=['GET'])
def get_screenshot_list(client_id):
    """获取指定客户端的所有截图列表"""
    
    # 验证客户端存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 获取上传目录中的截图
    client_upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
    if not os.path.exists(client_upload_dir):
        return jsonify({"status": "success", "screenshots": []})
    
    # 获取所有以screen_开头的jpg和png文件
    screenshots = [f for f in os.listdir(client_upload_dir) 
                  if f.startswith("screen_") and (f.endswith(".jpg") or f.endswith(".png"))]
    
    return jsonify({"status": "success", "screenshots": screenshots})

# 添加API路由 - 请求同步截图
@app.route('/api/sync_screenshots/<client_id>', methods=['POST'])
def sync_screenshots(client_id):
    """请求客户端同步截图"""
    
    # 验证客户端存在
    clients = get_all_clients()
    if client_id not in clients:
        return jsonify({"status": "error", "message": "客户端不存在"}), 404
    
    # 创建命令
    command = {
        "id": generate_command_id(),
        "type": "sync_screenshots",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 添加命令到队列
    if client_id not in client_commands:
        client_commands[client_id] = []
    client_commands[client_id].append(command)
    
    return jsonify({
        "status": "success", 
        "message": "同步截图命令已发送", 
        "command_id": command["id"]
    })

@app.route('/api/delete_keylog/<client_id>/<filename>', methods=['POST'])
def delete_keylog_file(client_id, filename):
    """删除指定客户端的键盘记录文件"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({
                'success': False,
                'message': f'客户端不存在: {client_id}'
            }), 404
        
        # 检查文件名是否以"keylog_"开头，确保只能删除键盘记录文件
        if not filename.startswith('keylog_'):
            return jsonify({
                'success': False,
                'message': '只能删除键盘记录文件'
            }), 400
            
        # 构建文件路径 - 使用与view_keylog函数相同的路径
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        file_path = os.path.join(client_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'文件不存在: {filename}'
            }), 404
            
        # 删除文件
        os.remove(file_path)
        
        # 记录删除操作
        print(f'已删除键盘记录文件: {filename} (客户端: {client_id})')
        
        return jsonify({
            'success': True,
            'message': f'键盘记录文件已删除: {filename}'
        }), 200
        
    except Exception as e:
        print(f'删除键盘记录文件错误: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'删除文件时出错: {str(e)}'
        }), 500

# 删除客户端
@app.route('/api/client/delete/<client_id>', methods=['POST'])
def delete_client(client_id):
    """删除指定的客户端"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({
                'success': False,
                'message': f'客户端不存在: {client_id}'
            }), 404

        # 删除客户端信息
        del clients[client_id]
        with open(clients_file, "w") as f:
            json.dump(clients, f, indent=2)

        # 清理相关文件夹
        client_dir = os.path.join(app.config["UPLOAD_FOLDER"], client_id)
        if os.path.exists(client_dir):
            shutil.rmtree(client_dir)

        # 删除下载目录
        download_dir = os.path.join(app.config["UPLOAD_FOLDER"], "download", client_id)
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)

        # 清理暂停配置
        pause_configs = load_pause_config()
        if client_id in pause_configs:
            del pause_configs[client_id]
            save_pause_config(pause_configs)

        # 清理客户端配置
        client_configs = load_client_configs()
        if client_id in client_configs:
            del client_configs[client_id]
            save_client_configs(client_configs)

        # 清理命令队列
        if client_id in client_commands:
            del client_commands[client_id]

        # 清理实时键盘记录缓冲区
        if client_id in realtime_keylog_buffer:
            del realtime_keylog_buffer[client_id]

        # 清理系统信息缓存
        if client_id in sysinfo_cache:
            del sysinfo_cache[client_id]

        # 清理实时日志缓冲区
        if client_id in realtime_log_buffer:
            del realtime_log_buffer[client_id]

        # 清理客户端实时查看状态
        if client_id in client_live_views:
            del client_live_views[client_id]

        return jsonify({
            'success': True,
            'message': f'客户端 {client_id} 已成功删除'
        })
    except Exception as e:
        print(f"删除客户端错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除客户端时发生错误: {str(e)}'
        }), 500

# 恢复客户端原始设置
@app.route('/api/client/reset/<client_id>', methods=['POST'])
def reset_client(client_id):
    """恢复客户端原始设置（不恢复IP）"""
    try:
        # 验证客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({
                'success': False,
                'message': f'客户端不存在: {client_id}'
            }), 404

        # 获取当前客户端配置
        client_configs = load_client_configs()
        
        # 保存当前服务器IP地址
        server_url = None
        if client_id in client_configs:
            server_url = client_configs[client_id].get("server_url")
        
        # 重置为默认配置
        default_config = get_default_client_config()
        
        # 保留原始IP地址
        if server_url:
            default_config["server_url"] = server_url
            
        # 将first_run_completed设置为False，触发初次使用界面
        default_config["first_run_completed"] = False
        
        # 更新客户端配置
        client_configs[client_id] = default_config
        save_client_configs(client_configs)
        
        # 创建命令告知客户端配置已重置
        cmd_id = generate_command_id()
        cmd = {
            "id": cmd_id,
            "type": "reset_config",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加到命令队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        client_commands[client_id].append(cmd)
        
        # 添加到命令状态
        command_status[cmd_id] = {
            "client_id": client_id,
            "command": cmd,
            "status": "pending",
            "message": "等待客户端执行",
            "timestamp": datetime.datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'message': f'客户端 {client_id} 的配置已重置为初始状态，保留了服务器IP地址'
        })
    except Exception as e:
        print(f"重置客户端配置错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'重置客户端配置时发生错误: {str(e)}'
        }), 500

# 添加初始化验证状态变量和配置文件路径（在文件开头已经定义）
verification_status = {}  # 格式: {client_id: {is_verification_needed, key, attempts_left, start_time, end_time, is_verified}}

# 加载验证配置
def load_verification_config():
    """加载验证配置文件"""
    try:
        with open(verification_config_file, "r") as f:
            return json.load(f)
    except:
        return {}  # 如果文件不存在或无法解析，返回空字典

# 保存验证配置
def save_verification_config(configs):
    """保存验证配置到文件"""
    try:
        with open(verification_config_file, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except:
        return False

# API: 更新客户端验证状态
@app.route('/api/verification/status/<client_id>', methods=['POST'])
def update_verification_status(client_id):
    """更新客户端的验证状态"""
    try:
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        data = request.json
        required_fields = ["is_verification_needed", "attempts_left",
                         "verification_start_time", "verification_end_time", "is_verified"]
        
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": "缺少必要的状态字段"}), 400
        
        # 更新验证状态，包含永久验证状态和机器码
        verification_status[client_id] = {
            "is_verification_needed": data["is_verification_needed"],
            "attempts_left": data["attempts_left"],
            "start_time": data["verification_start_time"],
            "end_time": data["verification_end_time"],
            "is_verified": data["is_verified"],
            "is_permanent_activated": data.get("is_permanent_activated", False),
            "machine_code": data.get("machine_code", ""),
            "last_update": int(time.time())
        }
        
        # 记录验证状态更新
        is_permanent = data.get("is_permanent_activated", False)
        machine_code = data.get("machine_code", "")
        
        print(f"更新客户端 {client_id} 验证状态: 需要验证={data['is_verification_needed']}, 已验证={data['is_verified']}, 永久激活={is_permanent}, 机器码={machine_code}")
        
        # 如果已经验证成功，添加到验证记录
        if data["is_verified"] and data["is_verification_needed"]:
            configs = load_verification_config()
            if client_id not in configs:
                configs[client_id] = {"verifications": []}
            
            # 添加验证记录
            verification_record = {
                "time": int(time.time()),
                "success": True,
                "ip": request.remote_addr
            }
            
            # 如果是永久验证，添加特殊标记
            if is_permanent:
                verification_record["type"] = "permanent_activation"
                verification_record["machine_code"] = machine_code
                print(f"客户端 {client_id} 完成永久激活，机器码: {machine_code}")
            
            configs[client_id]["verifications"].append(verification_record)
            save_verification_config(configs)
        
        return jsonify({"status": "success", "message": "验证状态已更新"})
    except Exception as e:
        print(f"更新验证状态错误: {str(e)}")
        return jsonify({"status": "error", "message": f"更新验证状态失败: {str(e)}"}), 500

# API: 验证密钥
@app.route('/api/verification/verify/<client_id>', methods=['POST'])
def verify_client_key(client_id):
    """验证客户端密钥，通过命令发送给客户端验证"""
    try:
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 获取输入的密钥
        data = request.json
        if "key" not in data:
            return jsonify({"status": "error", "message": "缺少密钥参数"}), 400
        
        # 获取密钥内容
        key = data.get("key", "").strip()
        
        # 检查客户端验证状态
        if client_id not in verification_status:
            return jsonify({"status": "error", "message": "客户端无需验证"}), 400
        
        status = verification_status.get(client_id, {})
        
        # 检查是否需要验证
        if not status.get("is_verification_needed", False):
            return jsonify({"status": "error", "message": "客户端当前不需要验证"}), 400
        
        # 检查是否为永久激活密钥（FV前缀）
        is_permanent_key = key.upper().startswith("FV")
        
        if not is_permanent_key:
            # 非永久激活密钥，进行常规检查
            # 检查尝试次数
            if status.get("attempts_left", 0) <= 0:
                return jsonify({"status": "error", "message": "验证尝试次数已用尽"}), 403
            
            # 检查时间是否有效
            current_time = int(time.time())
            end_time = status.get("end_time", 0)
            
            if end_time and current_time > end_time:
                return jsonify({"status": "error", "message": "验证已过期"}), 403
        else:
            # 永久激活密钥，跳过过期和次数检查
            print(f"检测到永久激活密钥，跳过过期和次数检查: {client_id}")
        
        # 创建验证命令发送给客户端
        command = {
            "id": generate_command_id(),
            "type": "verify",
            "key": key,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 添加命令到队列（验证命令插入到队列最前面，确保优先处理）
        if client_id not in client_commands:
            client_commands[client_id] = []
        
        # 验证命令插入到队列前面，确保优先发送
        client_commands[client_id].insert(0, command)
        print(f"🔑 验证命令已加入优先队列: {command['id']} for {client_id}")
        
        # 添加命令状态
        command_status[command["id"]] = {
            "client_id": client_id,
            "command": command,
            "status": "pending",
            "message": "等待客户端验证",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return jsonify({
            "status": "success", 
            "message": "验证命令已优先发送到客户端", 
            "command_id": command["id"]
        })
    except Exception as e:
        print(f"验证密钥错误: {str(e)}")
        return jsonify({"status": "error", "message": f"验证处理失败: {str(e)}"}), 500

# API: 获取客户端验证状态
@app.route('/api/verification/status/<client_id>', methods=['GET'])
def get_client_verification_status(client_id):
    """获取客户端验证状态"""
    try:
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 获取验证状态
        status = verification_status.get(client_id, {
            "is_verification_needed": False,
            "attempts_left": 0,
            "start_time": 0,
            "end_time": 0,
            "is_verified": True,
            "is_permanent_activated": False,
            "machine_code": ""
        })
        
        # 计算剩余时间
        current_time = int(time.time())
        end_time = status.get("end_time", 0)
        remaining_time = max(0, end_time - current_time) if end_time else 0
        
        return jsonify({
            "status": "success",
            "verification_status": {
                "is_verification_needed": status.get("is_verification_needed", False),
                "attempts_left": status.get("attempts_left", 0),
                "start_time": status.get("start_time", 0),
                "end_time": status.get("end_time", 0),
                "is_verified": status.get("is_verified", True),
                "remaining_time": remaining_time,
                "is_permanent_activated": status.get("is_permanent_activated", False),
                "machine_code": status.get("machine_code", "")
            }
        })
    except Exception as e:
        print(f"获取验证状态错误: {str(e)}")
        return jsonify({"status": "error", "message": f"获取验证状态失败: {str(e)}"}), 500

# API: 获取验证历史记录
@app.route('/api/verification/history/<client_id>', methods=['GET'])
def get_verification_history(client_id):
    """获取客户端验证历史记录"""
    try:
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
        
        # 加载验证配置
        configs = load_verification_config()
        client_configs = configs.get(client_id, {"verifications": []})
        
        # 获取验证记录
        verifications = client_configs.get("verifications", [])
        
        # 按时间倒序排序
        verifications.sort(key=lambda x: x.get("time", 0), reverse=True)
        
        # 格式化验证记录
        formatted_verifications = []
        for v in verifications:
            time_str = datetime.datetime.fromtimestamp(v.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
            formatted_verifications.append({
                "time": time_str,
                "success": v.get("success", False),
                "ip": v.get("ip", "未知")
            })
        
        return jsonify({
            "status": "success",
            "verifications": formatted_verifications
        })
    except Exception as e:
        print(f"获取验证历史记录错误: {str(e)}")
        return jsonify({"status": "error", "message": f"获取验证历史记录失败: {str(e)}"}), 500

# 添加验证历史查看页面
@app.route('/verification/history/<client_id>')
def view_verification_history(client_id):
    """查看客户端验证历史页面"""
    # 获取所有客户端信息
    clients = get_all_clients()
    if client_id not in clients:
        return render_template("error.html", message="客户端不存在")
    
    # 加载验证配置
    configs = load_verification_config()
    client_configs = configs.get(client_id, {"verifications": []})
    
    # 获取验证记录
    verifications = client_configs.get("verifications", [])
    
    # 按时间倒序排序
    verifications.sort(key=lambda x: x.get("time", 0), reverse=True)
    
    # 格式化验证记录
    formatted_verifications = []
    for v in verifications:
        time_str = datetime.datetime.fromtimestamp(v.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
        formatted_verifications.append({
            "time": time_str,
            "success": v.get("success", False),
            "ip": v.get("ip", "未知")
        })
    
    # 计算统计数据
    total_count = len(verifications)
    successful_count = sum(1 for v in verifications if v.get("success", False))
    failed_count = total_count - successful_count
    
    # 计算最近7天的验证次数
    current_time = int(time.time())
    seven_days_ago = current_time - (7 * 86400)
    recent_verifications = [v for v in verifications if v.get("time", 0) > seven_days_ago]
    recent_count = len(recent_verifications)
    
    return render_template(
        "verification_history.html", 
        client_id=client_id,
        client_info=clients.get(client_id, {}),
        verifications=formatted_verifications,
        total_count=total_count,
        successful_count=successful_count,
        failed_count=failed_count,
        recent_count=recent_count
    )

# 添加验证命令状态检查API
@app.route('/api/verification/command/<command_id>', methods=['GET'])
def get_verification_command_status(command_id):
    """获取验证命令的执行状态"""
    try:
        if command_id not in command_status:
            # 尝试从命令结果中查找
            for client_id, results in command_results.items():
                if command_id in results:
                    # 创建一个临时的命令状态记录
                    result = results[command_id]
                    cmd_status = {
                        "client_id": client_id,
                        "command": {"id": command_id, "type": "verify"},
                        "status": "completed",
                        "success": result.get("success", False),
                        "attempts_left": result.get("attempts_left", 0),
                        "message": result.get("message", "验证已完成"),
                        "timestamp": result.get("timestamp", datetime.datetime.now().isoformat())
                    }
                    # 将临时状态保存到命令状态字典中
                    command_status[command_id] = cmd_status
                    print(f"从命令结果中恢复命令状态: command_id={command_id}")
                    break
            
            # 如果仍然找不到命令
        if command_id not in command_status:
            return jsonify({"status": "error", "message": "命令不存在"}), 404
            
        cmd_status = command_status[command_id]
        
        # 添加调试日志，查看完整的命令状态
        print(f"验证命令状态查询: command_id={command_id}, 状态详情: {json.dumps(cmd_status, default=str)}")
        
        # 获取命令执行状态
        status = cmd_status.get("status", "pending")
        message = cmd_status.get("message", "等待执行")
        
        # 如果命令已执行完成
        if status == "completed":
            # 从命令状态中直接获取验证结果
            success = cmd_status.get("success", False)
            
            # 尝试从command_status中获取attempts_left
            # 这个值是客户端在命令结果中提供的
            attempts_left = cmd_status.get("attempts_left", 0)
            message = cmd_status.get("message", "")
            
            # 构建统一的响应格式，无论成功或失败都包含attempts_left字段
            result = {
                    "status": "success",
                    "command_status": "completed",
                "success": success,  # 添加明确的success字段
                "verification_status": "success" if success else "failed",
                "attempts_left": attempts_left,  # 无论成功失败都返回尝试次数
                    "message": message
            }
            
            # 添加调试日志
            print(f"验证命令API响应: {json.dumps(result, default=str)}")
            
            return jsonify(result)
        else:
            # 命令仍在等待执行
            # 创建友好的消息，说明当前状态
            pending_message = cmd_status.get("message", "等待执行")
            if not "等待" in pending_message:
                pending_message = f"等待客户端执行验证，状态: {pending_message}"
            
            return jsonify({
                "status": "success",
                "command_status": status,
                "message": pending_message,
                "command_id": command_id
            })
    except Exception as e:
        print(f"获取验证命令状态错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"获取命令状态失败: {str(e)}"}), 500

# 发送命令到客户端API
# 调试API：查看实时查看状态
@app.route('/api/debug/live_views', methods=['GET'])
def debug_live_views():
    return jsonify({
        "client_live_views": client_live_views,
        "pending_keylog_commands": {
            client_id: sum(1 for cmd_id, cmd_info in command_status.items() 
                          if cmd_info.get("client_id") == client_id and 
                             cmd_info.get("command", {}).get("type") == "get_realtime_keylog" and 
                             cmd_info.get("status") == "pending")
            for client_id in client_live_views.keys()
        }
    })

@app.route('/api/send_command/<client_id>', methods=['POST'])
def send_command_to_client(client_id):
    """发送命令到指定客户端"""
    try:
        data = request.json
        
        # 检查客户端是否存在
        clients = get_all_clients()
        if client_id not in clients:
            return jsonify({"status": "error", "message": "客户端不存在"}), 404
            
        # 获取命令类型
        cmd_type = data.get('type')
        if not cmd_type:
            return jsonify({"status": "error", "message": "未指定命令类型"}), 400
            
        # 生成命令ID
        command_id = generate_command_id()
        
        # 构建命令
        command = {
            "id": command_id,
            "type": cmd_type,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 根据命令类型添加特定参数
        if cmd_type == "browse_files":
            path = data.get('path')
            if not path:
                return jsonify({"status": "error", "message": "未指定浏览路径"}), 400
            command["path"] = path
        elif cmd_type == "read_file":
            file_path = data.get('file_path')
            if not file_path:
                return jsonify({"status": "error", "message": "未指定文件路径"}), 400
            command["file_path"] = file_path
        elif cmd_type == "download_file":
            file_path = data.get('file_path')
            if not file_path:
                return jsonify({"status": "error", "message": "未指定下载文件路径"}), 400
            command["file_path"] = file_path
        elif cmd_type == "get_realtime_keylog":
            command["max_records"] = data.get('max_records', 50)
        elif cmd_type == "start_realtime_recording":
            command["fps"] = data.get('fps', 10)
        elif cmd_type == "refresh_verification_status":
            # 添加对刷新验证状态命令的支持
            print(f"发送刷新验证状态命令到客户端: {client_id}")
            # 无需额外参数
        
        # 添加命令到队列
        if client_id not in client_commands:
            client_commands[client_id] = []
        client_commands[client_id].append(command)
        
        # 添加命令状态
        command_status[command_id] = {
            "client_id": client_id,
            "command": command,
            "status": "pending",
            "message": f"命令已发送: {cmd_type}",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return jsonify({
            "status": "success", 
            "message": f"命令已发送到客户端: {cmd_type}", 
            "command_id": command_id
        })
    except Exception as e:
        print(f"发送命令错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送命令错误: {str(e)}"}), 500
