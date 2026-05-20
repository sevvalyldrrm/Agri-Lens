/* ─────────────────────────────────────────
   REPORT SCREEN  –  Diagnosis Details
   Data: PlantDiseaseResult passed via router state
         OR fallback → GET /demo/plant-disease/nutrient-deficiency
   ───────────────────────────────────────── */

import Api from '../api.js';
import router from '../router.js';

const ReportScreen = {

  mount(container, state = {}) {
    if (state.result) {
      container.innerHTML = this._render(state.result, state.imageUrl);
      this._bindEvents(container, state.result);
    } else {
      container.innerHTML = this._loading();
      this._loadDemo(container);
    }
  },

  unmount() {},

  async _loadDemo(container) {
    try {
      const result = await Api.getDemoScenario('nutrient-deficiency');
      container.innerHTML = this._render(result, null);
      this._bindEvents(container, result);
    } catch (err) {
      container.innerHTML = `<div class="error-state">⚠️ ${err.message}</div>`;
    }
  },

  /* ── Map priority → colour ── */
  _priorityColor(p = '') {
    const lower = p.toLowerCase();
    if (lower.includes('disease'))   return { bg: '#fee2e2', color: '#dc2626' };
    if (lower.includes('irrigation'))return { bg: '#dbeafe', color: '#0284c7' };
    if (lower.includes('nutrient'))  return { bg: '#fef3c7', color: '#ca8a04' };
    return { bg: '#dcfce7', color: '#16a34a' };
  },

  /* ── Sensor row HTML ── */
  _sensorRows(sensors) {
    if (!sensors) return '<div style="font-size:.72rem;color:#aac0aa;">No sensor data</div>';
    const fields = [
      ['Soil Moisture', sensors.soil_moisture, '%',    30, 70],
      ['Temperature',   sensors.temperature,   '°C',   15, 32],
      ['Humidity',      sensors.humidity,      '%',    35, 75],
      ['pH Level',      sensors.ph_level,      '',     6.0, 7.2],
      ['Nitrogen',      sensors.nitrogen,      ' mg/kg', 20, 80],
    ];
    return fields.map(([label, val, unit, lo, hi]) => {
      if (val == null) return '';
      const cls = val < lo ? 'val-low' : val > hi ? 'val-dec' : 'val-ok';
      const tag = val < lo ? 'LOW' : val > hi ? 'HIGH' : 'OK';
      return `<div class="divider-row">
        <span class="row-key">${label}</span>
        <span class="row-val ${cls}">${val.toFixed(1)}${unit} · ${tag}</span>
      </div>`;
    }).join('');
  },

  /* ── Recommendations list ── */
  _recommendations(recs = []) {
    if (!recs.length) return '<div style="font-size:.72rem;color:#aac0aa;">No recommendations</div>';
    return recs.map((r, i) => `
      <div style="display:flex;align-items:flex-start;gap:.5rem;padding:.4rem 0;
                  border-bottom:1px solid #f0f5f0;" ${i === recs.length - 1 ? 'style="border:none"' : ''}>
        <span style="color:#16a34a;font-weight:700;font-size:.8rem;">${i + 1}.</span>
        <span style="font-size:.75rem;color:#3a5a3a;line-height:1.5;">${r}</span>
      </div>`).join('');
  },

  _render(r, imageUrl) {
    const pColor   = this._priorityColor(r.priority ?? '');
    const confPct  = Math.round((r.confidence_score ?? 0.85) * 100);
    const imgSrc   = imageUrl
      ?? `http://localhost:8000/assets/demo_images/${r.disease_name?.toLowerCase().includes('blight') ? 'late_blight' : r.disease_name?.toLowerCase().includes('healthy') ? 'healthy' : 'early_blight'}.jpg`;

    return `
    <!-- Topbar -->
    <div class="topbar">
      <button class="btn-back" id="btn-back"
              style="width:32px;height:32px;background:#fff;border-radius:10px;border:1px solid #e0e8dc;
                     display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1rem;">‹</button>
      <h2 style="font-size:.95rem;font-weight:700;color:#1a3a1a;">Diagnosis Details</h2>
      <div style="width:32px;"></div>
    </div>

    <!-- Crop Image -->
    <div style="margin:.4rem 1.2rem;border-radius:18px;overflow:hidden;height:140px;position:relative;
                background:linear-gradient(135deg,#1a3a0a,#2d5c1a);">
      <img src="${imgSrc}" alt="crop"
           style="width:100%;height:100%;object-fit:cover;"
           onerror="this.style.display='none'"/>
      <div style="position:absolute;top:.6rem;left:.6rem;background:#ff7a00;color:#fff;
                  font-size:.65rem;font-weight:800;padding:.2rem .6rem;border-radius:8px;">⚡ AI ANALYZED</div>
    </div>

    <!-- Diagnosis -->
    <div class="card">
      <div class="card-label">🔬 Diagnosis</div>
      <h3 style="font-size:1.05rem;font-weight:800;color:#1a1a1a;line-height:1.3;">${r.disease_name ?? 'Unknown'}</h3>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.5rem;">
        <div class="pill">📍 ${r.sensor_data?.field_id ?? 'Field'}</div>
        <div class="pill">🕐 Detected today</div>
        <div class="pill" style="background:${pColor.bg};border-color:${pColor.bg};color:${pColor.color};">
          ⚠️ ${r.priority ?? 'N/A'}
        </div>
      </div>
    </div>

    <!-- Confidence -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">
        <div class="card-title">📊 Confidence Score</div>
        <div style="font-size:1.4rem;font-weight:800;color:#1a3a1a;">${confPct}<span style="font-size:.7rem;color:#6a9a6a">%</span></div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${confPct}%;"></div>
      </div>
    </div>

    <!-- Sensor Data Sync -->
    <div class="card">
      <div class="card-title">🔄 Sensor Data Sync</div>
      ${this._sensorRows(r.sensor_data)}
    </div>

    <!-- AI Reasoning -->
    <div class="card">
      <div class="card-title">🤖 AI Reasoning</div>
      <p style="font-size:.75rem;color:#3a5a3a;line-height:1.6;">${r.ai_reasoning ?? r.diagnosis_summary ?? 'No reasoning available.'}</p>
    </div>

    <!-- Recommendations -->
    <div class="card">
      <div class="card-title">💡 Recommendations</div>
      ${this._recommendations(r.recommendations ?? [])}
    </div>

    <!-- CTA -->
    <div style="padding:0 1.2rem 1rem;">
      <button class="btn btn-dark" id="btn-goto-actions">Go to Action Center →</button>
      <div style="text-align:center;font-size:.65rem;color:#8a9a8a;padding:.4rem;">
        Recommended: immediate targeted fertilization and irrigation adjustment.
      </div>
    </div>
    `;
  },

  _loading() {
    return `
    <div class="topbar">
      <h2 style="font-size:.95rem;font-weight:700;color:#1a3a1a;">Diagnosis Details</h2>
    </div>
    <div class="card" style="text-align:center;padding:2rem;">
      <div class="spinner"></div>
      <div style="margin-top:.8rem;font-size:.8rem;color:#6a9a6a;">Loading diagnosis…</div>
    </div>`;
  },

  _bindEvents(container, result) {
    container.querySelector('#btn-back')?.addEventListener('click',
      () => router.navigate('vision'));

    container.querySelector('#btn-goto-actions')?.addEventListener('click',
      () => router.navigate('actions', { result }));
  },
};

export default ReportScreen;
