/* ─────────────────────────────────────────
   ANALYTICS SCREEN  –  Growth Analytics
   API: GET /demo/plant-disease/{scenario}
        GET /devices/status
   ───────────────────────────────────────── */

import Api from '../api.js';

const SCENARIOS = ['late-blight', 'nutrient-deficiency', 'healthy'];

const AnalyticsScreen = {

  _activeScenario: 'healthy',
  _activePeriod: '1Y',

  mount(container) {
    container.innerHTML = this._skeleton();
    this._load(container);
  },

  unmount() {},

  async _load(container) {
    try {
      const [demoData, sensorData] = await Promise.all([
        Api.getDemoScenario(this._activeScenario),
        Api.getSensors().catch(() => ({ device_state: {} })),
      ]);
      container.innerHTML = this._render(demoData, sensorData.device_state);
      this._bindEvents(container);
    } catch (err) {
      container.innerHTML = `<div class="error-state">⚠️ ${err.message}</div>`;
    }
  },

  /* ── Generate fake chart path based on scenario ── */
  _chartPath(scenario) {
    const paths = {
      'healthy':             'M0,80 L25,72 L50,75 L75,60 L100,55 L125,48 L150,42 L175,45 L200,36 L225,28 L250,18 L275,12 L300,8',
      'late-blight':         'M0,30 L25,28 L50,32 L75,45 L100,55 L125,65 L150,70 L175,72 L200,68 L225,60 L250,55 L275,50 L300,48',
      'nutrient-deficiency': 'M0,40 L25,38 L50,42 L75,50 L100,55 L125,58 L150,54 L175,50 L200,45 L225,40 L250,35 L275,30 L300,28',
    };
    return paths[scenario] ?? paths['healthy'];
  },

  _milestones(result) {
    const field = result.sensor_data?.field_id ?? 'Field';
    return [
      { icon: '🌱', bg: '#dcfce7', title: 'Planting Date',     sub: `Winter Wheat · ${field}`,             date: 'Oct 14, 2023', status: 'COMPLETED', cls: 'badge-green' },
      { icon: '📈', bg: '#dbeafe', title: 'Peak Growth',       sub: 'Vegetative phase maximum height',       date: 'May 02, 2024', status: 'RECORDED',  cls: 'badge-blue'  },
      { icon: '🌾', bg: '#fef3c7', title: 'Harvest Prediction',sub: 'AI-estimated optimal harvest window',   date: 'Aug 18, 2024', status: 'PREDICTED', cls: 'badge-yellow'},
    ];
  },

  _render(result, sensors) {
    const path    = this._chartPath(this._activeScenario);
    const ms      = this._milestones(result);
    const moist   = (sensors.soil_moisture ?? 68).toFixed(0);
    const confPct = Math.round((result.confidence_score ?? 0.85) * 100);

    const scenarioTabs = SCENARIOS.map(s => `
      <button class="scenario-tab ${s === this._activeScenario ? 'active' : ''}"
              data-scenario="${s}"
              style="padding:.25rem .55rem;border-radius:6px;font-size:.64rem;font-weight:600;
                     cursor:pointer;border:1px solid #d4e8d4;
                     background:${s === this._activeScenario ? '#16a34a' : 'transparent'};
                     color:${s === this._activeScenario ? '#fff' : '#6a9a6a'};">
        ${s}
      </button>`).join('');

    const periodTabs = ['1M','3M','6M','1Y'].map(p => `
      <button class="time-tab ${p === this._activePeriod ? 'active' : ''}" data-period="${p}"
              style="padding:.3rem .65rem;border-radius:8px;font-size:.72rem;font-weight:600;cursor:pointer;
                     border:1px solid #d4e8d4;
                     background:${p === this._activePeriod ? '#16a34a' : 'transparent'};
                     color:${p === this._activePeriod ? '#fff' : '#6a9a6a'};">
        ${p}
      </button>`).join('');

    return `
    <!-- Topbar -->
    <div class="topbar">
      <div>
        <div style="font-size:.65rem;color:#16a34a;font-weight:700;text-transform:uppercase;letter-spacing:1px;">🌿 Agri-Lens</div>
        <h2>Growth Analytics</h2>
      </div>
      <div style="color:#6a9a6a;cursor:pointer;font-size:1.1rem;">⋮</div>
    </div>

    <!-- Period tabs + Export -->
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.2rem 1.2rem .4rem;">
      <div style="display:flex;gap:.35rem;">${periodTabs}</div>
      <button class="btn btn-outline" style="width:auto;padding:.3rem .65rem;font-size:.72rem;">📥 Export CSV</button>
    </div>

    <!-- Scenario Selector -->
    <div style="padding:.1rem 1.2rem .4rem;">
      <div style="font-size:.62rem;color:#aac0aa;margin-bottom:.3rem;">SCENARIO</div>
      <div style="display:flex;gap:.35rem;flex-wrap:wrap;">${scenarioTabs}</div>
    </div>

    <!-- Growth Chart -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.8rem;">
        <div>
          <h3 style="font-size:.82rem;font-weight:700;color:#1a3a1a;">Crop Growth Trend</h3>
          <div style="font-size:.62rem;color:#8aaa8a;margin-top:.1rem;">Aggregated health index · ${result.disease_name ?? 'Field'}</div>
        </div>
        <div class="ai-chip">▲ ${confPct}% Confidence</div>
      </div>
      <svg viewBox="0 0 300 100" style="width:100%;height:120px;" preserveAspectRatio="none">
        <defs>
          <linearGradient id="cg" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#4ade80" stop-opacity=".3"/>
            <stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${path} L300,100 L0,100Z" fill="url(#cg)"/>
        <path d="${path}" fill="none" stroke="#16a34a" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="300" cy="8" r="4" fill="#16a34a"/>
      </svg>
      <div style="display:flex;justify-content:space-between;font-size:.55rem;color:#aac0aa;padding:.2rem;">
        <span>SEP</span><span>OCT</span><span>NOV</span><span>DEC</span>
        <span>JAN</span><span>FEB</span><span>MAR</span><span>APR</span>
        <span>MAY</span><span>JUN</span><span>JUL</span><span>AUG</span>
      </div>
    </div>

    <!-- Key Milestones -->
    <div style="padding:.5rem 1.2rem 0;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">
        <h3 style="font-size:.85rem;font-weight:700;color:#1a3a1a;">Key Milestones</h3>
        <a style="font-size:.72rem;color:#16a34a;font-weight:600;cursor:pointer;">View History</a>
      </div>
      ${ms.map(m => `
      <div class="card-sm" style="display:flex;align-items:center;gap:.7rem;margin-bottom:.55rem;">
        <div class="icon-box" style="background:${m.bg};width:38px;height:38px;border-radius:10px;">${m.icon}</div>
        <div style="flex:1;">
          <div style="font-size:.78rem;font-weight:700;color:#1a3a1a;">${m.title}</div>
          <div style="font-size:.63rem;color:#6a9a6a;margin-top:.08rem;">${m.sub}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:.72rem;font-weight:700;color:#1a3a1a;">${m.date}</div>
          <span class="badge ${m.cls}" style="margin-top:.1rem;">${m.status}</span>
        </div>
      </div>`).join('')}
    </div>

    <!-- Soil Moisture Card -->
    <div style="margin:.5rem 1.2rem 1rem;border-radius:18px;overflow:hidden;position:relative;
                background:linear-gradient(135deg,#0a3a0a,#1a5a1a);padding:1rem;">
      <img src="http://localhost:8000/assets/demo_images/healthy.jpg" alt="sector"
           style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.25;"
           onerror="this.style.display='none'"/>
      <div style="position:relative;z-index:1;">
        <div style="font-size:.6rem;color:rgba(255,255,255,.65);text-transform:uppercase;letter-spacing:1px;">Current Active View</div>
        <div style="font-size:1rem;font-weight:800;color:#fff;margin:.2rem 0 .6rem;">North Sector B</div>
        <div style="height:7px;background:rgba(255,255,255,.2);border-radius:4px;overflow:hidden;margin-bottom:.3rem;">
          <div style="height:100%;background:#4ade80;border-radius:4px;width:${moist}%;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span style="font-size:.68rem;color:rgba(255,255,255,.7);">Soil Moisture</span>
          <strong style="font-size:.68rem;color:#fff;">${moist}%</strong>
        </div>
        <button class="btn btn-orange" style="margin-top:.7rem;border-radius:12px;font-size:.82rem;">Take Action</button>
      </div>
    </div>
    `;
  },

  _skeleton() {
    return `
    <div class="topbar">
      <div><div style="font-size:.65rem;color:#16a34a;font-weight:700;">🌿 Agri-Lens</div><h2>Growth Analytics</h2></div>
    </div>
    <div class="card" style="text-align:center;padding:2rem;">
      <div class="spinner"></div>
      <div style="margin-top:.8rem;font-size:.8rem;color:#6a9a6a;">Loading analytics…</div>
    </div>`;
  },

  _bindEvents(container) {
    /* Period tabs */
    container.querySelectorAll('.time-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this._activePeriod = btn.dataset.period;
        container.innerHTML = this._skeleton();
        this._load(container);
      });
    });

    /* Scenario tabs */
    container.querySelectorAll('.scenario-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this._activeScenario = btn.dataset.scenario;
        container.innerHTML = this._skeleton();
        this._load(container);
      });
    });

    /* Take Action */
    container.querySelector('.btn-orange')?.addEventListener('click', () => {
      import('../router.js').then(m => m.default.navigate('actions'));
    });
  },
};

export default AnalyticsScreen;
