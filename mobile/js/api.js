/* ─────────────────────────────────────────
   API.JS  –  All backend service calls
   Base URL is read from js/config.js
   ───────────────────────────────────────── */

import Config from './config.js';
const BASE_URL = Config.BASE_URL;

const Api = {

  /* ── GET /devices/status
     Returns { device_state: { field_id, soil_moisture, temperature,
               humidity, ph_level, nitrogen, ... } }
  ── */
  async getSensors() {
    const res = await fetch(`${BASE_URL}/devices/status`);
    if (!res.ok) throw new Error(`Sensor fetch failed: ${res.status}`);
    return res.json();
  },

  /* ── GET /demo/plant-disease/{scenario}
     scenario: 'late-blight' | 'nutrient-deficiency' | 'healthy'
     Returns PlantDiseaseResult
  ── */
  async getDemoScenario(scenario = 'nutrient-deficiency') {
    const res = await fetch(`${BASE_URL}/demo/plant-disease/${scenario}`);
    if (!res.ok) throw new Error(`Demo scenario failed: ${res.status}`);
    return res.json();
  },

  /* ── POST /analyze/plant-disease/upload
     Accepts FormData with: image (File), field_id, question,
     soil_moisture, temperature, humidity, ph_level, nitrogen,
     phosphorus, potassium, light_intensity
     Returns PlantDiseaseResult
  ── */
  async analyzeImage(formData) {
    const res = await fetch(`${BASE_URL}/analyze/plant-disease/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Analysis failed: ${res.status}`);
    }
    return res.json();
  },

  /* ── POST /analyze/text
     Accepts FormData with: field_id, question + sensor fields
     Returns DiagnosisResult
  ── */
  async analyzeText(formData) {
    const res = await fetch(`${BASE_URL}/analyze/text`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Text analysis failed: ${res.status}`);
    }
    return res.json();
  },

  /* ── POST /analyze/audio
     Accepts FormData with: audio (Blob/File) + sensor fields
     Returns DiagnosisResult
  ── */
  async analyzeAudio(formData) {
    const res = await fetch(`${BASE_URL}/analyze/audio`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Audio analysis failed: ${res.status}`);
    }
    return res.json();
  },

};

export default Api;
