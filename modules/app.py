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
    
    # 获取源图片和人脸（如果还没有加载）
    if not hasattr(modules.globals, 'source_face') or modules.globals.source_face is None:
        if not modules.globals.source_path:
            socketio.emit('error', '请先设置源图片路径')
            return
        source_img = cv2.imread(modules.globals.source_path)
        modules.globals.source_face = get_one_face(source_img)
    
    # 解码前端发送的base64图像
    decode_start = time.time()
    encoded_data = data.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    decode_time = time.time() - decode_start
    
    # 处理图像
    process_start = time.time()
    frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
    for processor in frame_processors:
        frame = processor.process_frame(modules.globals.source_face, frame)
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
