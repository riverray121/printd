// Bundled into dist/bundle.js and injected into a blank page by render.js.
// Exposes PrintdRender.renderComposite(gcodeText, opts) -> dataURL of a
// three-angle composite PNG.

import * as THREE from "three";
import { GCodeParser, GCodeRenderer } from "@polar3d/gcode-viewer";

// Keys are the parser's pathType names (see mapPathType in @polar3d/gcode-viewer).
const PATH_COLORS = {
  outer_perimeter: "#3a7ca5",
  inner_perimeter: "#8fb8d8",
  top_solid_infill: "#5a8db0",
  bottom_solid_infill: "#5a8db0",
  solid_infill: "#c0c0c0",
  infill: "#d9d9d9",
  support: "#f08a24",
  support_interface: "#c34a00",
  bridge: "#3366cc", // overhang perimeters also map here
  skirt: "#88bb88",
  brim: "#88bb88",
};

const LEGEND = [
  ["walls", "#3a7ca5"],
  ["surfaces", "#5a8db0"],
  ["infill", "#d9d9d9"],
  ["supports", "#f08a24"],
  ["support interface", "#c34a00"],
  ["bridges/overhangs", "#3366cc"],
  ["skirt/brim", "#88bb88"],
];

export async function renderComposite(gcodeText, opts) {
  const { bedX = 220, bedY = 220, panel = 720 } = opts || {};

  const parsed = new GCodeParser().parse(gcodeText);

  // Untagged extrusion (purge line, priming) has pathType "unknown"; keep it
  // out of both the render and the bounding box so it can't skew the framing.
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
  // render() centers all geometry on the bbox midpoint and returns one group
  // per layer.
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

  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 1.1);
  sun.position.set(1, -1, 2);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.4);
  fill.position.set(-1, 1, 1);
  scene.add(fill);

  // Scene space = G-code space minus `center` (Z-up). Draw the bed where it
  // really is so placement on the plate stays visible.
  const grid = new THREE.GridHelper(Math.max(bedX, bedY), 22, 0xcccccc, 0xe6e6e6);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(bedX / 2 - center.x, bedY / 2 - center.y, -center.z);
  scene.add(grid);

  const radius = Math.max(size.x, size.y, size.z) * 0.9 + 8;

  const canvas = document.createElement("canvas");
  canvas.width = panel;
  canvas.height = panel;
  const gl = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  gl.setSize(panel, panel, false);

  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
  camera.up.set(0, 0, 1);

  const angles = [
    ["isometric", [radius, -radius, radius * 0.85]],
    ["isometric, rotated", [-radius, -radius, radius * 0.85]],
    ["front", [0, -radius * 1.5, size.z * 0.25]],
  ];

  const shots = [];
  for (const [label, pos] of angles) {
    camera.position.set(pos[0], pos[1], pos[2]);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    gl.render(scene, camera);
    shots.push([label, canvas.toDataURL("image/png")]);
  }
  gl.dispose();

  const pad = 10;
  const legendH = 46;
  const out = document.createElement("canvas");
  out.width = panel * shots.length + pad * (shots.length + 1);
  out.height = panel + legendH + 56;
  const ctx = out.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, out.width, out.height);

  ctx.fillStyle = "#222222";
  ctx.font = "bold 22px sans-serif";
  ctx.fillText(`${opts.title || "sliced G-code"}   |   height ${size.z.toFixed(1)} mm`, pad, 30);

  for (let i = 0; i < shots.length; i++) {
    const [label, url] = shots[i];
    const img = new Image();
    await new Promise((res) => { img.onload = res; img.src = url; });
    const x = pad + i * (panel + pad);
    ctx.drawImage(img, x, 44, panel, panel);
    ctx.fillStyle = "#555555";
    ctx.font = "16px sans-serif";
    ctx.fillText(label, x + 4, 44 + panel + 18);
  }

  let lx = pad;
  const ly = out.height - 14;
  ctx.font = "15px sans-serif";
  for (const [name, color] of LEGEND) {
    ctx.fillStyle = color;
    ctx.fillRect(lx, ly - 13, 14, 14);
    ctx.fillStyle = "#333333";
    ctx.fillText(name, lx + 19, ly);
    lx += 19 + ctx.measureText(name).width + 22;
  }
  ctx.fillStyle = "#999999";
  ctx.fillText("rendered with @polar3d/gcode-viewer", out.width - 300, ly);

  return out.toDataURL("image/png");
}
