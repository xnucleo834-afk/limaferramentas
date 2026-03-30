import os
import uuid
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from rembg import remove
from pdf2docx import Converter
import whisper
import yt_dlp
from PIL import Image
import io
import qrcode

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Carregar modelo Whisper (base para ser rápido)
print("Carregando modelo Whisper...")
whisper_model = whisper.load_model("base")

@app.route('/api/remove-bg', methods=['POST'])
def remove_bg():
    if 'image' not in request.files:
        return jsonify({"error": "Nenhuma imagem enviada"}), 400
    file = request.files['image']
    input_data = file.read()
    output_data = remove(input_data)
    
    result_filename = f"no_bg_{uuid.uuid4()}.png"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    
    with open(result_path, 'wb') as f:
        f.write(output_data)
    
    return jsonify({"download_url": f"/api/download/{result_filename}"})

@app.route('/api/pdf-convert', methods=['POST'])
def pdf_convert():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    file = request.files['file']
    target_format = request.form.get('format', 'docx')
    
    temp_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}.pdf")
    file.save(input_path)
    
    result_filename = f"converted_{temp_id}.{target_format}"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    
    try:
        if target_format == 'docx':
            cv = Converter(input_path)
            cv.convert(result_path)
            cv.close()
        else:
            # Fallback simples para outros formatos ou erro
            return jsonify({"error": f"Conversão para {target_format} ainda em desenvolvimento"}), 400
            
        return jsonify({"download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/compress-video', methods=['POST'])
def compress_video():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    file = request.files['file']
    crf = request.form.get('crf', '18')
    
    temp_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
    file.save(input_path)
    
    result_filename = f"compressed_{temp_id}_{file.filename}"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    
    try:
        # ffmpeg -i input.mp4 -vcodec libx264 -crf 18 -preset slow output.mp4
        cmd = ['ffmpeg', '-i', input_path, '-vcodec', 'libx264', '-crf', str(crf), '-preset', 'fast', result_path]
        subprocess.run(cmd, check=True)
        return jsonify({"download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/extract-audio', methods=['POST'])
def extract_audio():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    file = request.files['file']
    
    temp_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
    file.save(input_path)
    
    result_filename = f"audio_{temp_id}.mp3"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    
    try:
        cmd = ['ffmpeg', '-i', input_path, '-vn', '-c:a', 'libmp3lame', '-q:a', '2', result_path]
        subprocess.run(cmd, check=True)
        return jsonify({"download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    file = request.files['file']
    
    temp_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
    file.save(input_path)
    
    try:
        result = whisper_model.transcribe(input_path)
        text = result['text']
        
        result_filename = f"transcription_{temp_id}.txt"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        return jsonify({
            "text": text,
            "download_url": f"/api/download/{result_filename}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-custom', methods=['POST'])
def download_custom():
    data = request.json
    url = data.get('url')
    platform = data.get('platform')
    
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400
        
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(RESULT_FOLDER, f'dl_{uuid.uuid4()}_%(title)s.%(ext)s'),
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            basename = os.path.basename(filename)
            
        return jsonify({"download_url": f"/api/download/{basename}", "filename": basename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Arquivo não encontrado", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
