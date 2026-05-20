/* ─────────────────────────────────────────
   ROUTER.JS  –  Screen navigation manager
   ───────────────────────────────────────── */

/* Each screen module exports: { mount(container) } */
import HomeScreen     from './screens/home.js';
import VisionScreen   from './screens/vision.js';
import ReportScreen   from './screens/report.js';
import ActionsScreen  from './screens/actions.js';
import AnalyticsScreen from './screens/analytics.js';

const SCREENS = {
  home:      HomeScreen,
  vision:    VisionScreen,
  report:    ReportScreen,
  actions:   ActionsScreen,
  analytics: AnalyticsScreen,
};

class Router {
  constructor() {
    this.current = null;
    this.instances = {};
  }

  /** Navigate to a named screen, optionally passing state data */
  navigate(name, state = {}) {
    if (!SCREENS[name]) {
      console.warn(`[Router] Unknown screen: ${name}`);
      return;
    }

    /* Deactivate old screen */
    if (this.current) {
      const oldEl = document.getElementById(`screen-${this.current}`);
      if (oldEl) oldEl.classList.remove('active');

      const oldNav = document.getElementById(`nav-${this.current}`);
      if (oldNav) oldNav.classList.remove('active');

      /* Call unmount lifecycle if defined */
      if (this.instances[this.current]?.unmount) {
        this.instances[this.current].unmount();
      }
    }

    this.current = name;

    /* Activate new screen */
    const el = document.getElementById(`screen-${name}`);
    if (el) {
      el.classList.add('active');
      el.scrollTop = 0;
    }

    const nav = document.getElementById(`nav-${name}`);
    if (nav) nav.classList.add('active');

    /* Lazy-create & mount screen instance */
    if (!this.instances[name]) {
      this.instances[name] = Object.create(SCREENS[name]);
    }

    const container = document.getElementById(`screen-${name}`);
    if (container && this.instances[name].mount) {
      this.instances[name].mount(container, state);
    }
  }
}

const router = new Router();
export default router;
