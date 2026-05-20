/* ─────────────────────────────────────────
   VISION SCREEN  –  Metin / Ses / Görüntü
   APIs: /analyze/text  /analyze/audio  /analyze/plant-disease/upload
   ───────────────────────────────────────── */

import Api from '../api.js';
import router from '../router.js';

const VisionScreen = {

  _mediaRecorder: null,
  _audioChunks:   [],
  _recording:     false,
  _timerInterval: null,

  mount(container) {
    container.innerHTML = this._render();
    this._bindEvents(container);
  },

  unmount() {
    this._stopRecording();
    this._mediaRecorder = null;
    this._audioChunks   = [];
    this._recording     = false;
  },

  _render() {
    return `
    <!-- Background -->
    <div style="position:absolute;inset:0;background:linear-gradient(180deg,#0a2a0a 0%,#0d3d0d 40%,#1a5c1a 100%);z-index:0;"></div>
    <img src="http://localhost:8000/assets/demo_images/healthy.jpg"
         style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.35;z-index:1;"
         alt="field" onerror="this.style.display='none'" />

    <!-- Topbar -->
    <div style="position:relative;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:.5rem 1.4rem;">
      <div style="color:#fff;font-weight:700;font-size:1rem;display:flex;align-items:center;gap:.4rem;">🌿 Agri-Lens</div>
      <div style="width:36px;height:36px;background:rgba(255,255,255,.15);border-radius:10px;
                  display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.1rem;
                  backdrop-filter:blur(4px);">⚙️</div>
    </div>

    <!-- Scan Frame -->
    <div style="position:relative;z-index:10;display:flex;flex-direction:column;align-items:center;padding:0 1rem .5rem;">
      <div class="scan-corners-wrap" style="width:200px;height:120px;position:relative;margin-bottom:.8rem;">
        <span class="corner tl"></span><span class="corner tr"></span>
        <span class="corner bl"></span><span class="corner br"></span>
        <div class="scan-line-anim"></div>
      </div>
      <div id="vision-dialog" style="background:rgba(255,255,255,.12);backdrop-filter:blur(12px);
           border:1px solid rgba(255,255,255,.2);border-radius:18px;padding:.8rem 1rem;
           text-align:center;max-width:260px;width:100%;">
        <h3 style="color:#fff;font-size:.9rem;font-weight:700;margin-bottom:.2rem;">AI Tarım Asistanı</h3>
        <p style="color:rgba(255,255,255,.7);font-size:.72rem;line-height:1.5;margin:0;">
          Metin yaz, ses kaydet veya bitki fotoğrafı yükle
        </p>
      </div>
    </div>

    <!-- MODE TABS -->
    <div style="position:relative;z-index:10;display:flex;gap:.4rem;padding:0 1rem .5rem;">
      <button id="tab-text"  class="mode-tab active-tab" data-mode="text">✏️ Metin</button>
      <button id="tab-voice" class="mode-tab"            data-mode="voice">🎙️ Ses</button>
      <button id="tab-image" class="mode-tab"            data-mode="image">📷 Görüntü</button>
    </div>

    <!-- TEXT MODE -->
    <div id="mode-text" style="position:relative;z-index:10;padding:0 1rem .5rem;display:flex;flex-direction:column;gap:.5rem;">
      <textarea id="text-input"
        placeholder="Sorunuzu yazın… Örn: Yapraklar sararıyor, ne yapmalıyım?"
        style="width:100%;min-height:80px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);
               border-radius:12px;padding:.7rem;color:#fff;font-size:.8rem;line-height:1.5;
               backdrop-filter:blur(4px);resize:none;box-sizing:border-box;outline:none;font-family:inherit;"
      ></textarea>
      <button class="btn btn-green" id="btn-send-text" style="border-radius:14px;font-size:.8rem;">
        🔍 Analiz Et
      </button>
    </div>

    <!-- VOICE MODE -->
    <div id="mode-voice" style="position:relative;z-index:10;padding:0 1rem .5rem;display:none;flex-direction:column;align-items:center;gap:.6rem;">
      <div id="voice-status" style="color:rgba(255,255,255,.75);font-size:.75rem;text-align:center;">
        Mikrofona bas ve konuş
      </div>
      <div class="voice-wave" id="voice-wave-vis" style="opacity:.4;">
        <span></span><span></span><span></span><span></span><span></span><span></span>
      </div>
      <button id="btn-record"
        style="width:64px;height:64px;border-radius:50%;border:none;cursor:pointer;font-size:1.8rem;
               background:rgba(239,68,68,.85);backdrop-filter:blur(6px);transition:all .2s;">
        🎙️
      </button>
      <div id="voice-timer" style="color:rgba(255,255,255,.5);font-size:.7rem;display:none;">⏱ 0:00</div>
    </div>

    <!-- IMAGE MODE -->
    <div id="mode-image" style="position:relative;z-index:10;padding:0 1rem .5rem;display:none;flex-direction:column;gap:.5rem;">
      <input type="file" id="img-input" accept="image/*" style="display:none"/>
      <div id="img-preview" style="display:none;border-radius:12px;overflow:hidden;border:1px solid rgba(255,255,255,.2);">
        <img id="img-thumb" style="width:100%;max-height:90px;object-fit:cover;" alt="preview"/>
      </div>
      <div style="display:flex;gap:.5rem;">
        <button class="btn btn-outline" id="btn-upload"
                style="border-radius:14px;font-size:.78rem;flex:1;background:rgba(255,255,255,.12);
                       color:#fff;border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(4px);">
          📂 Fotoğraf Seç
        </button>
        <button class="btn btn-green" id="btn-analyze-img" style="border-radius:14px;font-size:.78rem;flex:1;" disabled>
          🔍 Analiz Et
        </button>
      </div>
      <div style="display:flex;gap:.4rem;">
        <button class="btn btn-outline" id="btn-identify"
                style="border-radius:14px;font-size:.72rem;flex:1;background:rgba(255,255,255,.08);
                       color:#ddd;border:1px solid rgba(255,255,255,.2);">
          🐛 Zararlı Tanı
        </button>
        <button class="btn btn-outline" id="btn-stress"
                style="border-radius:14px;font-size:.72rem;flex:1;background:rgba(255,255,255,.08);
                       color:#ddd;border:1px solid rgba(255,255,255,.2);">
          ⚡ Stres Kontrol
        </button>
      </div>
    </div>

    <style>
      .mode-tab {
        flex:1;padding:.4rem;border:1px solid rgba(255,255,255,.2);border-radius:10px;
        background:rgba(255,255,255,.08);color:rgba(255,255,255,.65);font-size:.72rem;
        cursor:pointer;transition:all .2s;
      }
      .mode-tab.active-tab {
        background:rgba(74,222,128,.2);border-color:#4ade80;color:#4ade80;font-weight:700;
      }
      #text-input::placeholder { color:rgba(255,255,255,.4); }
    </style>
    `;
  },

  _bindEvents(container) {
    // Tab switching
    container.querySelectorAll('.mode-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        container.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active-tab'));
        tab.classList.add('active-tab');
        const mode = tab.dataset.mode;
        container.querySelector('#mode-text').style.display  = mode === 'text'  ? 'flex' : 'none';
        container.querySelector('#mode-voice').style.display = mode === 'voice' ? 'flex' : 'none';
        container.querySelector('#mode-image').style.display = mode === 'image' ? 'flex' : 'none';
      });
    });

    // TEXT
    container.querySelector('#btn-send-text').addEventListener('click', () => {
      const question = container.querySelector('#text-input').value.trim();
      if (!question) { alert('Lütfen bir soru yazın.'); return; }
      this._runTextAnalysis(container, question);
    });

    // VOICE
    container.querySelector('#btn-record').addEventListener('click', () => {
      if (!this._recording) this._startRecording(container);
      else this._stopRecordingAndAnalyze(container);
    });

    // IMAGE
    const imgInput      = container.querySelector('#img-input');
    const btnAnalyzeImg = container.querySelector('#btn-analyze-img');

    container.querySelector('#btn-upload').addEventListener('click', () => imgInput.click());
    container.querySelector('#btn-identify').addEventListener('click', () => {
      imgInput.dataset.question = 'Identify any pests or diseases visible in this image.';
      imgInput.click();
    });
    container.querySelector('#btn-stress').addEventListener('click', () => {
      imgInput.dataset.question = 'Check for any water, nutrient or heat stress in these crops.';
      imgInput.click();
    });

    imgInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      container.querySelector('#img-thumb').src = URL.createObjectURL(file);
      container.querySelector('#img-preview').style.display = 'block';
      btnAnalyzeImg.disabled = false;
    });

    btnAnalyzeImg.addEventListener('click', () => {
      const file = imgInput.files[0];
      if (!file) return;
      const question = imgInput.dataset.question || 'What is wrong with these leaves and what should I do?';
      delete imgInput.dataset.question;
      this._runImageAnalysis(container, file, question);
    });
  },

  async _getSensors() {
    try { const d = await Api.getSensors(); return d.device_state ?? {}; } catch (_) { return {}; }
  },

  _appendSensors(fd, sensors) {
    fd.append('field_id',        sensors.field_id        ?? 'field-A');
    fd.append('soil_moisture',   sensors.soil_moisture   ?? 45);
    fd.append('temperature',     sensors.temperature     ?? 28);
    fd.append('humidity',        sensors.humidity        ?? 65);
    fd.append('ph_level',        sensors.ph_level        ?? 6.5);
    fd.append('nitrogen',        sensors.nitrogen        ?? 28);
    fd.append('phosphorus',      sensors.phosphorus      ?? 20);
    fd.append('potassium',       sensors.potassium       ?? 25);
    fd.append('light_intensity', sensors.light_intensity ?? 55000);
  },

  _showLoading(container, msg) {
    container.querySelector('#vision-dialog').innerHTML = `
      <div class="spinner"></div>
      <div style="color:rgba(255,255,255,.85);font-size:.78rem;margin-top:.8rem;">${msg}</div>`;
  },

  _showError(container, err) {
    container.querySelector('#vision-dialog').innerHTML = `
      <div style="color:#f87171;font-size:.82rem;font-weight:700;">⚠️ Hata</div>
      <div style="color:rgba(255,255,255,.7);font-size:.72rem;margin-top:.4rem;line-height:1.4;">${err.message}</div>
      <button onclick="location.reload()"
              style="margin-top:.6rem;background:#16a34a;color:#fff;border:none;border-radius:8px;
                     padding:.4rem .8rem;font-size:.72rem;cursor:pointer;">Tekrar Dene</button>`;
  },

  async _runTextAnalysis(container, question) {
    this._showLoading(container, '✏️ Metin sorunuz analiz ediliyor…');
    try {
      const sensors = await this._getSensors();
      const fd = new FormData();
      fd.append('question', question);
      this._appendSensors(fd, sensors);
      const result = await Api.analyzeText(fd);
      router.navigate('report', { result, mode: 'text', question });
    } catch (err) { this._showError(container, err); }
  },

  async _startRecording(container) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this._audioChunks   = [];
      this._mediaRecorder = new MediaRecorder(stream);
      this._mediaRecorder.ondataavailable = e => this._audioChunks.push(e.data);
      this._mediaRecorder.start();
      this._recording = true;

      const btn    = container.querySelector('#btn-record');
      const status = container.querySelector('#voice-status');
      const wave   = container.querySelector('#voice-wave-vis');
      const timer  = container.querySelector('#voice-timer');

      btn.style.background = 'rgba(239,68,68,1)';
      btn.style.boxShadow  = '0 0 0 8px rgba(239,68,68,.3)';
      btn.innerHTML = '⏹️';
      status.textContent = 'Kaydediliyor… Durdurmak için tekrar bas';
      wave.style.opacity  = '1';
      timer.style.display = 'block';

      let secs = 0;
      this._timerInterval = setInterval(() => {
        secs++;
        const m = Math.floor(secs / 60), s = secs % 60;
        timer.textContent = `⏱ ${m}:${s.toString().padStart(2,'0')}`;
      }, 1000);
    } catch (e) {
      container.querySelector('#voice-status').textContent = '❌ Mikrofon erişimi reddedildi';
    }
  },

  _stopRecording() {
    if (this._timerInterval) { clearInterval(this._timerInterval); this._timerInterval = null; }
    if (this._mediaRecorder && this._recording) {
      this._mediaRecorder.stop();
      this._mediaRecorder.stream?.getTracks().forEach(t => t.stop());
    }
    this._recording = false;
  },

  _stopRecordingAndAnalyze(container) {
    this._mediaRecorder.onstop = async () => {
      const blob = new Blob(this._audioChunks, { type: 'audio/webm' });
      await this._runAudioAnalysis(container, blob);
    };
    this._stopRecording();
    const btn = container.querySelector('#btn-record');
    btn.style.background = 'rgba(239,68,68,.85)';
    btn.style.boxShadow  = 'none';
    btn.innerHTML = '🎙️';
    container.querySelector('#voice-wave-vis').style.opacity = '.4';
  },

  async _runAudioAnalysis(container, audioBlob) {
    this._showLoading(container, '🎙️ Ses mesajınız analiz ediliyor…');
    try {
      const sensors = await this._getSensors();
      const fd = new FormData();
      fd.append('audio', audioBlob, 'voice.webm');
      this._appendSensors(fd, sensors);
      const result = await Api.analyzeAudio(fd);
      router.navigate('report', { result, mode: 'audio' });
    } catch (err) { this._showError(container, err); }
  },

  async _runImageAnalysis(container, file, question) {
    this._showLoading(container, '📷 Görüntü analiz ediliyor…');
    try {
      const sensors = await this._getSensors();
      const fd = new FormData();
      fd.append('image',    file);
      fd.append('question', question);
      this._appendSensors(fd, sensors);
      const result = await Api.analyzeImage(fd);
      router.navigate('report', { result, imageUrl: URL.createObjectURL(file) });
    } catch (err) { this._showError(container, err); }
  },
};

export default VisionScreen;
