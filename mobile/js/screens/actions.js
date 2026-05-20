/* ─────────────────────────────────────────
   ACTIONS SCREEN  –  Action Center
   Data: PlantDiseaseResult.recommendations (from router state)
         OR fallback → GET /demo/plant-disease/late-blight
   ───────────────────────────────────────── */

import Api from '../api.js';
import router from '../router.js';

const ActionsScreen = {

  mount(container, state = {}) {
    if (state.result) {
      container.innerHTML = this._render(state.result);
    } else {
      container.innerHTML = this._loading();
      this._loadDemo(container);
    }
    this._bindEvents(container);
  },

  unmount() {},

  async _loadDemo(container) {
    try {
      const result = await Api.getDemoScenario('late-blight');
      container.innerHTML = this._render(result);
      this._bindEvents(container);
    } catch (err) {
      container.innerHTML = `<div class="error-state">⚠️ ${err.message}</div>`;
    }
  },

  /* ── Map recommendation text → icon + colour ── */
  _recMeta(text = '') {
    const t = text.toLowerCase();
    if (t.includes('irrigat') || t.includes('water'))
      return { icon: '💧', bg: '#dbeafe', urgent: false };
    if (t.includes('fertiliz') || t.includes('nitrogen') || t.includes('nutrient'))
      return { icon: '🧪', bg: '#fef3c7', urgent: true };
    if (t.includes('fungal') || t.includes('fungicide') || t.includes('disease'))
      return { icon: '🍄', bg: '#fce7f3', urgent: true };
    if (t.includes('agronomi') || t.includes('consult') || t.includes('expert'))
      return { icon: '👨‍🌾', bg: '#dcfce7', urgent: false };
    return { icon: '📋', bg: '#f3f4f6', urgent: false };
  },

  _recCards(recs = []) {
    if (!recs.length) {
      return `<div class="card-sm" style="color:#6a9a6a;font-size:.78rem;text-align:center;">
        ✅ No urgent actions required.
      </div>`;
    }

    return recs.map((text, i) => {
      const { icon, bg, urgent } = this._recMeta(text);
      return `
      <div class="card-sm" style="margin-bottom:.6rem;" data-rec-idx="${i}">
        <div style="display:flex;align-items:flex-start;gap:.7rem;">
          <div class="icon-box" style="background:${bg};">${icon}</div>
          <div style="flex:1;">
            <div style="font-size:.78rem;font-weight:700;color:#1a3a1a;
                        display:flex;justify-content:space-between;align-items:center;">
              Recommendation ${i + 1}
              ${urgent
                ? '<span class="badge badge-yellow">URGENT</span>'
                : '<button class="toggle" id="toggle-' + i + '"></button>'}
            </div>
            <div style="font-size:.67rem;color:#6a9a6a;margin-top:.25rem;line-height:1.5;">${text}</div>
          </div>
        </div>
        ${urgent ? `<button class="btn btn-dark" style="margin-top:.6rem;font-size:.75rem;" data-apply="${i}">
          📋 Apply Suggested Action</button>` : ''}
      </div>`;
    }).join('');
  },

  _render(r) {
    const recs  = r.recommendations ?? [];
    const field = r.sensor_data?.field_id ?? 'Field';
    const temp  = r.sensor_data?.temperature ?? 24;
    const hum   = r.sensor_data?.humidity    ?? 62;
    const urgentCount = recs.filter(t => {
      const l = t.toLowerCase();
      return l.includes('fertiliz') || l.includes('fungal') || l.includes('disease');
    }).length;

    return `
    <!-- Topbar -->
    <div class="topbar">
      <h2>Action Center</h2>
      <div class="icon-group">
        <div class="icon-btn">🔔</div>
        <div class="icon-btn">👤</div>
      </div>
    </div>

    <!-- System Status -->
    <div style="margin:.4rem 1.2rem;background:#1a3a1a;border-radius:16px;padding:.9rem 1rem;
                display:flex;justify-content:space-between;align-items:center;">
      <div style="display:flex;align-items:center;gap:.5rem;">
        <span style="font-size:1.1rem;">⚙️</span>
        <div>
          <div style="font-size:.7rem;color:rgba(255,255,255,.65);text-transform:uppercase;letter-spacing:.5px;">System Status</div>
          <div style="font-size:.88rem;font-weight:700;color:#fff;">Executing Autonomous Tasks</div>
        </div>
      </div>
      <div class="live-badge"><div class="live-dot"></div>Live Pulse</div>
    </div>

    <!-- AI Recommendations Header -->
    <div style="padding:.6rem 1.4rem .3rem;display:flex;justify-content:space-between;align-items:center;">
      <h3 style="font-size:.82rem;font-weight:700;color:#1a3a1a;display:flex;align-items:center;gap:.35rem;">
        🤖 AI Smart Recommendations
        <span class="badge badge-red">${urgentCount || recs.length} Priority</span>
      </h3>
    </div>

    <!-- Rec Cards -->
    <div style="padding:0 1.2rem;" id="rec-list">
      ${this._recCards(recs)}
    </div>

    <!-- Extra Action Buttons -->
    <div style="padding:0 1.2rem;display:flex;flex-direction:column;gap:.5rem;margin-top:.4rem;">
      <button class="btn btn-outline" id="btn-notify">👨‍🌾 Notify Agronomist</button>
      <button class="btn btn-outline" id="btn-report" style="color:#16a34a;">📤 Send Diagnostic Report</button>
    </div>

    <!-- Environmental Context -->
    <div class="section-header" style="margin-top:.4rem;"><h3>Environmental Context</h3></div>
    <div style="margin:.3rem 1.2rem 1rem;border-radius:18px;overflow:hidden;position:relative;height:88px;
                background:linear-gradient(135deg,#0a2a0a,#1a5c1a);">
      <img src="http://localhost:8000/assets/demo_images/healthy.jpg" alt="env"
           style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.45;"
           onerror="this.style.display='none'"/>
      <div style="position:absolute;inset:0;display:flex;align-items:center;gap:1.5rem;padding:0 1rem;">
        <div style="display:flex;align-items:center;gap:.35rem;color:#fff;">
          🌡️ <span style="font-size:.88rem;font-weight:700;">${temp}°C</span>
        </div>
        <div style="display:flex;align-items:center;gap:.35rem;color:#fff;">
          💧 <span style="font-size:.88rem;font-weight:700;">${hum}%</span>
          <small style="font-size:.65rem;color:rgba(255,255,255,.7);">Humidity</small>
        </div>
        <div style="display:flex;align-items:center;gap:.35rem;color:#fff;">
          📍 <small style="font-size:.68rem;color:rgba(255,255,255,.7);">${field}</small>
        </div>
      </div>
    </div>
    `;
  },

  _loading() {
    return `
    <div class="topbar"><h2>Action Center</h2></div>
    <div class="card" style="text-align:center;padding:2rem;">
      <div class="spinner"></div>
      <div style="margin-top:.8rem;font-size:.8rem;color:#6a9a6a;">Loading recommendations…</div>
    </div>`;
  },

  _bindEvents(container) {
    /* Toggle switches */
    container.querySelectorAll('.toggle').forEach(sw => {
      sw.addEventListener('click', () => sw.classList.toggle('off'));
    });

    /* Apply buttons */
    container.querySelectorAll('[data-apply]').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.textContent = '✅ Applied!';
        btn.style.background = '#16a34a';
        btn.disabled = true;
      });
    });

    /* Notify */
    container.querySelector('#btn-notify')?.addEventListener('click', () => {
      alert('📲 Agronomist has been notified via SMS & email.');
    });

    /* Report */
    container.querySelector('#btn-report')?.addEventListener('click', () => {
      alert('📤 Diagnostic report sent successfully.');
    });
  },
};

export default ActionsScreen;
