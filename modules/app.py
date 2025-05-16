from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import cv2
import numpy as np
import base64
import time  # 添加这行
from modules.processors.frame.core import get_frame_processors_modules
import modules.globals
from modules.face_analyser import get_one_face

app = Flask(__name__)
# 启用 CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": "*",
        "expose_headers": "*",
        "methods": ["GET", "POST", "OPTIONS"]
    }
})
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化全局设置
# modules.globals.frame_processors = ['face_swapper']
# modules.globals.many_faces = False
# modules.globals.nsfw_filter = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/page/image')
def page_image():
    return render_template('process_image.html')

@app.route('/process_image', methods=['POST'])
def process_image():
    try:
        # 获取上传的图片数据
        image_data = request.json.get('image')
        if not image_data or not image_data.startswith('data:image'):
            return jsonify({'error': '无效的图片数据'}), 400
        
        # 解码base64图像
        encoded_data = image_data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        source_img = cv2.imread(modules.globals.source_path)
        source_face = get_one_face(source_img)

        # 处理图像
        frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
        for processor in frame_processors:
            frame = processor.process_frame(source_face, frame)
        
        # 编码处理后的图像
        _, buffer = cv2.imencode('.jpg', frame)
        processed_image = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'processed_image': f'data:image/jpeg;base64,{processed_image}'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# 移除全局变量
# source_img = cv2.imread(modules.globals.source_path)
# source_face = get_one_face(source_img)

@socketio.on('video_feed')
def video_feed(data):
    start_time = time.time()  # 开始计时
    
    source_img = socket_faces[request.sid]
    # 获取源图片和人脸（如果还没有加载）
    # if not hasattr(modules.globals, 'source_face') or modules.globals.source_face is None:
    #     if not modules.globals.source_path:
    #         socketio.emit('error', '请先设置源图片路径')
    #         return
    #     source_img = cv2.imread(modules.globals.source_path)
    #     modules.globals.source_face = get_one_face(source_img)
    
    # 解码前端发送的base64图像
    decode_start = time.time()
    face_enhancer = False
    # 如果 data 是字符串，直接使用；如果是字典，提取 frame 字段
    if isinstance(data, dict):
        frame_data = data['frame']
        face_enhancer = data.get('enhance', False)
    else:
        frame_data = data
    encoded_data = frame_data.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    decode_time = time.time() - decode_start
    
    # 处理图像
    process_start = time.time()
    # 根据是否启用人脸增强来设置处理器
    processors = ['face_swapper']
    if face_enhancer:
        processors.append('face_enhancer')
    frame_processors = get_frame_processors_modules(processors)
    print(f'processors {processors}')
    for processor in frame_processors:
        print(f'{processor} running')
        frame = processor.process_frame(source_img, frame)
    process_time = time.time() - process_start
    
    # 编码处理后的图像
    encode_start = time.time()
    _, buffer = cv2.imencode('.jpg', frame)
    processed_image = base64.b64encode(buffer).decode('utf-8')
    encode_time = time.time() - encode_start
    
    # 计算总时间
    total_time = time.time() - start_time
    
    # 打印时间日志
    print(f'[性能统计] 总耗时: {total_time:.3f}s (解码: {decode_time:.3f}s, 处理: {process_time:.3f}s, 编码: {encode_time:.3f}s)')
    
    # 发送处理后的图像回客户端
    socketio.emit('processed_frame', f'data:image/jpeg;base64,{processed_image}')


# 添加 socket 连接的字典，用于存储每个连接的 source_face
socket_faces = {}

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    socket_faces[request.sid] = None

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in socket_faces:
        del socket_faces[request.sid]

@socketio.on('source_image')
def handle_source_image(data):
    try:
        # 解码base64图像
        encoded_data = data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        source_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 获取人脸
        source_face = get_one_face(source_img)
        if source_face is None:
            raise Exception('未检测到人脸')
        
        # 存储该连接的 source_face
        socket_faces[request.sid] = source_face
        socketio.emit('source_image_status', {'success': True})
        
    except Exception as e:
        socketio.emit('source_image_status', {
            'success': False,
            'error': str(e)
        })

@socketio.on('video_feed')
def video_feed(data):
    # 检查是否有 source_face
    if request.sid not in socket_faces or socket_faces[request.sid] is None:
        socketio.emit('error', '请先上传源图片')
        return
    
    start_time = time.time()
    source_face = socket_faces[request.sid]
    
    try:
        # 解码前端发送的base64图像
        decode_start = time.time()
        # 检查数据类型
        # 如果是字符串，直接使用；如果是字典，提取 frame 字段
        if isinstance(data, dict):
            frame_data = data['frame'] if isinstance(data, dict) else data
            enhance = data.get('enhance', False) if isinstance(data, dict) else False
        else:
            frame_data = data
            enhance = False
        
        encoded_data = frame_data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        decode_time = time.time() - decode_start
        
        # 处理图像
        process_start = time.time()
        # 根据是否启用人脸增强来设置处理器
        processors = ['face_swapper']
        if enhance:
            processors.append('face_enhancer')
            
        frame_processors = get_frame_processors_modules(processors)
        for processor in frame_processors:
            frame = processor.process_frame(source_face, frame)
        process_time = time.time() - process_start
    except Exception as e:
        socketio.emit('error', str(e))
        return

    # 编码处理后的图像
    encode_start = time.time()
    _, buffer = cv2.imencode('.jpg', frame)
    processed_image = base64.b64encode(buffer).decode('utf-8')
    encode_time = time.time() - encode_start
    
    # 计算总时间
    total_time = time.time() - start_time
    
    # 打印时间日志
    print(f'[性能统计] 总耗时: {total_time:.3f}s (解码: {decode_time:.3f}s, 处理: {process_time:.3f}s, 编码: {encode_time:.3f}s)')
    
    # 发送处理后的图像回客户端
    socketio.emit('processed_frame', f'data:image/jpeg;base64,{processed_image}')
