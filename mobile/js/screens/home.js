/* ─────────────────────────────────────────
   HOME SCREEN  –  Field Health Status
   API: GET /devices/status
   ───────────────────────────────────────── */

import Api from '../api.js';

const HomeScreen = {

  mount(container) {
    container.innerHTML = this._skeleton();
    this._loadSensors(container);
  },

  unmount() {},

  /* ── Fetch sensor data & re-render ── */
  async _loadSensors(container) {
    try {
      const data = await Api.getSensors();
      const s = data.device_state;
      container.innerHTML = this._render(s);
      this._bindEvents(container);
      this._animateRing(container, s.soil_moisture ?? 85);
    } catch (err) {
      container.querySelector('.sensor-grid').innerHTML =
        `<div class="error-state">⚠️ ${err.message}</div>`;
    }
  },

  /* ── Vitality score derived from sensors ── */
  _vitality(s) {
    const moist = s.soil_moisture  ?? 64;
    const ph    = s.ph_level       ?? 6.8;
    const temp  = s.temperature    ?? 24;
    const hum   = s.humidity       ?? 42;
    let score = 100;
    if (moist < 30 || moist > 80)  score -= 20;
    if (ph < 5.5   || ph > 7.5)    score -= 15;
    if (temp > 35  || temp < 10)   score -= 15;
    if (hum < 30   || hum > 90)    score -= 10;
    return Math.max(0, Math.min(100, score));
  },

  _vitalityLabel(v) {
    if (v >= 80) return { label: 'Excellent', sub: 'Your crops are showing optimal photosynthesis levels. No immediate intervention required.' };
    if (v >= 60) return { label: 'Good',      sub: 'Crop health is stable. Minor adjustments recommended.' };
    if (v >= 40) return { label: 'Fair',      sub: 'Some sensors indicate stress. Review AI recommendations.' };
    return         { label: 'Critical',  sub: 'Immediate action required. Check Action Center.' };
  },

  /* ── Ring dash offset (283 = full circle circumference) ── */
  _dashOffset(pct) {
    return Math.round(283 - (283 * pct) / 100);
  },

  _deltaBadge(val, low, high) {
    if (val < low)  return '<span class="badge badge-red">Low</span>';
    if (val > high) return '<span class="badge badge-yellow">High</span>';
    return '<span class="badge badge-green">OK</span>';
  },

  /* ── Sparkline SVG (simple fake trend) ── */
  _spark(color, trend = 'up') {
    const points = trend === 'up'
      ? '0,18 15,14 30,16 45,10 60,12 80,8'
      : '0,8  15,10 30,12 45,14 60,16 80,20';
    return `<svg viewBox="0 0 80 24" preserveAspectRatio="none">
      <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
  },

  /* ── Full HTML render ── */
  _render(s) {
    const vitality = this._vitality(s);
    const { label, sub } = this._vitalityLabel(vitality);
    const offset = this._dashOffset(vitality);

    const moist = (s.soil_moisture  ?? 64).toFixed(1);
    const ph    = (s.ph_level       ?? 6.8).toFixed(1);
    const temp  = (s.temperature    ?? 24).toFixed(1);
    const hum   = (s.humidity       ?? 42).toFixed(1);

    return `
    <div class="topbar">
      <div class="brand"><div class="brand-dot"></div>Agri-Lens</div>
      <div class="icon-group">
        <div class="icon-btn">🔔</div>
        <div class="icon-btn">👤</div>
      </div>
    </div>

    <!-- Vitality Ring -->
    <div class="card" style="text-align:center;">
      <div class="vitality-ring" style="width:110px;height:110px;position:relative;margin:0 auto .8rem;">
        <svg viewBox="0 0 100 100" width="110" height="110" style="transform:rotate(-90deg)">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e8f5e8" stroke-width="10"/>
          <circle cx="50" cy="50" r="45" fill="none" stroke="#16a34a" stroke-width="10"
            stroke-linecap="round" stroke-dasharray="283"
            stroke-dashoffset="${offset}" id="ring-fill"
            style="transition:stroke-dashoffset 1.2s ease"/>
        </svg>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;">
          <span style="font-size:1.5rem;font-weight:800;color:#1a3a1a;" id="ring-pct">${vitality}%</span>
          <span style="font-size:.6rem;color:#6a9a6a;font-weight:600;">VITALITY</span>
        </div>
      </div>
      <div style="font-size:1.3rem;font-weight:800;color:#16a34a;">${label}</div>
      <div style="font-size:.75rem;color:#5a8a5a;margin-top:.25rem;line-height:1.4;">${sub}</div>
    </div>

    <!-- Sensor Grid -->
    <div class="sensor-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin:.4rem 1.2rem;">
      <div class="card-sm">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
          <span style="font-size:1.1rem;">💧</span>
          ${this._deltaBadge(moist, 30, 70)}
        </div>
        <div style="font-size:1.4rem;font-weight:800;color:#1a3a1a;">${moist}%</div>
        <div style="font-size:.65rem;color:#7a9a7a;">Soil Moisture</div>
        <div class="sparkline">${this._spark('#4ade80', moist > 50 ? 'up' : 'down')}</div>
      </div>
      <div class="card-sm">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
          <span style="font-size:1.1rem;">🧪</span>
          ${this._deltaBadge(ph, 6.0, 7.2)}
        </div>
        <div style="font-size:1.4rem;font-weight:800;color:#1a3a1a;">${ph}</div>
        <div style="font-size:.65rem;color:#7a9a7a;">pH Level</div>
        <div class="sparkline">${this._spark('#fbbf24', 'up')}</div>
      </div>
      <div class="card-sm">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
          <span style="font-size:1.1rem;">🌡️</span>
          ${this._deltaBadge(temp, 15, 32)}
        </div>
        <div style="font-size:1.4rem;font-weight:800;color:#1a3a1a;">${temp}°C</div>
        <div style="font-size:.65rem;color:#7a9a7a;">Temperature</div>
        <div class="sparkline">${this._spark('#f97316', temp > 28 ? 'up' : 'down')}</div>
      </div>
      <div class="card-sm">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
          <span style="font-size:1.1rem;">💨</span>
          ${this._deltaBadge(hum, 35, 75)}
        </div>
        <div style="font-size:1.4rem;font-weight:800;color:#1a3a1a;">${hum}%</div>
        <div style="font-size:.65rem;color:#7a9a7a;">Humidity</div>
        <div class="sparkline">${this._spark('#60a5fa', hum > 50 ? 'up' : 'down')}</div>
      </div>
    </div>

    <!-- Recent AI Actions -->
    <div class="section-header">
      <h3>Recent AI Actions</h3>
      <a>See all</a>
    </div>
    <div style="padding:0 1.2rem;display:flex;flex-direction:column;gap:.6rem;margin-bottom:.6rem;">
      <div class="card-sm" style="display:flex;align-items:flex-start;gap:.7rem;">
        <div class="icon-box" style="background:#dbeafe;">💧</div>
        <div style="flex:1;">
          <div style="font-size:.78rem;font-weight:700;color:#1a3a1a;">Last Irrigation</div>
          <div style="font-size:.68rem;color:#6a9a6a;margin-top:.15rem;line-height:1.4;">Optimized for soil moisture (${moist}%). Saved 12L of water compared to schedule.</div>
          <div style="font-size:.6rem;color:#aac0aa;margin-top:.2rem;">2h ago &nbsp;<span class="badge badge-green">COMPLETED</span></div>
        </div>
      </div>
      <div class="card-sm" style="display:flex;align-items:flex-start;gap:.7rem;">
        <div class="icon-box" style="background:#dcfce7;">🌿</div>
        <div style="flex:1;">
          <div style="font-size:.78rem;font-weight:700;color:#1a3a1a;">Nitrogen Check</div>
          <div style="font-size:.68rem;color:#6a9a6a;margin-top:.15rem;line-height:1.4;">Scanning Plot B completed. Nutrient levels are in the 90th percentile.</div>
          <div style="font-size:.6rem;color:#aac0aa;margin-top:.2rem;">5h ago &nbsp;<span class="badge badge-blue">DONE</span></div>
        </div>
      </div>
      <div class="card-sm" style="display:flex;align-items:flex-start;gap:.7rem;">
        <div class="icon-box" style="background:#fef3c7;">🔍</div>
        <div style="flex:1;">
          <div style="font-size:.78rem;font-weight:700;color:#1a3a1a;">Pest Scan</div>
          <div style="font-size:.68rem;color:#6a9a6a;margin-top:.15rem;line-height:1.4;">No pathogenic activity detected via Vision module.</div>
          <div style="font-size:.6rem;color:#aac0aa;margin-top:.2rem;">Yesterday</div>
        </div>
      </div>
    </div>

    <!-- Field Banner -->
    <div class="field-banner" style="margin-bottom:1rem;">
      <img src="http://localhost:8000/assets/demo_images/healthy.jpg" alt="field" onerror="this.style.display='none'"/>
      <div class="banner-info">
        <div class="banner-label">Current Active View</div>
        <div class="banner-name">Western Acreage – Plot A</div>
      </div>
    </div>
    `;
  },

  _skeleton() {
    return `
    <div class="topbar">
      <div class="brand"><div class="brand-dot"></div>Agri-Lens</div>
      <div class="icon-group"><div class="icon-btn">🔔</div><div class="icon-btn">👤</div></div>
    </div>
    <div class="card" style="text-align:center;padding:2rem;">
      <div class="spinner"></div>
      <div style="margin-top:.8rem;font-size:.8rem;color:#6a9a6a;">Loading sensor data…</div>
    </div>
    <div class="sensor-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin:.4rem 1.2rem;"></div>`;
  },

  _animateRing(container, pct) {
    const offset = this._dashOffset(pct);
    requestAnimationFrame(() => {
      const ring = container.querySelector('#ring-fill');
      if (ring) ring.style.strokeDashoffset = offset;
    });
  },

  _bindEvents(container) {
    /* Refresh button (if ever added) can hook here */
  },
};

export default HomeScreen;
