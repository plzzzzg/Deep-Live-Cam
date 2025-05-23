from flask import Flask, render_template
from flask_socketio import SocketIO
import cv2
import numpy as np
import base64
from modules.processors.frame.core import get_frame_processors_modules
import modules.globals

app = Flask(__name__)
socketio = SocketIO(app)

# 初始化全局设置
modules.globals.frame_processors = ['face_swapper']
modules.globals.many_faces = False
modules.globals.nsfw_filter = False

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('video_feed')
def video_feed(data):
    # 解码前端发送的base64图像
    encoded_data = data.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 处理图像
    frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
    for processor in frame_processors:
        frame = processor.process_frame(frame)
    
    # 编码处理后的图像
    _, buffer = cv2.imencode('.jpg', frame)
    processed_image = base64.b64encode(buffer).decode('utf-8')
    
    # 发送处理后的图像回客户端
    socketio.emit('processed_frame', f'data:image/jpeg;base64,{processed_image}')
