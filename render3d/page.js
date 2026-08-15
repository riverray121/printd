// Bundled into dist/bundle.js and injected into a blank page by render.js.
// Exposes PrintdRender.renderComposite(gcodeText, opts) -> dataURL of a
// six-view composite PNG.

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

  const center = new THREE.Vector3()
    .addVectors(bbox.min, bbox.max)
    .multiplyScalar(0.5);
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

  // Unit directions the camera sits along, per view (Z-up).
  const views = [
    ["isometric front-left", [-1, -1, 0.8]],
    ["isometric front-right", [1, -1, 0.8]],
    ["isometric back-right", [1, 1, 0.8]],
    ["front", [0, -1, 0.15]],
    ["right side", [1, 0, 0.15]],
    ["top", [0, -0.35, 1]],
  ];

  const shots = [];
  for (const [label, dir] of views) {
    const d = new THREE.Vector3(...dir).normalize().multiplyScalar(dist);
    camera.position.copy(d);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    gl.render(scene, camera);
    shots.push([label, canvas.toDataURL("image/png")]);
  }
  gl.dispose();

  const cols = 3;
  const rows = Math.ceil(shots.length / cols);
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

  for (let i = 0; i < shots.length; i++) {
    const [label, url] = shots[i];
    const img = new Image();
    await new Promise((res) => { img.onload = res; img.src = url; });
    const x = pad + (i % cols) * (panel + pad);
    const y = headerH + Math.floor(i / cols) * (panel + labelH + pad);
    ctx.drawImage(img, x, y, panel, panel);
    ctx.fillStyle = "#555555";
    ctx.font = "17px sans-serif";
    ctx.fillText(label, x + 4, y + panel + 19);
  }

  let lx = pad;
  const ly = out.height - 14;
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
