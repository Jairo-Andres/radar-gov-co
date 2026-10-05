// Radar 3D en canvas 2D (sin WebGL): plano inclinado, una baliza por portal, barrido con
// brillo y "ping" cuando el haz pasa. Más alta la baliza cuanto más lejos está de 80.
// Es decorativo y complementario: los mismos datos están en la vista plana (SVG con
// marcas enfocables), en la tabla y en las fichas.

const TAU = Math.PI * 2;
const SWEEP_SPEED = TAU / 6000; // una vuelta cada 6 s, igual que la vista plana

function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function createRadar3D(canvas, { onSelect, onHover, reduceMotion }) {
  const ctx = canvas.getContext("2d");
  const state = {
    points: [], labels: [], tilt: 1, tiltTarget: 1, rot: 0, sweep: 0, last: 0,
    w: 0, h: 0, dpr: 1, drag: null, hover: -1, running: false, visible: true, frame: 0,
    dim: () => false,
  };
  const colors = {};

  function readColors() {
    colors.good = cssVar("--status-good", "#3FB950");
    colors.warn = cssVar("--status-warn-dot", "#E3B341");
    colors.bad = cssVar("--status-bad", "#FF7B5C");
    colors.route = cssVar("--route-q", "#E0569A");
    colors.routeInk = cssVar("--ink-q", "#FF7AAE");
    colors.ring = cssVar("--color-border-strong", "#6E767F");
    colors.text = cssVar("--color-fg-muted", "#A2A9B1");
    colors.disc = cssVar("--color-surface", "#1A1D21");
    colors.font = cssVar("--font-body", "Verdana, sans-serif");
  }

  function resize() {
    const box = canvas.getBoundingClientRect();
    state.dpr = Math.min(2, window.devicePixelRatio || 1);
    state.w = box.width;
    state.h = box.height;
    canvas.width = Math.round(box.width * state.dpr);
    canvas.height = Math.round(box.height * state.dpr);
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    requestDraw();
  }

  // Proyección: radio r (0..1), ángulo a (0 = arriba, horario), altura z (0..1).
  function project(r, a, z = 0) {
    const { w, h, tilt } = state;
    const radius = Math.min(w * 0.45, h * (0.62 - 0.2 * (1 - tilt)));
    const angle = a + state.rot - Math.PI / 2;
    const squash = 1 - 0.56 * tilt;
    return {
      x: w / 2 + Math.cos(angle) * r * radius,
      y: h * (0.5 + 0.1 * tilt) + Math.sin(angle) * r * radius * squash - z * tilt * h * 0.26,
    };
  }

  function colorFor(light) {
    return light === "verde" ? colors.good : light === "amarillo" ? colors.warn : colors.bad;
  }

  function path(points) {
    ctx.beginPath();
    points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  }

  function ring(r) {
    const pts = [];
    for (let i = 0; i <= 96; i++) pts.push(project(r, (i / 96) * TAU));
    return pts;
  }

  // Bueno = círculo, regular = triángulo, malo = cuadrado (regla de la identidad común).
  function shape(x, y, light, size) {
    ctx.beginPath();
    if (light === "amarillo") {
      ctx.moveTo(x, y - size * 1.2);
      ctx.lineTo(x + size * 1.1, y + size * 0.8);
      ctx.lineTo(x - size * 1.1, y + size * 0.8);
      ctx.closePath();
    } else if (light === "rojo") {
      ctx.rect(x - size * 0.9, y - size * 0.9, size * 1.8, size * 1.8);
    } else {
      ctx.arc(x, y, size, 0, TAU);
    }
    ctx.fill();
  }

  function draw(time) {
    state.frame = 0;
    const dt = state.last ? Math.min(50, time - state.last) : 16;
    state.last = time;
    state.tilt += (state.tiltTarget - state.tilt) * (reduceMotion ? 1 : 0.1);
    if (!reduceMotion) state.sweep = (state.sweep + dt * SWEEP_SPEED) % TAU;
    const { w, h } = state;
    ctx.clearRect(0, 0, w, h);
    if (!w || !h) return;

    // Disco, anillos (cada uno = 10 puntos) y sectores.
    path(ring(1));
    ctx.fillStyle = colors.disc;
    ctx.globalAlpha = 0.85;
    ctx.fill();
    ctx.globalAlpha = 1;
    [0.2, 0.4, 0.6, 0.8].forEach((r) => {
      path(ring(r));
      ctx.strokeStyle = colors.ring;
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      ctx.stroke();
    });
    path(ring(1));
    ctx.globalAlpha = 0.8;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.globalAlpha = 1;

    const sectors = state.labels.length || 5;
    const center = project(0, 0);
    ctx.font = `700 12px ${colors.font}`;
    ctx.textAlign = "center";
    for (let s = 0; s < sectors; s++) {
      const a = (s / sectors) * TAU;
      const edge = project(1, a);
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(edge.x, edge.y);
      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = colors.ring;
      ctx.globalAlpha = 0.35;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // Barrido con estela y brillo en el haz.
    if (!reduceMotion) {
      const trail = 0.9;
      const steps = 18;
      for (let k = 0; k < steps; k++) {
        const a0 = state.sweep - (trail * (k + 1)) / steps;
        const a1 = state.sweep - (trail * k) / steps;
        const pts = [center];
        for (let m = 0; m <= 6; m++) pts.push(project(1, a0 + ((a1 - a0) * m) / 6));
        path(pts);
        ctx.closePath();
        ctx.fillStyle = colors.route;
        ctx.globalAlpha = 0.3 * (1 - k / steps);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      const tip = project(1, state.sweep);
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(tip.x, tip.y);
      ctx.strokeStyle = colors.routeInk;
      ctx.lineWidth = 2;
      ctx.shadowColor = colors.route;
      ctx.shadowBlur = 14;
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Balizas, de atrás hacia adelante.
    const order = state.points
      .map((p, i) => ({ i, y: project(p.r, p.a).y }))
      .sort((a, b) => a.y - b.y);
    for (const { i } of order) {
      const p = state.points[i];
      const base = project(p.r, p.a);
      const top = project(p.r, p.a, p.height);
      const color = colorFor(p.light);
      const dim = state.dim(p.site);
      ctx.globalAlpha = dim ? 0.18 : 1;

      const behind = (((state.sweep - p.a) % TAU) + TAU) % TAU;
      if (!reduceMotion && !dim && behind < 0.06 && p.ping < 0) p.ping = 0;
      if (p.ping >= 0) {
        p.ping += dt / 900;
        if (p.ping > 1) p.ping = -1;
        else {
          ctx.beginPath();
          ctx.ellipse(base.x, base.y, 26 * p.ping, 26 * p.ping * (1 - 0.56 * state.tilt), 0, 0, TAU);
          ctx.strokeStyle = color;
          ctx.globalAlpha = 1 - p.ping;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.globalAlpha = dim ? 0.18 : 1;
        }
      }

      ctx.beginPath();
      ctx.ellipse(base.x, base.y, 4, 4 * (1 - 0.56 * state.tilt), 0, 0, TAU);
      ctx.fillStyle = "rgba(0,0,0,.5)";
      ctx.fill();
      if (state.tilt > 0.05 && p.height > 0) {
        const grad = ctx.createLinearGradient(0, base.y, 0, top.y);
        grad.addColorStop(0, "rgba(255,255,255,0)");
        grad.addColorStop(1, color);
        ctx.beginPath();
        ctx.moveTo(base.x, base.y);
        ctx.lineTo(top.x, top.y);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      const active = i === state.hover;
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = active ? 18 : 8;
      shape(top.x, top.y, p.light, active ? 7 : 5);
      ctx.shadowBlur = 0;
      if (active) {
        ctx.beginPath();
        ctx.arc(top.x, top.y, 13, 0, TAU);
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      p.sx = top.x;
      p.sy = top.y;
    }

    // Nombres de los sectores encima de todo, con borde oscuro para que se lean sobre las balizas.
    ctx.font = `700 12px ${colors.font}`;
    ctx.textAlign = "center";
    ctx.lineJoin = "round";
    for (let s = 0; s < sectors; s++) {
      const label = project(1.12, (s / sectors) * TAU + Math.PI / sectors);
      const x = Math.max(40, Math.min(w - 40, label.x));
      ctx.lineWidth = 4;
      ctx.strokeStyle = "rgba(11,13,16,.9)";
      ctx.strokeText(state.labels[s] || "", x, label.y + 4);
      ctx.fillStyle = colors.text;
      ctx.fillText(state.labels[s] || "", x, label.y + 4);
    }

    const settling = Math.abs(state.tiltTarget - state.tilt) > 0.002;
    if (state.running && state.visible && (!reduceMotion || settling)) requestDraw();
  }

  function requestDraw() {
    if (!state.frame) state.frame = requestAnimationFrame(draw);
  }

  function nearest(event) {
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    let best = -1;
    let bestDistance = 22;
    state.points.forEach((p, i) => {
      if (state.dim(p.site)) return;
      const d = Math.hypot((p.sx ?? -99) - x, (p.sy ?? -99) - y);
      if (d < bestDistance) { bestDistance = d; best = i; }
    });
    return { index: best, x, y };
  }

  canvas.addEventListener("pointerdown", (event) => {
    state.drag = { x: event.clientX, rot: state.rot, moved: false };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (state.drag) {
      const dx = event.clientX - state.drag.x;
      if (Math.abs(dx) > 4) state.drag.moved = true;
      state.rot = state.drag.rot + dx * 0.01;
      requestDraw();
      return;
    }
    const { index, x, y } = nearest(event);
    if (index !== state.hover) {
      state.hover = index;
      canvas.style.cursor = index >= 0 ? "pointer" : "grab";
      onHover?.(index >= 0 ? state.points[index].site : null, x, y);
      requestDraw();
    }
  });
  canvas.addEventListener("pointerleave", () => {
    state.hover = -1;
    onHover?.(null);
    requestDraw();
  });
  canvas.addEventListener("pointerup", (event) => {
    const drag = state.drag;
    state.drag = null;
    if (drag && !drag.moved) {
      const { index } = nearest(event);
      if (index >= 0) onSelect?.(state.points[index].site);
    }
    requestDraw();
  });

  // Pausa cuando no se ve (ahorra batería y CPU).
  const observer = new IntersectionObserver((entries) => {
    state.visible = entries.some((e) => e.isIntersecting);
    if (state.visible) requestDraw();
  });
  observer.observe(canvas);
  document.addEventListener("visibilitychange", () => {
    state.visible = !document.hidden;
    state.last = 0;
    if (state.visible) requestDraw();
  });
  new ResizeObserver(resize).observe(canvas);

  return {
    setData(entries, labels) {
      readColors();
      state.labels = labels;
      state.points = entries.map(({ site, angle }) => ({
        site,
        light: site.light,
        a: angle,
        r: Math.min(1, Math.max(0.06, (100 - site.overall) / 50)),
        // Más alta cuanto más lejos de 80 por debajo; los buenos quedan casi a ras del plano.
        height: Math.min(1, Math.max(0.03, (80 - site.overall) / 40)),
        ping: -1,
      }));
      resize();
    },
    setDim(fn) { state.dim = fn; requestDraw(); },
    start() { state.running = true; state.last = 0; requestDraw(); },
    stop() { state.running = false; },
    setTilt(value) { state.tiltTarget = value; if (reduceMotion) state.tilt = value; requestDraw(); },
  };
}
