/* Synchronised multi-camera player.
 *
 * One <video> per camera; the main camera is the clock and the others are nudged back into sync when they
 * drift.  Consecutive one-minute segment files are stitched into a single continuous timeline.
 */
class MultiCamPlayer {
  constructor(tilesEl, callbacks) {
    this.tilesEl = tilesEl;
    this.cb = Object.assign({ onTime: () => {}, onPlayState: () => {}, onEnded: () => {}, onRangeEnd: () => {}, onTileClick: () => {} }, callbacks);
    this.event = null;
    this.segStarts = [];
    this.videos = new Map(); // camera -> {el, tile, idx, label, nosignal}
    this.tiles = [];
    this.view = { cameras: ['front'], main: 'front', fit: 'cover', mirror: false, labels: false, labelsMap: {} };
    this.playing = false;
    this.rate = 1;
    this.segIdx = 0;
    this.stopAt = null;
    this._raf = null;
    this._lastSync = 0;
    this._pendingSeeks = 0;
    this._loop = this._loop.bind(this);
  }

  /* ---------- loading ---------- */
  load(event) {
    this.pause();
    this.event = event;
    this.segStarts = [];
    let acc = 0;
    for (const s of event.segments) { this.segStarts.push(acc); acc += s.duration; }
    this.duration = acc;
    this.segIdx = 0;
    this.stopAt = null;
    for (const v of this.videos.values()) { v.el.removeAttribute('src'); v.el.load(); v.tile.remove(); }
    this.videos.clear();
    for (const cam of event.cameras) this._createTile(cam);
    this.applyTiles(this.tiles);
    this.seek(0);
  }

  _createTile(cam) {
    const tile = document.createElement('div');
    tile.className = 'tile';
    tile.dataset.camera = cam;
    const el = document.createElement('video');
    el.muted = true; el.playsInline = true; el.preload = 'auto'; el.disablePictureInPicture = true;
    el.addEventListener('ended', () => { if (this.playing && this._master() === el) this._advance(); });
    el.addEventListener('error', () => { /* missing segment for this camera; tile shows "no signal" */ });
    const nosignal = document.createElement('div');
    nosignal.className = 'nosignal'; nosignal.textContent = 'No recording'; nosignal.hidden = true;
    const label = document.createElement('div');
    label.className = 'label'; label.hidden = true;
    tile.append(el, nosignal, label);
    tile.addEventListener('click', () => this.cb.onTileClick(cam));
    this.tilesEl.appendChild(tile);
    this.videos.set(cam, { el, tile, idx: -1, nosignal, label });
  }

  /* ---------- view / layout ---------- */
  setView(view) {
    Object.assign(this.view, view);
    for (const [cam, v] of this.videos) {
      const visible = this.tiles.some(t => t.camera === cam);
      v.tile.classList.toggle('main', cam === this.view.main);
      v.tile.classList.toggle('multi', this.tiles.length > 1);
      v.tile.classList.toggle('mirrored', this.view.mirror && cam !== 'front');
      v.tile.classList.toggle('contain', this.view.fit === 'contain');
      v.label.hidden = !this.view.labels;
      v.label.textContent = (this.view.labelsMap || {})[cam] || cam;
      if (!visible && !v.el.paused) v.el.pause();
      if (visible && this.playing && v.el.paused && v.el.src) v.el.play().catch(() => {});
    }
    // The main camera may have changed: re-align the clock source.
    this._syncSlaves(true);
  }

  applyTiles(tiles) {
    this.tiles = tiles || [];
    for (const [cam, v] of this.videos) {
      const t = this.tiles.find(x => x.camera === cam);
      if (!t) { v.tile.style.display = 'none'; continue; }
      v.tile.style.display = '';
      v.tile.style.left = (t.x * 100) + '%';
      v.tile.style.top = (t.y * 100) + '%';
      v.tile.style.width = (t.w * 100) + '%';
      v.tile.style.height = (t.h * 100) + '%';
      v.tile.style.zIndex = cam === this.view.main ? 1 : 2;
    }
    this.setView({});
    if (this.event) this._ensureSegment(this.segIdx, this.time);
  }

  /* ---------- time ---------- */
  get time() {
    const m = this._master();
    if (!m) return this.segStarts[this.segIdx] || 0;
    return (this.segStarts[this.segIdx] || 0) + (m.currentTime || 0);
  }

  epochAt(t) {
    if (!this.event) return null;
    const idx = this._segIndex(t);
    return this.event.segments[idx].start_epoch + (t - this.segStarts[idx]);
  }

  _segIndex(t) {
    let idx = 0;
    for (let i = 0; i < this.segStarts.length; i++) if (t >= this.segStarts[i]) idx = i;
    return idx;
  }

  _visibleCams() { return this.tiles.map(t => t.camera).filter(c => this.videos.has(c)); }

  _master() {
    if (!this.event) return null;
    const seg = this.event.segments[this.segIdx];
    const cams = this._visibleCams();
    const order = [this.view.main, ...cams];
    for (const cam of order) {
      const v = this.videos.get(cam);
      if (v && seg.files[cam] && cams.includes(cam)) return v.el;
    }
    const any = cams.map(c => this.videos.get(c)).find(v => v && seg.files[v.tile.dataset.camera]);
    return any ? any.el : null;
  }

  _ensureSegment(idx, t) {
    const seg = this.event.segments[idx];
    const off = Math.max(0, Math.min(seg.duration, t - this.segStarts[idx]));
    for (const cam of this._visibleCams()) {
      const v = this.videos.get(cam);
      const has = !!seg.files[cam];
      v.nosignal.hidden = has;
      v.el.style.visibility = has ? '' : 'hidden';
      if (!has) { v.idx = idx; continue; }
      if (v.idx !== idx) {
        v.idx = idx;
        v.el.src = `/api/media/${this.event.id}/${idx}/${cam}`;
        v.el.playbackRate = this.rate;
        const setTime = () => { try { v.el.currentTime = off; } catch (e) { /* not ready */ } };
        if (v.el.readyState >= 1) setTime(); else v.el.addEventListener('loadedmetadata', setTime, { once: true });
        if (this.playing) v.el.play().catch(() => {});
      } else if (Math.abs(v.el.currentTime - off) > 0.05) {
        v.el.currentTime = off;
      }
    }
  }

  seek(t) {
    if (!this.event) return;
    t = Math.max(0, Math.min(this.duration - 0.001, t));
    const idx = this._segIndex(t);
    this.segIdx = idx;
    this._ensureSegment(idx, t);
    this.cb.onTime(t);
  }

  _advance() {
    if (this.segIdx + 1 < this.event.segments.length) {
      this.seek(this.segStarts[this.segIdx + 1] + 0.001);
      if (this.playing) this._playAll();
    } else {
      this.pause();
      this.seek(this.duration - 0.001);
      this.cb.onEnded();
    }
  }

  /* ---------- transport ---------- */
  _playAll() {
    for (const cam of this._visibleCams()) {
      const v = this.videos.get(cam);
      if (v.el.src && v.el.style.visibility !== 'hidden') { v.el.playbackRate = this.rate; v.el.play().catch(() => {}); }
    }
  }

  play() {
    if (!this.event) return;
    if (this.time >= this.duration - 0.05) this.seek(0);
    this.playing = true;
    this._playAll();
    cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(this._loop);
    this.cb.onPlayState(true);
  }

  pause() {
    this.playing = false;
    cancelAnimationFrame(this._raf);
    for (const v of this.videos.values()) v.el.pause();
    this.cb.onPlayState(false);
  }

  toggle() { this.playing ? this.pause() : this.play(); }

  setRate(r) {
    this.rate = r;
    for (const v of this.videos.values()) v.el.playbackRate = r;
  }

  step(frames) {
    this.pause();
    const fps = 30;
    this.seek(this.time + frames / fps);
  }

  playRange(t0, t1) {
    this.stopAt = t1;
    this.seek(t0);
    this.play();
  }

  _syncSlaves(force) {
    const master = this._master();
    if (!master) return;
    const mt = master.currentTime;
    for (const cam of this._visibleCams()) {
      const v = this.videos.get(cam);
      if (v.el === master || v.el.style.visibility === 'hidden' || !v.el.src) continue;
      const drift = v.el.currentTime - mt;
      if (Math.abs(drift) > (force ? 0.05 : 0.12) && v.el.readyState >= 1) v.el.currentTime = mt;
      if (this.playing && v.el.paused && !v.el.ended) v.el.play().catch(() => {});
    }
  }

  _loop(ts) {
    if (!this.playing) return;
    const master = this._master();
    if (master) {
      const seg = this.event.segments[this.segIdx];
      const t = this.time;
      if (this.stopAt != null && t >= this.stopAt - 0.02) {
        this.pause();
        this.stopAt = null;
        this.cb.onTime(t);
        this.cb.onRangeEnd();
        return;
      }
      if (master.ended || master.currentTime >= seg.duration - 0.02) {
        this._advance();
      } else {
        if (ts - this._lastSync > 250) { this._lastSync = ts; this._syncSlaves(false); }
        this.cb.onTime(t);
      }
    }
    this._raf = requestAnimationFrame(this._loop);
  }
}

window.MultiCamPlayer = MultiCamPlayer;
