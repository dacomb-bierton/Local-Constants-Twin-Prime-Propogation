/* TeslaCam Editor front end.  Talks to the local FastAPI server; all rendering happens there with ffmpeg. */
(() => {
  'use strict';
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const CAMERA_KEYS = { '1': 'front', '2': 'back', '3': 'left_repeater', '4': 'right_repeater', '5': 'left_pillar', '6': 'right_pillar' };

  const defaultView = () => ({
    cameras: ['front', 'back', 'left_repeater', 'right_repeater', 'left_pillar', 'right_pillar'],
    layout: 'grid', main_camera: 'front', fit: 'cover', mirror_rear: false,
    speed: 1, cycle_enabled: false, cycle_interval: 5, cycle_cameras: [],
    show_timestamp: true, show_labels: false, show_location: false, blur_regions: [],
  });

  const state = {
    config: null, events: [], kind: 'all', search: '',
    event: null, view: defaultView(), aspect: '16:9',
    inPoint: null, outPoint: null,
    project: { name: 'Untitled', items: [], music: null, export: { aspect: '16:9', resolution: 1080, fps: 30, quality: 'standard', format: 'mp4', encoder: 'auto', background: '#000000', watermark_path: null, watermark_opacity: 0.7, watermark_scale: 0.15, watermark_position: 'br', output_dir: null, filename: null } },
    selectedItem: null,
    seq: null,           // sequence preview state {i}
    layoutCache: new Map(),
    layoutReq: 0,
    cycleTimer: null,
    drawing: false,
    musicUrl: null,
    exportJob: null,
    map: null,
  };

  /* ---------------- helpers ---------------- */
  const fmtTime = (t, frac = true) => {
    t = Math.max(0, t || 0);
    const m = Math.floor(t / 60), s = t - m * 60;
    return frac ? `${m}:${s.toFixed(1).padStart(4, '0')}` : `${m}:${Math.floor(s).toString().padStart(2, '0')}`;
  };
  const fmtClock = (epoch) => {
    if (epoch == null) return '';
    const d = new Date(epoch * 1000);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  };
  const fmtBytes = (b) => b > 1e9 ? (b / 1e9).toFixed(2) + ' GB' : (b / 1e6).toFixed(0) + ' MB';
  const uid = () => Math.random().toString(36).slice(2, 10);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const camLabel = (c) => (state.config && state.config.camera_labels[c]) || c;

  async function api(path, opts = {}) {
    const res = await fetch(path, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) { /* ignore */ }
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return res.json();
  }
  const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });

  let toastTimer;
  function toast(msg, err = false) {
    const el = $('#toast');
    el.textContent = msg; el.classList.toggle('err', err); el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, err ? 6000 : 2500);
  }
  function stageToast(msg) {
    const el = $('#stage-toast');
    el.textContent = msg; el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 1200);
  }

  function openModal(id) { $(id).hidden = false; }
  function closeModals() { $$('.modal').forEach(m => { m.hidden = true; }); }
  $$('.modal-close').forEach(b => b.addEventListener('click', closeModals));
  $$('.modal').forEach(m => m.addEventListener('click', (e) => { if (e.target === m) closeModals(); }));

  function confirmDialog(title, text, okLabel = 'Delete') {
    return new Promise((resolve) => {
      $('#confirm-title').textContent = title;
      $('#confirm-text').innerHTML = text;
      $('#confirm-ok').textContent = okLabel;
      openModal('#modal-confirm');
      const ok = $('#confirm-ok');
      const done = (v) => { ok.onclick = null; closeModals(); resolve(v); };
      ok.onclick = () => done(true);
      $$('#modal-confirm .modal-close').forEach(b => { b.onclick = () => done(false); });
    });
  }
  function promptDialog(title, value = '') {
    return new Promise((resolve) => {
      $('#prompt-title').textContent = title;
      const input = $('#prompt-input');
      input.value = value;
      openModal('#modal-prompt');
      input.focus();
      const done = (v) => { $('#prompt-ok').onclick = null; input.onkeydown = null; closeModals(); resolve(v); };
      $('#prompt-ok').onclick = () => done(input.value.trim());
      input.onkeydown = (e) => { if (e.key === 'Enter') done(input.value.trim()); if (e.key === 'Escape') done(null); };
      $$('#modal-prompt .modal-close').forEach(b => { b.onclick = () => done(null); });
    });
  }

  /* ---------------- player ---------------- */
  const player = new MultiCamPlayer($('#tiles'), {
    onTime: (t) => updateTimeUI(t),
    onPlayState: (playing) => {
      $('#btn-play').innerHTML = playing ? '&#10074;&#10074;' : '&#9654;';
      if (playing) startCycleTimer(); else stopCycleTimer();
    },
    onEnded: () => { if (state.seq) nextSeqItem(); },
    onRangeEnd: () => { if (state.seq) nextSeqItem(); },
    onTileClick: (cam) => { if (state.drawing) return; setMain(cam); },
  });

  function updateTimeUI(t) {
    if (!state.event) return;
    $('#time-display').textContent = `${fmtTime(t)} / ${fmtTime(state.event.duration)}`;
    $('#clock-display').textContent = fmtClock(player.epochAt(t));
    $('#tl-head').style.left = (t / state.event.duration * 100) + '%';
    $('#tl-progress').style.width = (t / state.event.duration * 100) + '%';
    const clock = $('#ov-clock');
    if (clock) clock.textContent = fmtClock(player.epochAt(t));
  }

  /* ---------------- stage sizing & layout ---------------- */
  function aspectWH(aspect) {
    const [a, b] = aspect.split(':').map(Number);
    return [a || 16, b || 9];
  }
  function canvasSize(aspect, short) {
    const [a, b] = aspectWH(aspect);
    const even = (v) => { let n = Math.round(v); return n % 2 ? n - 1 : n; };
    return a >= b ? [even(short * a / b), even(short)] : [even(short), even(short * b / a)];
  }
  function fitStage() {
    const wrap = $('#stage-wrap'), stage = $('#stage');
    const [a, b] = aspectWH(state.aspect);
    const pad = 24;
    const W = wrap.clientWidth - pad, H = wrap.clientHeight - pad;
    let w = W, h = W * b / a;
    if (h > H) { h = H; w = H * a / b; }
    stage.style.width = Math.floor(w) + 'px';
    stage.style.height = Math.floor(h) + 'px';
  }
  new ResizeObserver(fitStage).observe($('#stage-wrap'));

  async function fetchLayout(layout, cameras, main, aspect) {
    const key = `${layout}|${cameras.join(',')}|${main}|${aspect}`;
    if (state.layoutCache.has(key)) return state.layoutCache.get(key);
    const data = await api(`/api/layout?layout=${layout}&cameras=${cameras.join(',')}&main=${main}&aspect=${encodeURIComponent(aspect)}`);
    state.layoutCache.set(key, data);
    return data;
  }

  function effectiveCameras() {
    if (!state.event) return state.view.cameras;
    const cams = state.view.cameras.filter(c => state.event.cameras.includes(c));
    return cams.length ? cams : state.event.cameras.slice(0, 1);
  }
  function effectiveMain(cams) {
    return cams.includes(state.view.main_camera) ? state.view.main_camera : cams[0];
  }

  async function applyView() {
    const v = state.view;
    const cams = effectiveCameras();
    const main = effectiveMain(cams);
    const req = ++state.layoutReq;
    let data;
    try { data = await fetchLayout(v.layout, cams, main, state.aspect); } catch (e) { toast(e.message, true); return; }
    if (req !== state.layoutReq) return;
    player.view.main = main;
    player.applyTiles(data.tiles);
    player.setView({ cameras: cams, main, fit: v.fit, mirror: v.mirror_rear, labels: v.show_labels, labelsMap: state.config ? state.config.camera_labels : {} });
    player.setRate(v.speed);
    renderOverlays(data.tiles, main);
    renderBlurBoxes();
    syncViewControls(cams, main);
    if (state.selectedItem) { writeViewToItem(); renderSequence(); }
  }

  function renderOverlays(tiles, main) {
    const layer = $('#stage-overlays');
    layer.innerHTML = '';
    const mt = tiles.find(t => t.camera === main) || tiles[0];
    if (!mt || !state.event) return;
    if (state.view.show_timestamp) {
      const c = document.createElement('div');
      c.id = 'ov-clock'; c.className = 'ov-clock';
      c.style.left = `calc(${mt.x * 100}% + 1.2%)`; c.style.top = `calc(${mt.y * 100}% + 1.5%)`;
      c.textContent = fmtClock(player.epochAt(player.time));
      layer.appendChild(c);
      if (state.view.show_location) {
        const parts = [state.event.city, state.event.reason_label].filter(Boolean);
        if (parts.length) {
          const l = document.createElement('div');
          l.className = 'ov-loc';
          l.style.left = `calc(${mt.x * 100}% + 1.2%)`; l.style.top = `calc(${mt.y * 100}% + 1.5% + 2.2em)`;
          l.textContent = parts.join(' · ');
          layer.appendChild(l);
        }
      }
    }
  }

  function syncViewControls(cams, main) {
    $$('#camera-checks input').forEach(i => {
      const has = !state.event || state.event.cameras.includes(i.value);
      i.checked = state.view.cameras.includes(i.value);
      i.disabled = !has;
      i.closest('label').classList.toggle('off', !has);
    });
    $$('#layout-buttons button').forEach(b => b.classList.toggle('active', b.dataset.layout === state.view.layout));
    $$('#aspect-buttons button').forEach(b => b.classList.toggle('active', b.dataset.aspect === state.aspect));
    const sel = $('#main-camera');
    sel.innerHTML = cams.map(c => `<option value="${c}" ${c === main ? 'selected' : ''}>${camLabel(c)}</option>`).join('');
    $('#fit-select').value = state.view.fit;
    $('#mirror-toggle').checked = state.view.mirror_rear;
    $('#speed-select').value = String(state.view.speed);
    $('#auto-cycle').checked = state.view.cycle_enabled;
    $('#cycle-interval').value = state.view.cycle_interval;
    $('#ov-timestamp').checked = state.view.show_timestamp;
    $('#ov-labels').checked = state.view.show_labels;
    $('#ov-location').checked = state.view.show_location;
    $('#export-aspect').value = state.aspect;
    updateExportSize();
  }

  function setMain(cam) {
    const cams = effectiveCameras();
    if (!cams.includes(cam)) {
      if (state.event && state.event.cameras.includes(cam)) { state.view.cameras.push(cam); } else return;
    }
    state.view.main_camera = cam;
    stageToast(camLabel(cam));
    applyView();
  }
  function cycleMain() {
    const cams = effectiveCameras();
    const pool = (state.view.cycle_cameras || []).filter(c => cams.includes(c));
    const list = pool.length > 1 ? pool : cams;
    if (list.length < 2) return;
    const i = list.indexOf(effectiveMain(cams));
    setMain(list[(i + 1) % list.length]);
  }
  function startCycleTimer() {
    stopCycleTimer();
    if (!state.view.cycle_enabled) return;
    const ms = Math.max(300, state.view.cycle_interval * 1000 / Math.max(0.1, state.view.speed));
    state.cycleTimer = setInterval(() => { if (player.playing) cycleMain(); }, ms);
  }
  function stopCycleTimer() { clearInterval(state.cycleTimer); state.cycleTimer = null; }

  /* ---------------- library ---------------- */
  async function openRoot(path) {
    if (!path) return toast('Enter a folder path first', true);
    $('#library-summary').textContent = 'Scanning…';
    try {
      const data = await post('/api/library/scan', { root: path });
      state.events = data.events;
      $('#root-input').value = data.root;
      renderLibrary();
      toast(`Found ${data.events.length} events`);
      if (data.events.length && !state.event) selectEvent(data.events[0].id);
    } catch (e) {
      $('#library-summary').textContent = 'Could not open folder';
      toast(e.message, true);
    }
  }

  function renderLibrary() {
    const list = $('#event-list');
    const q = state.search.toLowerCase();
    const events = state.events.filter(e => (state.kind === 'all' || e.kind === state.kind) &&
      (!q || `${e.title} ${e.city || ''} ${e.reason_label || ''} ${e.start}`.toLowerCase().includes(q)));
    const total = events.reduce((a, e) => a + e.size_bytes, 0);
    $('#library-summary').textContent = `${events.length} events · ${fmtBytes(total)}`;
    list.innerHTML = '';
    let lastDay = '';
    for (const e of events) {
      const day = e.start.slice(0, 10);
      if (day !== lastDay) {
        lastDay = day;
        const h = document.createElement('div'); h.className = 'day-head';
        h.textContent = new Date(e.start_epoch * 1000).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
        list.appendChild(h);
      }
      const card = document.createElement('div');
      card.className = 'event-card' + (state.event && state.event.id === e.id ? ' active' : '');
      card.dataset.id = e.id;
      const kindCls = e.kind === 'SentryClips' ? 'sentry' : e.kind === 'SavedClips' ? 'saved' : 'recent';
      const kindName = e.kind === 'SentryClips' ? 'Sentry' : e.kind === 'SavedClips' ? 'Saved' : 'Recent';
      card.innerHTML = `<img loading="lazy" src="/api/events/${e.id}/thumb" alt="">
        <div><div class="ttl">${e.title.replace(/^\w+ /, '')}</div>
        <div class="meta"><span class="badge ${kindCls}">${kindName}</span>${e.reason_label ? e.reason_label : ''}</div>
        <div class="meta">${e.city ? e.city + ' · ' : ''}${e.segment_count} min · ${e.cameras.length} cams</div></div>`;
      card.addEventListener('click', () => selectEvent(e.id));
      list.appendChild(card);
    }
  }

  async function selectEvent(id, opts = {}) {
    if (state.event && state.event.id === id && !opts.force) return state.event;
    let ev;
    try { ev = await api(`/api/events/${id}`); } catch (e) { toast(e.message, true); return null; }
    state.event = ev;
    if (!opts.keepSelection) { state.selectedItem = null; state.inPoint = null; state.outPoint = null; }
    $('#stage').dataset.empty = '0';
    player.load(ev);
    renderTimeline();
    renderInfo();
    renderLibrary();
    renderInOut();
    renderClipEditor();
    await applyView();
    if (opts.seek != null) player.seek(opts.seek);
    else if (ev.trigger_offset != null && ev.kind !== 'RecentClips') player.seek(Math.max(0, ev.trigger_offset - 10));
    return ev;
  }

  function renderTimeline() {
    const ev = state.event;
    const segs = $('#tl-segments');
    segs.innerHTML = '';
    let acc = 0;
    ev.segments.forEach((s, i) => {
      const d = document.createElement('div');
      d.className = 'tl-seg';
      d.style.left = (acc / ev.duration * 100) + '%';
      const t = new Date(s.start_epoch * 1000);
      d.innerHTML = `<span>${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}</span>`;
      segs.appendChild(d);
      acc += s.duration;
    });
    const trig = $('#tl-trigger');
    if (ev.trigger_offset != null && ev.kind !== 'RecentClips') {
      trig.hidden = false; trig.style.left = (ev.trigger_offset / ev.duration * 100) + '%';
      trig.title = `Event trigger: ${ev.reason_label || ''} ${fmtClock(ev.trigger_epoch)}`;
    } else trig.hidden = true;
    updateTimeUI(0);
  }

  function renderInfo() {
    const ev = state.event;
    const info = $('#event-info');
    if (!ev) { info.textContent = 'Select an event.'; return; }
    const rows = [
      ['Type', ev.kind.replace('Clips', ' clips')],
      ['Start', fmtClock(ev.start_epoch)],
      ['Duration', `${fmtTime(ev.duration, false)} (${ev.segment_count} segments)`],
      ['Cameras', ev.cameras.map(camLabel).join(', ')],
      ev.reason_label ? ['Reason', `${ev.reason_label}${ev.trigger_camera ? ' · ' + camLabel(ev.trigger_camera) : ''}`] : null,
      ev.trigger_epoch ? ['Trigger', fmtClock(ev.trigger_epoch)] : null,
      ev.city ? ['City', ev.city] : null,
      ev.lat != null ? ['Location', `${ev.lat.toFixed(5)}, ${ev.lon.toFixed(5)} · <a href="https://www.google.com/maps?q=${ev.lat},${ev.lon}" target="_blank" rel="noopener">Google Maps</a>`] : null,
      ['Size', fmtBytes(ev.size_bytes)],
      ['Folder', `<span class="mono small">${ev.folder}</span>`],
    ].filter(Boolean);
    info.innerHTML = '<dl>' + rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('') + '</dl>';
    $('#event-actions').hidden = false;
    const mapEl = $('#map');
    if (ev.lat != null && window.L) {
      mapEl.hidden = false;
      if (!state.map) {
        state.map = L.map(mapEl, { zoomControl: false, attributionControl: false });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(state.map);
        state.marker = L.marker([ev.lat, ev.lon]).addTo(state.map);
      }
      state.marker.setLatLng([ev.lat, ev.lon]);
      setTimeout(() => { state.map.invalidateSize(); state.map.setView([ev.lat, ev.lon], 15); }, 50);
    } else mapEl.hidden = true;
  }

  /* ---------------- timeline interaction ---------------- */
  (() => {
    const track = $('.tl-track');
    let dragging = false;
    const seekFromEvent = (e) => {
      if (!state.event) return;
      const r = track.getBoundingClientRect();
      const frac = clamp((e.clientX - r.left) / r.width, 0, 1);
      player.seek(frac * state.event.duration);
    };
    track.addEventListener('pointerdown', (e) => { dragging = true; track.setPointerCapture(e.pointerId); seekFromEvent(e); });
    track.addEventListener('pointermove', (e) => { if (dragging) seekFromEvent(e); });
    track.addEventListener('pointerup', () => { dragging = false; });
  })();

  function renderInOut() {
    const ev = state.event;
    const has = ev && (state.inPoint != null || state.outPoint != null);
    const inT = state.inPoint != null ? state.inPoint : 0;
    const outT = state.outPoint != null ? state.outPoint : (ev ? ev.duration : 0);
    $('#tl-in').hidden = !has || state.inPoint == null;
    $('#tl-out').hidden = !has || state.outPoint == null;
    $('#tl-range').style.display = has ? 'block' : 'none';
    if (ev) {
      $('#tl-in').style.left = (inT / ev.duration * 100) + '%';
      $('#tl-out').style.left = (outT / ev.duration * 100) + '%';
      $('#tl-range').style.left = (inT / ev.duration * 100) + '%';
      $('#tl-range').style.width = ((outT - inT) / ev.duration * 100) + '%';
    }
    $('#inout-display').textContent = has ? `${fmtTime(inT)} → ${fmtTime(outT)} (${fmtTime(outT - inT)})` : 'Whole event';
    if (state.selectedItem) { const it = currentItem(); if (it) { it.in_point = inT; it.out_point = outT; renderSequence(); renderClipEditor(); } }
  }
  function setIn() { if (!state.event) return; state.inPoint = player.time; if (state.outPoint != null && state.outPoint <= state.inPoint) state.outPoint = null; renderInOut(); stageToast('In point set'); }
  function setOut() { if (!state.event) return; state.outPoint = player.time; if (state.inPoint != null && state.inPoint >= state.outPoint) state.inPoint = null; renderInOut(); stageToast('Out point set'); }

  /* ---------------- sequence ---------------- */
  const currentItem = () => state.project.items.find(i => i.id === state.selectedItem) || null;

  function viewSnapshot() {
    const cams = effectiveCameras();
    return {
      cameras: cams.slice(), layout: state.view.layout, main_camera: effectiveMain(cams), fit: state.view.fit,
      speed: state.view.speed, cycle_enabled: state.view.cycle_enabled, cycle_interval: state.view.cycle_interval,
      cycle_cameras: state.view.cycle_cameras.slice(), mirror_rear: state.view.mirror_rear,
      show_timestamp: state.view.show_timestamp, show_labels: state.view.show_labels, show_location: state.view.show_location,
      blur_regions: state.view.blur_regions.map(r => ({ ...r })),
    };
  }
  function writeViewToItem() {
    const it = currentItem();
    if (it) Object.assign(it, viewSnapshot());
  }
  function loadViewFromItem(it) {
    state.view = Object.assign(defaultView(), {
      cameras: it.cameras.slice(), layout: it.layout, main_camera: it.main_camera, fit: it.fit, speed: it.speed,
      cycle_enabled: it.cycle_enabled, cycle_interval: it.cycle_interval, cycle_cameras: (it.cycle_cameras || []).slice(),
      mirror_rear: it.mirror_rear, show_timestamp: it.show_timestamp, show_labels: it.show_labels, show_location: it.show_location,
      blur_regions: (it.blur_regions || []).map(r => ({ ...r })),
    });
  }

  function addClip() {
    if (!state.event) return toast('Select an event first', true);
    const ev = state.event;
    const item = Object.assign({ id: uid(), event_id: ev.id, in_point: state.inPoint != null ? state.inPoint : 0, out_point: state.outPoint != null ? state.outPoint : ev.duration }, viewSnapshot());
    if (item.out_point - item.in_point < 0.1) return toast('The in/out range is empty', true);
    state.project.items.push(item);
    state.selectedItem = item.id;
    renderSequence(); renderClipEditor();
    toast('Clip added to sequence');
  }

  function itemDuration(it) { return Math.max(0, it.out_point - it.in_point) / (it.speed || 1); }
  function eventOf(it) { return state.events.find(e => e.id === it.event_id); }

  function renderSequence() {
    const box = $('#sequence');
    const items = state.project.items;
    const total = items.reduce((a, i) => a + itemDuration(i), 0);
    $('#sequence-total').textContent = `${items.length} clip${items.length === 1 ? '' : 's'} · ${fmtTime(total, false)}`;
    if (!items.length) {
      box.innerHTML = '<div class="muted small pad">No clips yet. Set In/Out on the timeline and press <b>Add to sequence</b>. Clips from different events (and days) can be combined.</div>';
      return;
    }
    box.innerHTML = '';
    items.forEach((it, idx) => {
      const ev = eventOf(it);
      const el = document.createElement('div');
      el.className = 'clip' + (it.id === state.selectedItem ? ' active' : '') + (state.seq && state.seq.i === idx ? ' playing' : '');
      el.draggable = true;
      el.dataset.id = it.id;
      const lay = (state.config ? state.config.layouts[it.layout] : it.layout).split(' (')[0];
      el.innerHTML = `<span class="idx">${idx + 1}</span>
        <img src="/api/events/${it.event_id}/thumb?t=${it.in_point.toFixed(1)}&camera=${it.main_camera}" alt="">
        <div><div class="ttl">${ev ? ev.title.replace(/^\w+ /, '') : 'Missing event'}</div>
        <div class="meta">${fmtTime(it.in_point)}–${fmtTime(it.out_point)} · ${fmtTime(itemDuration(it))}</div>
        <div class="meta">${it.cameras.length} cam · ${lay}${it.speed !== 1 ? ' · ' + it.speed + '×' : ''}${it.cycle_enabled ? ' · cycle' : ''}</div></div>
        <div class="tools"><button data-act="left" title="Move left">&larr;</button><button data-act="right" title="Move right">&rarr;</button><button data-act="dup" title="Duplicate">⧉</button><button data-act="del" title="Remove">✕</button></div>`;
      el.addEventListener('click', (e) => {
        const act = e.target.dataset.act;
        if (act) { e.stopPropagation(); itemAction(it.id, act); return; }
        selectItem(it.id);
      });
      el.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', it.id); el.classList.add('dragging'); });
      el.addEventListener('dragend', () => el.classList.remove('dragging'));
      el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('drop-before'); });
      el.addEventListener('dragleave', () => el.classList.remove('drop-before'));
      el.addEventListener('drop', (e) => {
        e.preventDefault(); el.classList.remove('drop-before');
        const from = items.findIndex(x => x.id === e.dataTransfer.getData('text/plain'));
        const to = items.findIndex(x => x.id === it.id);
        if (from < 0 || from === to) return;
        const [moved] = items.splice(from, 1);
        items.splice(to > from ? to - 1 : to, 0, moved);
        renderSequence();
      });
      box.appendChild(el);
    });
  }

  function itemAction(id, act) {
    const items = state.project.items;
    const i = items.findIndex(x => x.id === id);
    if (i < 0) return;
    if (act === 'left' && i > 0) [items[i - 1], items[i]] = [items[i], items[i - 1]];
    if (act === 'right' && i < items.length - 1) [items[i + 1], items[i]] = [items[i], items[i + 1]];
    if (act === 'dup') { const copy = Object.assign(JSON.parse(JSON.stringify(items[i])), { id: uid() }); items.splice(i + 1, 0, copy); }
    if (act === 'del') { items.splice(i, 1); if (state.selectedItem === id) { state.selectedItem = null; renderClipEditor(); } }
    renderSequence();
  }

  async function selectItem(id, opts = {}) {
    const it = state.project.items.find(x => x.id === id);
    if (!it) return;
    state.selectedItem = id;
    loadViewFromItem(it);
    state.inPoint = it.in_point; state.outPoint = it.out_point;
    if (!state.event || state.event.id !== it.event_id) {
      await selectEvent(it.event_id, { keepSelection: true, seek: it.in_point });
    }
    renderInOut();
    if (!opts.noSeek) player.seek(it.in_point);
    await applyView();
    renderSequence(); renderClipEditor();
    if (!opts.keepTab) activateTab('clip');
  }

  function renderClipEditor() {
    const it = currentItem();
    $('#clip-none').hidden = !!it;
    $('#clip-editor').hidden = !it;
    if (!it) return;
    const ev = eventOf(it);
    $('#clip-title').textContent = `Clip ${state.project.items.indexOf(it) + 1}: ${ev ? ev.title : ''}`;
    $('#clip-in').value = it.in_point.toFixed(1);
    $('#clip-out').value = it.out_point.toFixed(1);
    $('#clip-speed').value = String(it.speed);
    $('#clip-duration').textContent = `Source ${fmtTime(it.out_point - it.in_point)} → output ${fmtTime(itemDuration(it))}${it.blur_regions.length ? ` · ${it.blur_regions.length} blur region(s)` : ''}`;
  }

  /* ---- sequence preview ---- */
  async function playSequence() {
    if (!state.project.items.length) return toast('The sequence is empty', true);
    state.seq = { i: -1, elapsed: 0 };
    $('#btn-play-seq').textContent = '■ Stop preview';
    nextSeqItem();
  }
  function stopSequence() {
    state.seq = null;
    player.stopAt = null;
    player.pause();
    const audio = $('#music-audio');
    audio.pause();
    $('#btn-play-seq').innerHTML = '&#9654; Preview sequence';
    renderSequence();
  }
  async function nextSeqItem() {
    if (!state.seq) return;
    const prev = state.project.items[state.seq.i];
    if (prev) state.seq.elapsed += itemDuration(prev);
    state.seq.i += 1;
    const it = state.project.items[state.seq.i];
    if (!it) { stopSequence(); toast('Sequence preview finished'); return; }
    await selectItem(it.id, { noSeek: true, keepTab: true });
    if (!state.seq) return;
    player.setRate(it.speed);
    syncMusicPreview(state.seq.elapsed);
    player.playRange(it.in_point, it.out_point);
    renderSequence();
  }
  function syncMusicPreview(elapsed) {
    const m = state.project.music, audio = $('#music-audio');
    if (!m || !state.musicUrl || !$('#music-preview').checked) { audio.pause(); return; }
    if (audio.src !== location.origin + state.musicUrl && audio.getAttribute('src') !== state.musicUrl) audio.src = state.musicUrl;
    audio.volume = clamp(m.volume, 0, 1);
    audio.loop = m.loop;
    const start = elapsed - (m.video_offset || 0);
    if (start < 0) { audio.pause(); setTimeout(() => { if (state.seq) { audio.currentTime = m.offset || 0; audio.play().catch(() => {}); } }, -start * 1000); return; }
    const seekTo = (m.offset || 0) + start;
    const apply = () => { try { audio.currentTime = m.loop && audio.duration ? (m.offset || 0) + (start % Math.max(0.01, audio.duration - (m.offset || 0))) : seekTo; } catch (e) { /* ignore */ } audio.play().catch(() => {}); };
    if (audio.readyState >= 1) apply(); else audio.addEventListener('loadedmetadata', apply, { once: true });
  }

  /* ---------------- blur regions ---------------- */
  function renderBlurBoxes() {
    const layer = $('#blur-layer');
    layer.innerHTML = '';
    state.view.blur_regions.forEach((r, i) => {
      const b = document.createElement('div');
      b.className = 'blur-box';
      b.style.left = (r.x * 100) + '%'; b.style.top = (r.y * 100) + '%'; b.style.width = (r.w * 100) + '%'; b.style.height = (r.h * 100) + '%';
      const x = document.createElement('button'); x.textContent = '×'; x.title = 'Remove blur region';
      x.addEventListener('click', (e) => { e.stopPropagation(); state.view.blur_regions.splice(i, 1); renderBlurBoxes(); writeViewToItem(); renderClipEditor(); });
      b.appendChild(x);
      layer.appendChild(b);
    });
  }
  (() => {
    const stage = $('#stage');
    let start = null, rect = null;
    const norm = (e) => { const r = stage.getBoundingClientRect(); return [clamp((e.clientX - r.left) / r.width, 0, 1), clamp((e.clientY - r.top) / r.height, 0, 1)]; };
    stage.addEventListener('pointerdown', (e) => {
      if (!state.drawing) return;
      start = norm(e); rect = document.createElement('div'); rect.className = 'draw-rect'; stage.appendChild(rect); stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener('pointermove', (e) => {
      if (!state.drawing || !start) return;
      const [x, y] = norm(e);
      const l = Math.min(x, start[0]), t = Math.min(y, start[1]);
      rect.style.left = l * 100 + '%'; rect.style.top = t * 100 + '%'; rect.style.width = Math.abs(x - start[0]) * 100 + '%'; rect.style.height = Math.abs(y - start[1]) * 100 + '%';
    });
    stage.addEventListener('pointerup', (e) => {
      if (!state.drawing || !start) return;
      const [x, y] = norm(e);
      const region = { x: Math.min(x, start[0]), y: Math.min(y, start[1]), w: Math.abs(x - start[0]), h: Math.abs(y - start[1]) };
      rect.remove(); rect = null; start = null;
      state.drawing = false; stage.classList.remove('drawing');
      if (region.w > 0.005 && region.h > 0.005) {
        state.view.blur_regions.push(region);
        renderBlurBoxes(); writeViewToItem(); renderClipEditor(); renderSequence();
        toast('Blur region added');
      }
    });
  })();

  /* ---------------- music ---------------- */
  function setMusic(info) {
    if (!info) {
      state.project.music = null; state.musicUrl = null;
      $('#music-info').textContent = 'No music. The export is silent unless you add a track (TeslaCam clips have no audio).';
      $('#music-controls').hidden = true;
      return;
    }
    state.project.music = Object.assign({ path: info.path, name: info.name, offset: 0, volume: 1, fade_in: 1, fade_out: 2, loop: true, video_offset: 0 }, state.project.music || {}, { path: info.path, name: info.name });
    state.musicUrl = info.url;
    $('#music-info').textContent = `${info.name}${info.duration ? ' · ' + fmtTime(info.duration, false) : ''}`;
    $('#music-controls').hidden = false;
    const m = state.project.music;
    $('#music-offset').value = m.offset; $('#music-video-offset').value = m.video_offset; $('#music-volume').value = m.volume;
    $('#music-volume-val').textContent = Math.round(m.volume * 100) + '%';
    $('#music-fade-in').value = m.fade_in; $('#music-fade-out').value = m.fade_out; $('#music-loop').checked = m.loop;
  }
  async function uploadFile(kind, file) {
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch(`/api/upload/${kind}`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
    return res.json();
  }
  $('#music-file').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { setMusic(await uploadFile('music', f)); toast('Music added'); } catch (err) { toast(err.message, true); }
    e.target.value = '';
  });
  $('#music-path-btn').addEventListener('click', async () => {
    const p = await promptDialog('Path to an audio file on this PC', '');
    if (!p) return;
    try { setMusic(await post('/api/localfile', { path: p })); } catch (err) { toast(err.message, true); }
  });
  $('#music-remove').addEventListener('click', () => setMusic(null));
  const bindMusic = (id, key, parse = parseFloat) => $(id).addEventListener('input', (e) => { if (state.project.music) state.project.music[key] = parse(e.target.value); });
  bindMusic('#music-offset', 'offset'); bindMusic('#music-video-offset', 'video_offset'); bindMusic('#music-fade-in', 'fade_in'); bindMusic('#music-fade-out', 'fade_out');
  $('#music-volume').addEventListener('input', (e) => { if (state.project.music) state.project.music.volume = parseFloat(e.target.value); $('#music-volume-val').textContent = Math.round(e.target.value * 100) + '%'; $('#music-audio').volume = clamp(e.target.value, 0, 1); });
  $('#music-loop').addEventListener('change', (e) => { if (state.project.music) state.project.music.loop = e.target.checked; });

  /* ---------------- export ---------------- */
  function updateExportSize() {
    const [w, h] = canvasSize(state.aspect, parseInt($('#export-resolution').value, 10));
    $('#export-size').textContent = `${w} × ${h} px`;
  }
  function collectProject() {
    writeViewToItem();
    const ex = state.project.export;
    ex.aspect = state.aspect;
    ex.resolution = parseInt($('#export-resolution').value, 10);
    ex.fps = parseInt($('#export-fps').value, 10);
    ex.quality = $('#export-quality').value;
    ex.format = $('#export-format').value;
    ex.encoder = $('#export-encoder').value;
    ex.background = $('#export-bg').value;
    ex.watermark_position = $('#watermark-pos').value;
    ex.watermark_scale = parseFloat($('#watermark-scale').value);
    ex.watermark_opacity = parseFloat($('#watermark-opacity').value);
    ex.output_dir = $('#export-dir').value.trim() || null;
    ex.filename = $('#export-name').value.trim() || null;
    return { name: $('#project-name').value.trim() || 'Untitled', library_root: state.config && state.config.library_root, items: state.project.items, music: state.project.music, export: ex };
  }
  async function startExport() {
    if (!state.project.items.length) {
      if (!state.event) return toast('Nothing to export', true);
      addClip();
    }
    const project = collectProject();
    $('#export-error').hidden = true; $('#export-result').hidden = true;
    try {
      const { job_id } = await post('/api/export', { project });
      state.exportJob = job_id;
      $('#export-status').hidden = false; $('#btn-export').disabled = true; $('#btn-export-top').disabled = true;
      activateTab('export');
      pollJob(job_id);
    } catch (e) { $('#export-error').textContent = e.message; $('#export-error').hidden = false; toast(e.message, true); }
  }
  async function pollJob(id) {
    try {
      const job = await api(`/api/jobs/${id}`);
      $('#export-bar').style.width = (job.progress * 100).toFixed(1) + '%';
      $('#export-msg').textContent = `${job.message} · ${(job.progress * 100).toFixed(0)}%`;
      if (job.state === 'running' || job.state === 'queued') { setTimeout(() => pollJob(id), 500); return; }
      $('#export-status').hidden = true; $('#btn-export').disabled = false; $('#btn-export-top').disabled = false;
      if (job.state === 'done') {
        $('#export-result').hidden = false; $('#export-path').textContent = job.output;
        const v = $('#export-preview'); v.hidden = true; v.removeAttribute('src');
        state.lastOutput = job.output;
        toast('Export finished');
      } else if (job.state === 'error') { $('#export-error').textContent = job.error || 'Export failed'; $('#export-error').hidden = false; toast('Export failed', true); }
      else toast('Export cancelled');
    } catch (e) { $('#export-status').hidden = true; $('#btn-export').disabled = false; $('#btn-export-top').disabled = false; toast(e.message, true); }
  }
  $('#export-cancel').addEventListener('click', () => { if (state.exportJob) post(`/api/jobs/${state.exportJob}/cancel`, {}); });
  $('#export-reveal').addEventListener('click', () => post('/api/reveal', { path: state.lastOutput }).catch(e => toast(e.message, true)));
  $('#export-preview-btn').addEventListener('click', () => {
    const v = $('#export-preview');
    if (state.lastOutput.endsWith('.gif')) { window.open(`/api/output?path=${encodeURIComponent(state.lastOutput)}`, '_blank'); return; }
    v.src = `/api/output?path=${encodeURIComponent(state.lastOutput)}`; v.hidden = false; v.play().catch(() => {});
  });
  $('#watermark-file').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { const info = await uploadFile('watermark', f); state.project.export.watermark_path = info.path; $('#watermark-info').textContent = info.name; } catch (err) { toast(err.message, true); }
    e.target.value = '';
  });
  $('#watermark-remove').addEventListener('click', () => { state.project.export.watermark_path = null; $('#watermark-info').textContent = 'None'; });
  $('#export-resolution').addEventListener('change', updateExportSize);
  $('#export-aspect').addEventListener('change', (e) => setAspect(e.target.value));
  $('#export-format').addEventListener('change', (e) => { if (e.target.value === 'gif') { $('#export-resolution').value = '480'; updateExportSize(); } });

  async function snapshot() {
    if (!state.event) return;
    const cams = effectiveCameras();
    const body = { event_id: state.event.id, time: player.time, cameras: cams, layout: state.view.layout, main_camera: effectiveMain(cams), aspect: state.aspect, resolution: parseInt($('#export-resolution').value, 10), fit: state.view.fit, mirror_rear: state.view.mirror_rear, show_timestamp: state.view.show_timestamp, output_dir: $('#export-dir').value.trim() || null };
    try { const r = await post('/api/still', body); toast(`Snapshot saved: ${r.output}`); state.lastOutput = r.output; } catch (e) { toast(e.message, true); }
  }

  /* ---------------- projects ---------------- */
  async function refreshProjects() {
    try {
      const list = await api('/api/projects');
      const sel = $('#load-project');
      sel.innerHTML = '<option value="">Load…</option>' + list.map(p => `<option value="${p.name}">${p.name}</option>`).join('');
    } catch (e) { /* ignore */ }
  }
  async function saveProject() {
    const name = $('#project-name').value.trim() || 'Untitled';
    try { await api(`/api/projects/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(collectProject()) }); toast(`Project "${name}" saved`); refreshProjects(); } catch (e) { toast(e.message, true); }
  }
  async function loadProject(name) {
    try {
      const p = await api(`/api/projects/${encodeURIComponent(name)}`);
      state.project.items = p.items; state.project.export = Object.assign(state.project.export, p.export);
      $('#project-name').value = p.name;
      setAspect(p.export.aspect, true);
      $('#export-resolution').value = String(p.export.resolution); $('#export-fps').value = String(p.export.fps); $('#export-quality').value = p.export.quality; $('#export-format').value = p.export.format;
      $('#export-bg').value = p.export.background || '#000000'; $('#export-dir').value = p.export.output_dir || $('#export-dir').value; $('#export-name').value = p.export.filename || '';
      if (p.music) { state.project.music = p.music; setMusic({ path: p.music.path, name: p.music.name || p.music.path.split(/[\\/]/).pop(), url: `/api/output?path=${encodeURIComponent(p.music.path)}` }); post('/api/localfile', { path: p.music.path }).catch(() => {}); } else setMusic(null);
      if (p.library_root && (!state.config.library_root || state.config.library_root !== p.library_root) && !state.events.length) await openRoot(p.library_root);
      state.selectedItem = null;
      renderSequence(); renderClipEditor();
      if (p.items.length) selectItem(p.items[0].id);
      toast(`Project "${p.name}" loaded`);
    } catch (e) { toast(e.message, true); }
  }

  /* ---------------- folder browser ---------------- */
  let browsePath = null;
  async function browseTo(path) {
    try {
      const data = await api(`/api/browse${path ? '?path=' + encodeURIComponent(path) : ''}`);
      browsePath = data.path;
      $('#browse-path').textContent = data.path || 'Drives';
      $('#browse-up').disabled = !data.parent && !data.path;
      $('#browse-up').dataset.parent = data.parent || '';
      $('#browse-hint').textContent = data.is_teslacam ? 'This looks like a TeslaCam folder.' : '';
      $('#browse-use').disabled = !data.path;
      const list = $('#browse-list');
      list.innerHTML = '';
      for (const d of data.dirs) {
        const row = document.createElement('div');
        const tc = ['TeslaCam', 'SavedClips', 'SentryClips', 'RecentClips'].includes(d.name);
        row.className = tc ? 'tc' : '';
        row.innerHTML = `<span>${tc ? '🎥' : '📁'}</span><span>${d.name}</span>`;
        row.addEventListener('click', () => browseTo(d.path));
        list.appendChild(row);
      }
    } catch (e) { toast(e.message, true); }
  }
  $('#browse-btn').addEventListener('click', () => { openModal('#modal-browse'); browseTo($('#root-input').value.trim() || null); });
  $('#browse-up').addEventListener('click', () => browseTo($('#browse-up').dataset.parent || null));
  $('#browse-use').addEventListener('click', () => { closeModals(); if (browsePath) { $('#root-input').value = browsePath; openRoot(browsePath); } });

  /* ---------------- inspector wiring ---------------- */
  function activateTab(name) {
    $$('#inspector-tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    $$('#inspector .tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    if (name === 'info' && state.map) setTimeout(() => state.map.invalidateSize(), 30);
  }
  $$('#inspector-tabs button').forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));

  function setAspect(aspect, quiet) {
    state.aspect = aspect;
    state.project.export.aspect = aspect;
    fitStage();
    if (!quiet) applyView(); else syncViewControls(effectiveCameras(), effectiveMain(effectiveCameras()));
    buildLayoutIcons();
  }

  function layoutIcon(tiles) {
    const rects = tiles.map(t => `<rect x="${(t.x * 40).toFixed(1)}" y="${(t.y * 26).toFixed(1)}" width="${(t.w * 40).toFixed(1)}" height="${(t.h * 26).toFixed(1)}"/>`).join('');
    return `<svg viewBox="0 0 40 26">${rects}</svg>`;
  }
  async function buildLayoutIcons() {
    const box = $('#layout-buttons');
    const cams = ['front', 'back', 'left_repeater', 'right_repeater'];
    const [a, b] = aspectWH(state.aspect);
    for (const [name, label] of Object.entries(state.config.layouts)) {
      let btn = box.querySelector(`[data-layout="${name}"]`);
      if (!btn) {
        btn = document.createElement('button'); btn.dataset.layout = name; btn.title = label;
        btn.innerHTML = `<span class="ico"></span><span>${label.split(' (')[0]}</span>`;
        btn.addEventListener('click', () => { state.view.layout = name; applyView(); });
        box.appendChild(btn);
      }
      try {
        const data = await fetchLayout(name, cams, 'front', state.aspect);
        const svg = btn.querySelector('.ico');
        svg.innerHTML = layoutIcon(data.tiles);
        svg.querySelector('svg').setAttribute('viewBox', '0 0 40 26');
        svg.querySelector('svg').style.aspectRatio = `${a} / ${b}`;
      } catch (e) { /* ignore */ }
    }
  }

  function buildStaticControls() {
    const cfg = state.config;
    const cc = $('#camera-checks');
    cc.innerHTML = cfg.cameras.map(c => `<label class="chk"><input type="checkbox" value="${c}" checked> ${cfg.camera_labels[c]}</label>`).join('');
    cc.addEventListener('change', (e) => {
      const cams = $$('#camera-checks input:checked').map(i => i.value);
      if (!cams.length) { e.target.checked = true; return; }
      state.view.cameras = cams;
      applyView();
    });
    const ab = $('#aspect-buttons');
    ab.innerHTML = '';
    for (const asp of cfg.aspects) {
      const [a, b] = aspectWH(asp);
      const btn = document.createElement('button'); btn.dataset.aspect = asp;
      const w = a >= b ? 28 : 28 * a / b, h = a >= b ? 28 * b / a : 28;
      btn.innerHTML = `<span class="ar" style="width:${w}px;height:${h}px"></span><span>${asp}</span>`;
      btn.addEventListener('click', () => setAspect(asp));
      ab.appendChild(btn);
    }
    $('#export-aspect').innerHTML = cfg.aspects.map(a => `<option value="${a}">${a}</option>`).join('');
    $('#export-dir').value = cfg.output_dir || '';
    const dr = $('#detected-roots');
    const roots = [...new Set([...(cfg.detected_roots || []), ...(cfg.recent_roots || [])])];
    dr.innerHTML = '<option value="">Detected / recent…</option>' + roots.map(r => `<option value="${r}">${r}</option>`).join('');
    dr.addEventListener('change', (e) => { if (e.target.value) { $('#root-input').value = e.target.value; openRoot(e.target.value); e.target.value = ''; } });
    if (cfg.last_root) $('#root-input').value = cfg.last_root;
  }

  $('#main-camera').addEventListener('change', (e) => setMain(e.target.value));
  $('#fit-select').addEventListener('change', (e) => { state.view.fit = e.target.value; applyView(); });
  $('#mirror-toggle').addEventListener('change', (e) => { state.view.mirror_rear = e.target.checked; applyView(); });
  $('#speed-select').addEventListener('change', (e) => { state.view.speed = parseFloat(e.target.value); player.setRate(state.view.speed); startCycleTimer(); if (state.selectedItem) { writeViewToItem(); renderSequence(); renderClipEditor(); } });
  $('#auto-cycle').addEventListener('change', (e) => {
    state.view.cycle_enabled = e.target.checked;
    if (player.playing) startCycleTimer();
    stageToast(e.target.checked ? `Auto-cycle on: main camera changes every ${state.view.cycle_interval} s while playing` : 'Auto-cycle off');
    if (state.selectedItem) { writeViewToItem(); renderSequence(); }
  });
  $('#cycle-interval').addEventListener('change', (e) => { state.view.cycle_interval = Math.max(0.5, parseFloat(e.target.value) || 5); if (player.playing) startCycleTimer(); writeViewToItem(); });
  $('#btn-cycle').addEventListener('click', cycleMain);
  $('#ov-timestamp').addEventListener('change', (e) => { state.view.show_timestamp = e.target.checked; applyView(); });
  $('#ov-labels').addEventListener('change', (e) => { state.view.show_labels = e.target.checked; applyView(); });
  $('#ov-location').addEventListener('change', (e) => { state.view.show_location = e.target.checked; applyView(); });
  $('#cams-all').addEventListener('click', () => { state.view.cameras = state.event ? state.event.cameras.slice() : state.config.cameras.slice(); applyView(); });
  $('#cams-none').addEventListener('click', () => { state.view.cameras = ['front']; state.view.main_camera = 'front'; applyView(); });

  $('#clip-in').addEventListener('change', (e) => { const it = currentItem(); if (!it) return; it.in_point = clamp(parseFloat(e.target.value) || 0, 0, it.out_point - 0.1); state.inPoint = it.in_point; renderInOut(); });
  $('#clip-out').addEventListener('change', (e) => { const it = currentItem(); if (!it) return; it.out_point = clamp(parseFloat(e.target.value) || 0, it.in_point + 0.1, state.event ? state.event.duration : 1e9); state.outPoint = it.out_point; renderInOut(); });
  $('#clip-speed').addEventListener('change', (e) => { state.view.speed = parseFloat(e.target.value); player.setRate(state.view.speed); writeViewToItem(); renderSequence(); renderClipEditor(); syncViewControls(effectiveCameras(), effectiveMain(effectiveCameras())); });
  $('#btn-add-blur').addEventListener('click', () => { state.drawing = true; $('#stage').classList.add('drawing'); stageToast('Drag a rectangle to blur'); });
  $('#btn-clear-blur').addEventListener('click', () => { state.view.blur_regions = []; renderBlurBoxes(); writeViewToItem(); renderClipEditor(); });
  $('#clip-duplicate').addEventListener('click', () => { if (state.selectedItem) itemAction(state.selectedItem, 'dup'); });
  $('#clip-remove').addEventListener('click', () => { if (state.selectedItem) itemAction(state.selectedItem, 'del'); });
  $('#clip-split').addEventListener('click', () => {
    const it = currentItem(); if (!it) return;
    const t = player.time;
    if (t <= it.in_point + 0.1 || t >= it.out_point - 0.1) return toast('Move the playhead inside the clip to split it', true);
    const copy = Object.assign(JSON.parse(JSON.stringify(it)), { id: uid(), in_point: t });
    it.out_point = t;
    state.project.items.splice(state.project.items.indexOf(it) + 1, 0, copy);
    state.outPoint = t; renderInOut(); renderSequence(); renderClipEditor();
  });

  $('#btn-play').addEventListener('click', () => { if (state.seq) stopSequence(); else player.toggle(); });
  $('#btn-back').addEventListener('click', () => player.seek(player.time - 5));
  $('#btn-fwd').addEventListener('click', () => player.seek(player.time + 5));
  $('#btn-prev-seg').addEventListener('click', () => { const i = player._segIndex(player.time - 0.5); player.seek(player.segStarts[Math.max(0, i)]); });
  $('#btn-next-seg').addEventListener('click', () => { const i = player._segIndex(player.time); if (i + 1 < player.segStarts.length) player.seek(player.segStarts[i + 1]); });
  $('#btn-fullscreen').addEventListener('click', () => { const s = $('#stage'); if (document.fullscreenElement) document.exitFullscreen(); else s.requestFullscreen().catch(() => {}); });
  $('#btn-still').addEventListener('click', snapshot);
  $('#btn-set-in').addEventListener('click', setIn);
  $('#btn-set-out').addEventListener('click', setOut);
  $('#btn-clear-inout').addEventListener('click', () => { state.inPoint = null; state.outPoint = null; if (state.selectedItem) { const it = currentItem(); if (it) { it.in_point = 0; it.out_point = state.event.duration; } } renderInOut(); });
  $('#btn-add-clip').addEventListener('click', addClip);
  $('#btn-play-seq').addEventListener('click', () => { if (state.seq) stopSequence(); else playSequence(); });
  $('#btn-clear-seq').addEventListener('click', async () => { if (!state.project.items.length) return; if (await confirmDialog('Clear sequence', 'Remove all clips from the sequence?', 'Clear')) { state.project.items = []; state.selectedItem = null; renderSequence(); renderClipEditor(); } });
  $('#btn-export').addEventListener('click', startExport);
  $('#btn-export-top').addEventListener('click', () => { activateTab('export'); startExport(); });
  $('#open-btn').addEventListener('click', () => openRoot($('#root-input').value.trim()));
  $('#root-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') openRoot(e.target.value.trim()); });
  $('#save-project').addEventListener('click', saveProject);
  $('#load-project').addEventListener('change', (e) => { if (e.target.value) { loadProject(e.target.value); e.target.value = ''; } });
  $('#help-btn').addEventListener('click', () => openModal('#modal-help'));
  $$('#kind-filter button').forEach(b => b.addEventListener('click', () => { $$('#kind-filter button').forEach(x => x.classList.remove('active')); b.classList.add('active'); state.kind = b.dataset.kind; renderLibrary(); }));
  $('#library-search').addEventListener('input', (e) => { state.search = e.target.value; renderLibrary(); });
  $('#btn-reveal-event').addEventListener('click', () => state.event && post('/api/reveal', { path: state.event.folder }).catch(e => toast(e.message, true)));
  $('#btn-export-raw').addEventListener('click', async () => {
    if (!state.event) return;
    const btn = $('#btn-export-raw');
    btn.disabled = true; btn.textContent = 'Exporting…';
    try {
      const r = await post('/api/export_raw', { event_id: state.event.id, cameras: effectiveCameras(), output_dir: $('#export-dir').value.trim() || null });
      state.lastOutput = r.outputs[0];
      toast(`${r.outputs.length} file(s) written to ${r.outputs[0].replace(/[\\/][^\\/]*$/, '')}`);
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.textContent = 'Export original files';
  });
  $('#btn-delete-event').addEventListener('click', async () => {
    const ev = state.event; if (!ev) return;
    const ok = await confirmDialog('Delete event from drive', `Permanently delete <b>${ev.title}</b> (${ev.segment_count} min, ${fmtBytes(ev.size_bytes)}) from<br><span class="mono small">${ev.folder}</span>?<br><br>This cannot be undone.`);
    if (!ok) return;
    try {
      await api(`/api/events/${ev.id}`, { method: 'DELETE' });
      state.events = state.events.filter(e => e.id !== ev.id);
      state.project.items = state.project.items.filter(i => i.event_id !== ev.id);
      state.event = null; player.pause();
      $('#stage').dataset.empty = '1'; $('#tiles').innerHTML = '';
      renderLibrary(); renderSequence();
      toast('Event deleted');
      if (state.events.length) selectEvent(state.events[0].id);
    } catch (e) { toast(e.message, true); }
  });

  /* ---------------- keyboard ---------------- */
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'select' || tag === 'textarea') { if (e.key === 'Escape') e.target.blur(); return; }
    if (!$$('.modal').every(m => m.hidden)) { if (e.key === 'Escape') closeModals(); return; }
    const k = e.key;
    if (k === ' ' || k.toLowerCase() === 'k') { e.preventDefault(); if (state.seq) stopSequence(); else player.toggle(); }
    else if (k === 'ArrowLeft') player.seek(player.time - (e.shiftKey ? 5 : 1));
    else if (k === 'ArrowRight') player.seek(player.time + (e.shiftKey ? 5 : 1));
    else if (k.toLowerCase() === 'j') player.seek(player.time - 10);
    else if (k.toLowerCase() === 'l') player.seek(player.time + 10);
    else if (k === ',') player.step(-1);
    else if (k === '.') player.step(1);
    else if (k === '[') $('#btn-prev-seg').click();
    else if (k === ']') $('#btn-next-seg').click();
    else if (k === 'Home') player.seek(0);
    else if (k === 'End') player.seek(player.duration - 0.1);
    else if (k.toLowerCase() === 'i') setIn();
    else if (k.toLowerCase() === 'o') setOut();
    else if (k === 'Enter') addClip();
    else if (k.toLowerCase() === 'c') cycleMain();
    else if (k.toLowerCase() === 'm') { state.view.mirror_rear = !state.view.mirror_rear; applyView(); }
    else if (k.toLowerCase() === 'f') $('#btn-fullscreen').click();
    else if (k.toLowerCase() === 'g') { state.view.layout = 'grid'; applyView(); }
    else if (k.toLowerCase() === 'p') { state.view.layout = 'pip'; applyView(); }
    else if (k.toLowerCase() === 's') { state.view.layout = 'single'; applyView(); }
    else if (CAMERA_KEYS[k]) setMain(CAMERA_KEYS[k]);
    else if (k === 'Delete' && state.selectedItem) itemAction(state.selectedItem, 'del');
    else return;
    e.preventDefault();
  });

  /* ---------------- init ---------------- */
  async function init() {
    try { state.config = await api('/api/config'); } catch (e) { toast('Server not reachable: ' + e.message, true); return; }
    buildStaticControls();
    await buildLayoutIcons();
    syncViewControls(state.view.cameras, state.view.main_camera);
    fitStage();
    refreshProjects();
    api('/api/encoders').then(({ encoders, auto }) => {
      const sel = $('#export-encoder');
      const names = { libx264: 'CPU (libx264)', h264_nvenc: 'NVIDIA NVENC', h264_amf: 'AMD AMF', h264_qsv: 'Intel Quick Sync', h264_videotoolbox: 'Apple VideoToolbox' };
      sel.innerHTML = `<option value="auto">Auto (${names[auto] || auto})</option>` + Object.entries(encoders).filter(([, ok]) => ok).map(([k]) => `<option value="${k}">${names[k] || k}</option>`).join('');
    }).catch(() => {});
    if (state.config.library_root) { await openRoot(state.config.library_root); }
    else if (state.config.detected_roots && state.config.detected_roots.length === 1) { $('#root-input').value = state.config.detected_roots[0]; openRoot(state.config.detected_roots[0]); }
    renderSequence();
  }
  init();
})();
