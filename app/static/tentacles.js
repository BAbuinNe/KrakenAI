/*
 * KrakenAI animated tentacles.
 * Real-time canvas illustration, inspired by the Kraken chat concept video.
 * No network calls, video, WebGL, external dependencies, gradients or image assets.
 * Canvas remains behind the chat, and never catches pointer or keyboard events.
 */
(() => {
  'use strict';
  const canvas = document.getElementById('tentacleCanvas');
  const panel = document.getElementById('chatPanel');
  const scene = document.getElementById('chatView');
  if (!canvas || !panel || !scene) return;
  const context = canvas.getContext('2d', { alpha: true, desynchronized: true });
  if (!context) return;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let width = 1;
  let height = 1;
  let dpr = 1;
  let raf = 0;
  let previousFrame = -Infinity;
  let startTime = 0;
  let stoppedAt = 0;
  let active = false;
  let metrics = { x: 0, y: 0, w: 0, h: 0 };

  function measure() {
    const parent = scene.getBoundingClientRect();
    const card = panel.getBoundingClientRect();
    width = Math.max(1, Math.round(parent.width));
    height = Math.max(1, Math.round(parent.height));
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    metrics = {
      x: card.left - parent.left,
      y: card.top - parent.top,
      w: card.width,
      h: card.height
    };
    paint(stoppedAt);
  }

  // Catmull-Rom spline through six control points; tip bends smoothly.
  function interpolate(points, t) {
    const clamped = Math.max(0, Math.min(0.999999, t));
    const a = clamped * (points.length - 1);
    const i = Math.floor(a);
    const u = a - i;
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[Math.min(points.length - 1, i + 1)];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    function interp(k) {
      return 0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * u +
        (2*p0[k] - 5*p1[k] + 4*p2[k] - p3[k]) * u*u +
        (-p0[k] + 3*p1[k] - 3*p2[k] + p3[k]) * u*u*u);
    }
    return [interp(0), interp(1)];
  }

  function makeTentacle(kind) {
    const {x,y,w,h} = metrics;
    const mobile = width <= 680;
    const margin = mobile ? 43 : Math.min(125, Math.max(58, (width - w) * 0.50));
    const visible = mobile ? 32 : margin;
    const up = kind < 2;
    const left = kind % 2 === 0;
    const sx = mobile ? (left ? -19 : width + 19) : (left ? x + 18 : x + w - 18);
    const ty = y + h * (up ? (mobile ? 0.32 : 0.34) : (mobile ? 0.72 : 0.77));
    const direction = left ? -1 : 1;
    const v = up ? -1 : 1;
    const xOuter = mobile ? (left ? 24 : width - 24) : (left ? sx - visible : sx + visible);
    const pointDistance = mobile ? 47 : 75;
    if (mobile) return {
      points: [
        [sx,ty],[left? 7:width-7,ty-6],
        [xOuter,ty+(up?-34:34)],
        [left?17:width-17,ty+(up?-66:66)],
        [left?6:width-6,ty+(up?-82:82)],
        [left?12:width-12,ty+(up?-59:59)]
      ],
      phase:[0.3,2.7,1.8,4.2][kind],side:[1,-1,-1,1][kind],width:12,amplitude:4
    };
    return {
      points: [
        [sx, ty],
        [sx + direction * visible * 0.54, ty + v * 0.01*h],
        [xOuter, ty + v * (mobile ? 40 : pointDistance)],
        [xOuter - direction * 3, ty + v * (mobile ? 87 : 130)],
        [sx + direction * (mobile ? 25 : 58), ty + v * (mobile ? 116 : 146)],
        [sx + direction * (mobile ? 6 : 37), ty + v * (mobile ? 83 : 112)]
      ],
      phase: [0.3,2.7,1.8,4.2][kind],
      side: [1, -1, -1, 1][kind],
      width: mobile ? 15 : 21,
      amplitude: mobile ? 6 : Math.min(17, visible * 0.2)
    };
  }

  function coords(arm, time) {
    const out = [];
    const n = 88;
    const wave = time * Math.PI * 2 / 6 + arm.phase;
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const base = interpolate(arm.points, t);
      const influence = Math.pow(t, 1.45);
      out.push([
        base[0] + (Math.sin(wave + t * 2.0) - Math.sin(wave)) * arm.amplitude * influence,
        base[1] + (Math.cos(wave + t * 2.3) - Math.cos(wave)) * arm.amplitude * 1.25 * influence
      ]);
    }
    return out;
  }

  function strokeSegments(points, arm) {
    const ctx = context;
    const n = points.length - 1;
    const layers = [
      {c:'#301326', extra:6, shiftX:2.5, shiftY:3.5},
      {c:'#d42133', extra:0, shiftX:0, shiftY:0},
      {c:'#fa5964', extra:-arm.width*0.76, shiftX:-2, shiftY:-2}
    ];
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const layer of layers) {
      ctx.strokeStyle = layer.c;
      for (let i = 1; i <= n; i++) {
        const t = i / n;
        const radius = Math.max(2, arm.width * (1 - 0.76 * Math.pow(t, 1.25)) + layer.extra);
        ctx.lineWidth = radius;
        ctx.beginPath();
        ctx.moveTo(points[i-1][0] + layer.shiftX, points[i-1][1] + layer.shiftY);
        ctx.lineTo(points[i][0] + layer.shiftX, points[i][1] + layer.shiftY);
        ctx.stroke();
      }
    }
  }

  function suctionCups(points, arm) {
    const ctx = context;
    for (let i = 9; i < points.length-5; i += 7) {
      const p = points[i];
      const before = points[i-2];
      const after = points[i+2];
      const dx = after[0]-before[0];
      const dy = after[1]-before[1];
      const len = Math.hypot(dx,dy) || 1;
      const t = i/(points.length-1);
      const radius = Math.max(1.3,arm.width*.17*(1-.65*t));
      const shift = arm.width * 0.29 * (1 - .6*t);
      const px = p[0] + (-dy / len) * shift * arm.side;
      const py = p[1] + (dx / len) * shift * arm.side;
      ctx.beginPath();ctx.arc(px,py,radius+1.1,0,Math.PI*2);ctx.fillStyle='#861d36';ctx.fill();
      ctx.beginPath();ctx.arc(px,py,Math.max(1,radius-.5),0,Math.PI*2);ctx.fillStyle='#fb7b81';ctx.fill();
      if (radius>2.2) {ctx.beginPath();ctx.arc(px,py,radius*.43,0,Math.PI*2);ctx.fillStyle='#a41b35';ctx.fill();}
    }
  }

  function paint(seconds) {
    context.clearRect(0,0,width,height);
    if (scene.hidden || width < 280 || height < 280) return;
    // Preserve readability: clip around the open margins; the chat panel itself is opaque.
    for(let kind = 0; kind < 4; kind++) {
      const arm = makeTentacle(kind);
      const shape = coords(arm,seconds);
      strokeSegments(shape,arm);
      suctionCups(shape,arm);
    }
  }

  function tick(timestamp) {
    if (!active) return;
    raf = requestAnimationFrame(tick);
    if (timestamp - previousFrame < (width <= 680 ? 30 : 16)) return;
    previousFrame = timestamp;
    if (!startTime) startTime = timestamp - stoppedAt*1000;
    stoppedAt = (timestamp-startTime)/1000;
    paint(stoppedAt);
  }

  function updateAnimation() {
    const wantsAnimation = !reduceMotion.matches && !document.hidden && !scene.hidden;
    if (wantsAnimation && !active) {
      active = true;
      startTime = 0;
      raf = requestAnimationFrame(tick);
    } else if (!wantsAnimation && active) {
      active = false;
      cancelAnimationFrame(raf);
      paint(reduceMotion.matches ? 0 : stoppedAt);
    }
  }
  const observer = new ResizeObserver(measure);
  const visibilityObserver = new MutationObserver(() => {
    requestAnimationFrame(() => { measure(); updateAnimation(); });
  });
  visibilityObserver.observe(scene, { attributes:true, attributeFilter:['hidden'] });
  observer.observe(scene);
  observer.observe(panel);
  document.addEventListener('visibilitychange',updateAnimation);
  reduceMotion.addEventListener('change',updateAnimation);
  document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click', () => {
    requestAnimationFrame(() => {measure();updateAnimation();});
  }));
  measure();
  updateAnimation();
})();
