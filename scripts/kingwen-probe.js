import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const DATA = {
  registry: path.join(root, "data", "hexagram-registry.json"),
  weights: path.join(root, "data", "emotional-weights.json"),
  reflections: path.join(root, "data", "temporal-reflections.json"),
};

const ENDPOINTS = {
  kingwen: path.join(root, "src", "openjarvis", "emotion", "kingwen.py"),
  builder: path.join(root, "src", "openjarvis", "prompt", "builder.py"),
  operative: path.join(root, "src", "openjarvis", "agents", "operative.py"),
  monitor: path.join(root, "src", "openjarvis", "agents", "monitor_operative.py"),
  morning: path.join(root, "src", "openjarvis", "agents", "morning_digest.py"),
  config: path.join(root, "src", "openjarvis", "core", "config.py"),
};

function exists(p) {
  return Boolean(p && fs.existsSync(p));
}
function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

const result = {
  data: {
    registry: exists(DATA.registry),
    weights: exists(DATA.weights),
    reflections: exists(DATA.reflections),
  },
  endpoints: {
    kingwen: exists(ENDPOINTS.kingwen),
    builder: exists(ENDPOINTS.builder),
    operative: exists(ENDPOINTS.operative),
    monitor: exists(ENDPOINTS.monitor),
    morning: exists(ENDPOINTS.morning),
    config: exists(ENDPOINTS.config),
  },
};

if (result.data.registry && result.data.weights && result.data.reflections) {
  const registry = readJson(DATA.registry);
  const weights = readJson(DATA.weights);
  const reflections = readJson(DATA.reflections);
  result.counts = {
    registry: Object.keys(registry).length,
    weights: Object.keys(weights).length,
    reflections: Object.keys(reflections).length,
  };
  result.samples = {
    "3": registry["3"],
    "6": registry["6"],
    "37": registry["37"],
  };
} else {
  result.counts = null;
  result.samples = null;
}

console.log(JSON.stringify(result, null, 2));
