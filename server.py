import os
import uuid
import subprocess
import io
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configurações de pastas
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# ---------------------------------------------------------
# IMPORTAÇÕES SOB DEMANDA (Para o servidor iniciar INSTANTÂNEO)
# ---------------------------------------------------------

@app.route('/api/remove-bg', methods=['POST'])
def remove_bg():
    from rembg import remove # Importa só quando usa
    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pdf-convert', methods=['POST'])
def pdf_convert():
    from pdf2docx import Converter # Importa só quando usa
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        file = request.files['file']
        target_format = request.form.get('format', 'docx')
        
        temp_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}.pdf")
        file.save(input_path)
        
        result_filename = f"converted_{temp_id}.{target_format}"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        
        if target_format == 'docx':
            cv = Converter(input_path)
            cv.convert(result_path)
            cv.close()
            return jsonify({"download_url": f"/api/download/{result_filename}"})
        return jsonify({"error": "Formato não suportado"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/compress-video', methods=['POST'])
def compress_video():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        file = request.files['file']
        crf = request.form.get('crf', '23')
        
        temp_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
        file.save(input_path)
        
        result_filename = f"compressed_{temp_id}_{file.filename}"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        
        # FFmpeg é comando de sistema, não precisa de import pesado
        cmd = ['ffmpeg', '-i', input_path, '-vcodec', 'libx264', '-crf', str(crf), '-preset', 'ultrafast', result_path]
        subprocess.run(cmd, check=True)
        return jsonify({"download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/extract-audio', methods=['POST'])
def extract_audio():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        file = request.files['file']
        
        temp_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
        file.save(input_path)
        
        result_filename = f"audio_{temp_id}.mp3"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        
        cmd = ['ffmpeg', '-i', input_path, '-vn', '-c:a', 'libmp3lame', '-q:a', '4', result_path]
        subprocess.run(cmd, check=True)
        return jsonify({"download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    import whisper # Importa só quando usa
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        file = request.files['file']
        
        temp_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_FOLDER, f"{temp_id}_{file.filename}")
        file.save(input_path)
        
        model = whisper.load_model("tiny") # Modelo leve
        result = model.transcribe(input_path)
        text = result['text']
        
        result_filename = f"transcription_{temp_id}.txt"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        return jsonify({"text": text, "download_url": f"/api/download/{result_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-custom', methods=['POST'])
def download_custom():
    import yt_dlp # Importa só quando usa
    try:
        data = request.json
        url = data.get('url')
        if not url: return jsonify({"error": "URL não fornecida"}), 400
            
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(RESULT_FOLDER, f'dl_{uuid.uuid4()}_%(title)s.%(ext)s'),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            basename = os.path.basename(filename)
        return jsonify({"download_url": f"/api/download/{basename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Arquivo não encontrado", 404

@app.route('/')
@app.route('/healthz')
def health_check():
    return "Lima Ferramentas API Online!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
