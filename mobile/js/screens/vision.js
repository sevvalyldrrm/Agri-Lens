/* ─────────────────────────────────────────
   VISION SCREEN  –  Camera / Image Analysis
   API: POST /analyze/plant-disease/upload
   ───────────────────────────────────────── */

import Api from '../api.js';
import router from '../router.js';

const VisionScreen = {

  _analysisResult: null,

  mount(container) {
    container.innerHTML = this._render();
    this._bindEvents(container);
  },

  unmount() {
    this._analysisResult = null;
  },

  _render() {
    return `
    <!-- Dark camera overlay -->
    <div style="position:absolute;inset:0;background:linear-gradient(180deg,#0a2a0a 0%,#0d3d0d 40%,#1a5c1a 100%);z-index:0;"></div>
    <img src="http://localhost:8000/assets/demo_images/healthy.jpg"
         style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.5;z-index:1;"
         alt="field" onerror="this.style.display='none'" />

    <!-- Topbar -->
    <div style="position:relative;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:.5rem 1.4rem;">
      <div style="color:#fff;font-weight:700;font-size:1rem;display:flex;align-items:center;gap:.4rem;">🌿 Agri-Lens</div>
      <div style="width:36px;height:36px;background:rgba(255,255,255,.15);border-radius:10px;
                  display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.1rem;
                  backdrop-filter:blur(4px);">⚙️</div>
    </div>

    <!-- Scan Frame -->
    <div style="position:relative;z-index:10;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:1rem;" id="scan-area">
      <div class="scan-corners-wrap" style="width:220px;height:160px;position:relative;margin-bottom:1.5rem;">
        <span class="corner tl"></span>
        <span class="corner tr"></span>
        <span class="corner bl"></span>
        <span class="corner br"></span>
        <div class="scan-line-anim"></div>
      </div>

      <!-- Status dialog -->
      <div id="vision-dialog" style="background:rgba(255,255,255,.12);backdrop-filter:blur(12px);
           border:1px solid rgba(255,255,255,.2);border-radius:18px;padding:1rem 1.2rem;
           text-align:center;max-width:260px;">
        <h3 style="color:#fff;font-size:1rem;font-weight:700;margin-bottom:.3rem;">Analyzing field…</h3>
        <p style="color:rgba(255,255,255,.75);font-size:.75rem;line-height:1.5;margin-bottom:.8rem;">
          Upload a leaf or field image to get an instant AI diagnosis.
        </p>
        <div class="voice-wave">
          <span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <!-- Hidden file input -->
    <input type="file" id="img-input" accept="image/*" style="display:none"/>

    <!-- Buttons -->
    <div style="position:relative;z-index:10;padding:1rem 1.2rem 1.2rem;display:flex;flex-direction:column;gap:.6rem;">
      <div style="display:flex;gap:.6rem;">
        <button class="btn btn-green" id="btn-identify" style="border-radius:20px;font-size:.78rem;">
          🐛 Identify Pest
        </button>
        <button class="btn btn-outline" id="btn-stress"
                style="border-radius:20px;font-size:.78rem;background:rgba(255,255,255,.12);
                       color:#fff;border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(4px);">
          ⚡ Stress Check
        </button>
      </div>
      <button class="btn" id="btn-upload"
              style="border-radius:14px;font-size:.78rem;background:rgba(255,255,255,.12);
                     color:#fff;border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(4px);">
        📂 Upload Image for Analysis
      </button>
    </div>
    `;
  },

  _bindEvents(container) {
    const input   = container.querySelector('#img-input');
    const btnId   = container.querySelector('#btn-identify');
    const btnStr  = container.querySelector('#btn-stress');
    const btnUp   = container.querySelector('#btn-upload');

    /* Upload Image → analyze */
    btnUp.addEventListener('click', () => input.click());
    btnId.addEventListener('click', () => { input.dataset.question = 'Identify any pests or diseases visible in this image.'; input.click(); });
    btnStr.addEventListener('click', () => { input.dataset.question = 'Check for any water, nutrient or heat stress in these crops.'; input.click(); });

    input.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      await this._runAnalysis(container, file, input.dataset.question || 'What is wrong with these leaves and what should I do?');
      input.value = '';
    });
  },

  async _runAnalysis(container, file, question) {
    const dialog = container.querySelector('#vision-dialog');
    dialog.innerHTML = `
      <div class="spinner"></div>
      <div style="color:rgba(255,255,255,.85);font-size:.78rem;margin-top:.8rem;">
        🤖 Analyzing with Gemini AI…
      </div>`;

    try {
      /* Build FormData using current device state as default sensors */
      let sensors = {};
      try {
        const d = await Api.getSensors();
        sensors = d.device_state ?? {};
      } catch (_) { /* use defaults */ }

      const fd = new FormData();
      fd.append('image',         file);
      fd.append('field_id',      sensors.field_id      ?? 'field-A');
      fd.append('question',      question);
      fd.append('soil_moisture', sensors.soil_moisture ?? 45);
      fd.append('temperature',   sensors.temperature   ?? 28);
      fd.append('humidity',      sensors.humidity      ?? 65);
      fd.append('ph_level',      sensors.ph_level      ?? 6.5);
      fd.append('nitrogen',      sensors.nitrogen      ?? 28);
      fd.append('phosphorus',    sensors.phosphorus    ?? 20);
      fd.append('potassium',     sensors.potassium     ?? 25);
      fd.append('light_intensity', sensors.light_intensity ?? 55000);

      const result = await Api.analyzeImage(fd);

      /* Pass result to Report screen */
      router.navigate('report', { result, imageUrl: URL.createObjectURL(file) });

    } catch (err) {
      dialog.innerHTML = `
        <div style="color:#f87171;font-size:.82rem;font-weight:700;">⚠️ Analysis Failed</div>
        <div style="color:rgba(255,255,255,.7);font-size:.72rem;margin-top:.4rem;line-height:1.4;">${err.message}</div>
        <button onclick="location.reload()"
                style="margin-top:.6rem;background:#16a34a;color:#fff;border:none;border-radius:8px;
                       padding:.4rem .8rem;font-size:.72rem;cursor:pointer;">Try Again</button>`;
    }
  },
};

export default VisionScreen;
