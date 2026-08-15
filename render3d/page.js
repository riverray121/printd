// Bundled into dist/bundle.js and injected into a blank page by render.js.
// Exposes PrintdRender.renderComposite(gcodeText, opts) -> dataURL of a
// twelve-panel composite PNG: six shaded tube views plus six transparent
// line-projection views, in rows of three.

import * as THREE from "three";
import { GCodeParser, GCodeRenderer } from "@polar3d/gcode-viewer";

// The parser only understands a fixed set of ;TYPE: names. Orca emits some
// it doesn't know (they'd land in "unknown" and be dropped), so normalize
// before parsing. Overhang walls are routed to the otherwise-unused
// "Prime tower" bucket to give them their own color — the parser's own
// table would fold them into "bridge".
const TYPE_ALIASES = [
  [/^;TYPE:Overhang wall\s*$/, ";TYPE:Prime tower"],
  [/^;TYPE:Internal solid infill\s*$/, ";TYPE:Solid infill"],
  [/^;TYPE:Internal Bridge\s*$/, ";TYPE:Bridge"],
];

function normalizeTypes(gcodeText) {
  return gcodeText
    .split("\n")
    .map((ln) => {
      if (!ln.startsWith(";TYPE:")) return ln;
      for (const [re, sub] of TYPE_ALIASES) {
        if (re.test(ln)) return sub;
      }
      return ln;
    })
    .join("\n");
}

// Keys are the parser's pathType names. prime_tower carries overhang walls
// (see TYPE_ALIASES).
const PATH_COLORS = {
  outer_perimeter: "#555555",
  inner_perimeter: "#aaaaaa",
  top_solid_infill: "#777777",
  bottom_solid_infill: "#777777",
  solid_infill: "#c9c9c9",
  infill: "#e3e3e3",
  support: "#f08a24",
  support_interface: "#c34a00",
  bridge: "#3366cc",
  prime_tower: "#cc2288",
  skirt: "#88bb88",
  brim: "#88bb88",
};

// pathType -> (stroke px, alpha) for the line views. Infill is omitted
// there on purpose: transparency is what lets structure show through.
const LINE_STYLE = {
  outer_perimeter: [0.7, 0.75],
  inner_perimeter: [0.5, 0.35],
  top_solid_infill: [0.5, 0.5],
  bottom_solid_infill: [0.5, 0.5],
  support: [1.2, 0.85],
  support_interface: [1.2, 0.95],
  bridge: [0.9, 0.9],
  prime_tower: [0.9, 0.9],
  skirt: [0.7, 0.8],
  brim: [0.7, 0.8],
};
const LINE_DRAW_ORDER = [
  "brim", "skirt", "bottom_solid_infill", "top_solid_infill",
  "inner_perimeter", "outer_perimeter", "prime_tower", "bridge",
  "support", "support_interface",
];

const LEGEND = [
  ["part walls", "#555555"],
  ["surfaces", "#777777"],
  ["infill", "#e3e3e3"],
  ["supports", "#f08a24"],
  ["support interface", "#c34a00"],
  ["bridges", "#3366cc"],
  ["overhangs", "#cc2288"],
  ["skirt/brim", "#88bb88"],
];

const C30 = Math.cos(Math.PI / 6);
const S30 = Math.sin(Math.PI / 6);

export async function renderComposite(gcodeText, opts) {
  const { bedX = 220, bedY = 220, panel = 900 } = opts || {};

  const parsed = new GCodeParser().parse(normalizeTypes(gcodeText));

  // Untagged extrusion (purge line, start gcode) has pathType "unknown";
  // keep it out of the render and the bounding box.
  const layers = parsed.layers
    .map((l) => ({ ...l, paths: l.paths.filter((p) => p.pathType !== "unknown") }))
    .filter((l) => l.paths.length > 0);

  const bbox = {
    min: new THREE.Vector3(Infinity, Infinity, Infinity),
    max: new THREE.Vector3(-Infinity, -Infinity, -Infinity),
  };
  for (const l of layers) {
    for (const p of l.paths) {
      if (!p.isExtrusion) continue;
      for (let i = 0; i < p.vertices.length; i += 3) {
        bbox.min.x = Math.min(bbox.min.x, p.vertices[i]);
        bbox.min.y = Math.min(bbox.min.y, p.vertices[i + 1]);
        bbox.min.z = Math.min(bbox.min.z, p.vertices[i + 2]);
        bbox.max.x = Math.max(bbox.max.x, p.vertices[i]);
        bbox.max.y = Math.max(bbox.max.y, p.vertices[i + 1]);
        bbox.max.z = Math.max(bbox.max.z, p.vertices[i + 2]);
      }
    }
  }
  const center = new THREE.Vector3()
    .addVectors(bbox.min, bbox.max)
    .multiplyScalar(0.5);
  const size = new THREE.Vector3().subVectors(bbox.max, bbox.min);

  const tubeShots = renderTubeViews(layers, bbox, center, { bedX, bedY, panel });

  // ---- composite ----
  const cols = 3;
  const panels = 12;
  const rows = panels / cols;
  const pad = 10;
  const labelH = 26;
  const headerH = 44;
  const legendH = 46;
  const out = document.createElement("canvas");
  out.width = panel * cols + pad * (cols + 1);
  out.height = headerH + rows * (panel + labelH + pad) + legendH;
  const ctx = out.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);

  ctx.fillStyle = "#222222";
  ctx.font = "bold 24px sans-serif";
  ctx.fillText(
    `${opts.title || "sliced G-code"}   |   ${size.x.toFixed(0)} x ${size.y.toFixed(0)} x ${size.z.toFixed(1)} mm`,
    pad, 30,
  );

  const cell = (i) => [
    pad + (i % cols) * (panel + pad),
    headerH + Math.floor(i / cols) * (panel + labelH + pad),
  ];
  const label = (i, text) => {
    const [x, y] = cell(i);
    ctx.fillStyle = "#555555";
    ctx.font = "17px sans-serif";
    ctx.fillText(text, x + 4, y + panel + 19);
  };

  for (let i = 0; i < tubeShots.length; i++) {
    const [name, url] = tubeShots[i];
    const img = new Image();
    await new Promise((res) => { img.onload = res; img.src = url; });
    const [x, y] = cell(i);
    ctx.drawImage(img, x, y, panel, panel);
    label(i, name);
  }

  const lineViews = [
    ["isometric — lines", (x, y, z) => [(x - y) * C30, (x + y) * S30 - z], false],
    ["isometric, rotated 90° — lines", (x, y, z) => [(y - (bedX - x)) * C30, (y + (bedX - x)) * S30 - z], false],
    ["isometric back-right — lines", (x, y, z) => [((bedX - x) - (bedY - y)) * C30, ((bedX - x) + (bedY - y)) * S30 - z], false],
    ["front elevation — lines", (x, y, z) => [x, -z], false],
    ["side elevation — lines", (x, y, z) => [y, -z], false],
    ["top-down, bed dashed — lines", (x, y, z) => [x, -y], true],
  ];
  for (let i = 0; i < lineViews.length; i++) {
    const [name, proj, withBed] = lineViews[i];
    const [x, y] = cell(tubeShots.length + i);
    drawLineView(ctx, layers, proj, withBed, { bedX, bedY }, x, y, panel);
    label(tubeShots.length + i, name);
  }

  let lx = pad;
  const ly = out.height - 14;
  ctx.globalAlpha = 1;
  ctx.font = "16px sans-serif";
  for (const [name, color] of LEGEND) {
    ctx.fillStyle = color;
    ctx.fillRect(lx, ly - 14, 15, 15);
    ctx.fillStyle = "#333333";
    ctx.fillText(name, lx + 20, ly);
    lx += 20 + ctx.measureText(name).width + 24;
  }
  ctx.fillStyle = "#999999";
  ctx.fillText("rendered with @polar3d/gcode-viewer", out.width - 310, ly);

  return out.toDataURL("image/png");
}

function renderTubeViews(layers, bbox, center, { bedX, bedY, panel }) {
  const renderer3d = new GCodeRenderer({
    renderTubes: true,
    extrusionWidth: 0.45,
    lineHeight: 0.2,
    customColors: PATH_COLORS,
  });
  // render() centers all geometry on the bbox midpoint and returns one
  // group per layer.
  const renderedLayers = renderer3d.render(layers, bbox);
  const model = new THREE.Group();
  for (const rl of renderedLayers) model.add(rl.object);

  const size = new THREE.Vector3().subVectors(bbox.max, bbox.min);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#ffffff");
  scene.add(model);

  scene.add(new THREE.AmbientLight(0xffffff, 0.8));
  const sun = new THREE.DirectionalLight(0xffffff, 1.0);
  sun.position.set(1, -1, 2);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.45);
  fill.position.set(-1, 1, 1);
  scene.add(fill);

  // Scene space = G-code space minus `center` (Z-up). Draw the bed where
  // it really is so placement on the plate stays visible.
  const grid = new THREE.GridHelper(Math.max(bedX, bedY), 22, 0xcccccc, 0xeeeeee);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(bedX / 2 - center.x, bedY / 2 - center.y, -center.z);
  scene.add(grid);

  const canvas = document.createElement("canvas");
  canvas.width = panel;
  canvas.height = panel;
  const gl = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  gl.setSize(panel, panel, false);

  const FOV = 35;
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 5000);
  camera.up.set(0, 0, 1);

  // Fit the bbox's bounding sphere in view with a margin, so the whole
  // part is framed identically regardless of size.
  const sphereR = size.length() / 2;
  const dist = (sphereR / Math.sin((FOV / 2) * (Math.PI / 180))) * 1.12;

  const views = [
    ["isometric front-left — tubes", [-1, -1, 0.8]],
    ["isometric front-right — tubes", [1, -1, 0.8]],
    ["isometric back-right — tubes", [1, 1, 0.8]],
    ["front — tubes", [0, -1, 0.15]],
    ["right side — tubes", [1, 0, 0.15]],
    ["top — tubes", [0, -0.35, 1]],
  ];

  const shots = [];
  for (const [name, dir] of views) {
    const d = new THREE.Vector3(...dir).normalize().multiplyScalar(dist);
    camera.position.copy(d);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    gl.render(scene, camera);
    shots.push([name, canvas.toDataURL("image/png")]);
  }
  gl.dispose();
  return shots;
}

function drawLineView(ctx, layers, proj, withBed, { bedX, bedY }, ox, oy, panel) {
  // Project every drawable path, find extents, then scale-to-fit the cell.
  const margin = 30;
  let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;
  const paths = [];
  for (const l of layers) {
    for (const p of l.paths) {
      if (!p.isExtrusion || !(p.pathType in LINE_STYLE)) continue;
      const pts = [];
      for (let i = 0; i < p.vertices.length; i += 3) {
        const [u, v] = proj(p.vertices[i], p.vertices[i + 1], p.vertices[i + 2]);
        pts.push(u, v);
        if (u < minU) minU = u;
        if (u > maxU) maxU = u;
        if (v < minV) minV = v;
        if (v > maxV) maxV = v;
      }
      if (pts.length >= 4) paths.push([p.pathType, pts]);
    }
  }
  let bedPts = null;
  if (withBed) {
    bedPts = [[0, 0], [bedX, 0], [bedX, bedY], [0, bedY], [0, 0]].map(([cx, cy]) => proj(cx, cy, 0));
    for (const [u, v] of bedPts) {
      if (u < minU) minU = u;
      if (u > maxU) maxU = u;
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
  }
  if (!paths.length) return;

  const scale = Math.min(
    (panel - 2 * margin) / Math.max(maxU - minU, 1e-6),
    (panel - 2 * margin) / Math.max(maxV - minV, 1e-6),
  );
  const tx = (u) => ox + (panel - (maxU - minU) * scale) / 2 + (u - minU) * scale;
  const ty = (v) => oy + (panel - (maxV - minV) * scale) / 2 + (v - minV) * scale;

  ctx.save();
  ctx.beginPath();
  ctx.rect(ox, oy, panel, panel);
  ctx.clip();
  ctx.lineCap = "round";

  if (bedPts) {
    ctx.strokeStyle = "#bbbbbb";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 6]);
    ctx.globalAlpha = 1;
    ctx.beginPath();
    bedPts.forEach(([u, v], i) => (i ? ctx.lineTo(tx(u), ty(v)) : ctx.moveTo(tx(u), ty(v))));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  for (const type of LINE_DRAW_ORDER) {
    const [w, alpha] = LINE_STYLE[type];
    ctx.strokeStyle = PATH_COLORS[type];
    ctx.lineWidth = w;
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    for (const [t, pts] of paths) {
      if (t !== type) continue;
      ctx.moveTo(tx(pts[0]), ty(pts[1]));
      for (let i = 2; i < pts.length; i += 2) ctx.lineTo(tx(pts[i]), ty(pts[i + 1]));
    }
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}
