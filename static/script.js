// Tạo user_id nếu chưa có
function getCookie(name) {
    let value = "; " + document.cookie;
    let parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
}

let user_id = getCookie('user_id');
if (!user_id) {
    user_id = 'user_' + Date.now();
    document.cookie = `user_id=${user_id}; path=/; max-age=31536000`; // Lưu 1 năm
}

let chapters = [];
let translated = {};

// Tải nội dung
async function loadContent() {
    const formData = new FormData();
    const file = document.getElementById('fileInput').files[0];
    const text = document.getElementById('textInput').value;

    if (file) formData.append('file', file);
    else formData.append('text', text);

    const res = await fetch('/upload', { method: 'POST', body: formData });
    chapters = await res.json();
    renderChapters();
    loadProgress(); // Tải tiến trình sau khi có chương
}

// Render danh sách chương
function renderChapters() {
    const container = document.getElementById('chapters');
    container.innerHTML = '<h4>📚 Các chương</h4>';
    
    if (chapters.length === 0) {
        container.innerHTML += '<p class="text-muted">Chưa có chương nào.</p>';
        return;
    }

    chapters.forEach((chap, i) => {
        const transText = translated[i]
            ? (translated[i].length > 100 ? translated[i].substring(0, 100) + '...' : translated[i])
            : '[Chưa dịch]';
        const color = translated[i] ? '#0056b3' : '#6c757d';
        const elId = `trans-${i}`;

        const div = document.createElement('div');
        div.innerHTML = `
          <div class="card mb-2">
            <div class="card-body">
              <h6>${chap.title}</h6>
              <div><small><strong>Dịch:</strong> <span id="${elId}" style="color:${color}">${transText}</span></small></div>
            </div>
          </div>`;
        container.appendChild(div);
    });
    updateProgress();
}

// Tải tiến trình dịch từ server
async function loadProgress() {
    try {
        const res = await fetch('/status');
        const session = await res.json();
        translated = session.translated || {};
        renderChapters(); // Cập nhật lại giao diện
    } catch (e) {
        console.error("Không thể tải tiến trình:", e);
        document.getElementById('progress').innerHTML = '⚠️ Không thể tải tiến trình.';
    }
}

// Cập nhật thanh tiến trình
function updateProgress() {
    const total = chapters.length;
    const done = Object.keys(translated).length;
    document.getElementById('progress').innerHTML = 
        `<b>✅ Đã dịch: ${done}/${total} chương</b>`;
}

// Dịch khoảng chương đã chọn
async function translateRange() {
    const start = parseInt(document.getElementById('startChapter').value);
    const end = parseInt(document.getElementById('endChapter').value);
    const apiKeys = document.getElementById('apiKeys').value;
    const prompt = document.getElementById('prompt').value;

    if (start < 1 || end < start) {
        alert("Vui lòng chọn khoảng chương hợp lệ!");
        return;
    }

    const res = await fetch('/translate-range', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start, end, api_keys: apiKeys, prompt })
    });

    const data = await res.json();
    if (data.status === 'success') {
        alert(`✅ Đã dịch thêm ${data.translated_count} chương!`);
        loadProgress(); // Tải lại tiến trình ngay
    } else {
        alert("❌ Lỗi khi dịch.");
    }
}

// Xuất file EPUB
async function exportEpub() {
    if (Object.keys(translated).length === 0) {
        alert("Chưa có chương nào được dịch!");
        return;
    }

    const title = prompt("Nhập tên truyện:", "Truyện đã dịch") || "Truyện đã dịch";
    const data = {
        title,
        author: "Dịch bởi Gemini",
        chapters: chapters.map((chap, i) => ({
            title: chap.title,
            content: translated[i] || chap.content
        }))
    };

    try {
        const res = await fetch('/export-epub', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const json = await res.json();
        const a = document.createElement('a');
        a.href = json.url;
        a.download = `${title}.epub`;
        a.click();
    } catch (e) {
        alert("Lỗi khi xuất EPUB: " + e.message);
    }
}

// Tự động tải tiến trình khi trang mở
document.addEventListener("DOMContentLoaded", () => {
    loadProgress(); // Luôn tải tiến trình khi vào trang
});
