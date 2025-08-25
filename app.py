from flask import Flask, request, jsonify, render_template, send_from_directory
import google.generativeai as genai
import os
import re
import json
from ebooklib import epub
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TRANSLATION_FOLDER'] = 'translations'
app.config['DICTIONARY_FILE'] = 'dictionaries/default.json'
app.config['SESSIONS_FOLDER'] = 'sessions'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TRANSLATION_FOLDER'], exist_ok=True)
os.makedirs('dictionaries', exist_ok=True)
os.makedirs(app.config['SESSIONS_FOLDER'], exist_ok=True)

# Tạo từ điển mặc định
if not os.path.exists(app.config['DICTIONARY_FILE']):
    with open(app.config['DICTIONARY_FILE'], 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False)

# Tách chương
def split_chapters(text):
    chapters = re.split(r'(Chương\s+\d+.*?)', text, flags=re.IGNORECASE)
    chapters = [ch.strip() for ch in chapters if ch.strip()]
    result = []
    for i in range(1, len(chapters), 2):
        if i + 1 < len(chapters):
            result.append({'title': chapters[i], 'content': chapters[i+1]})
        else:
            result.append({'title': chapters[i], 'content': ''})
    return result

# Dịch văn bản
def translate_text(text, api_key, prompt):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt + "\n\n" + text)
        return response.text
    except Exception as e:
        return f"[Lỗi dịch: {str(e)}]"

# Lưu session
def save_session(user_id, data):
    with open(f"sessions/{user_id}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

# Load session
def load_session(user_id):
    try:
        with open(f"sessions/{user_id}.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'translated': {}}

# Load từ điển
def load_dictionary():
    try:
        with open(app.config['DICTIONARY_FILE'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

# Áp dụng từ điển
def apply_dictionary(text, dictionary):
    for src, dst in dictionary.items():
        text = text.replace(src, dst)
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global chapters
    chapters = []
    content = ""

    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = request.form['text']

    chapters = split_chapters(content)
    return jsonify(chapters)

@app.route('/translate-range', methods=['POST'])
def translate_range():
    data = request.json
    start_idx = data['start'] - 1
    end_idx = data['end']
    api_keys = [k.strip() for k in data['api_keys'].split(',') if k.strip()]
    prompt = data.get('prompt', 'Dịch tự nhiên sang tiếng Việt')
    user_id = request.cookies.get('user_id', 'default')

    session = load_session(user_id)
    dictionary = load_dictionary()

    chapters_to_translate = []
    indices = []

    for i in range(start_idx, min(end_idx, len(chapters))):
        if str(i) not in session['translated']:
            chapters_to_translate.append(chapters[i])
            indices.append(i)

    # Dịch song song
    for i, chapter in enumerate(chapters_to_translate):
        key = api_keys[i % len(api_keys)]
        text = apply_dictionary(chapter['content'], dictionary)
        translated = translate_text(text, key, prompt)
        session['translated'][str(indices[i])] = translated

    save_session(user_id, session)
    return jsonify({'status': 'success', 'translated_count': len(chapters_to_translate)})

@app.route('/export-epub', methods=['POST'])
def export_epub():
    data = request.json
    book = epub.EpubBook()
    book.set_title(data['title'])
    book.add_author(data['author'])

    style = 'BODY { font-family: Arial; }'
    book.add_item(epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style))

    epub_chapters = []
    for i, chap in enumerate(data['chapters']):
        c = epub.EpubHtml(title=chap['title'], file_name=f'chap_{i+1}.xhtml')
        c.content = f"<h1>{chap['title']}</h1><div>{chap['content'].replace(chr(10), '<br/>')}</div>"
        c.add_item(book.get_item('style'))
        book.add_item(c)
        epub_chapters.append(c)

    book.toc = tuple(epub_chapters)
    book.spine = ['nav'] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    filename = f"{uuid.uuid4().hex}.epub"
    filepath = os.path.join(app.config['TRANSLATION_FOLDER'], filename)
    epub.write_epub(filepath, book, {})

    return jsonify({'url': f'/download/{filename}'})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['TRANSLATION_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
