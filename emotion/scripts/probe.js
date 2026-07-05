import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

function readJson(rel) {
  const p = path.join(root, rel);
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function exists(rel) {
  return fs.existsSync(path.join(root, rel));
}

const out = {
  data: {
    registry: exists("data/hexagram-registry.json"),
    weights: exists("data/emotional-weights.json"),
    reflections: exists("data/temporal-reflections.json"),
  },
  ts: {
    kingwen: exists("src/openjarvis/emotion/kingwen.py"),
    builder: exists("src/openjarvis/prompt/builder.py"),
    operative: exists("src/openjarvis/agents/operative.py"),
    monitor: exists("src/openjarvis/agents/monitor_operative.py"),
    morning: exists("src/openjarvis/agents/morning_digest.py"),
    config: exists("src/openjarvis/core/config.py"),
  },
};

if (out.data.registry && out.data.weights && out.data.reflections) {
  const registry = readJson("data/hexagram-registry.json");
  const weights = readJson("data/emotional-weights.json");
  const reflections = readJson("data/temporal-reflections.json");
  out.counts = {
    registry: Object.keys(registry).length,
    weights: Object.keys(weights).length,
    reflections: Object.keys(reflections).length,
  };
  out.samples = {
    "3": registry["3"],
    "6": registry["6"],
    "37": registry["37"],
  };
} else {
  out.counts = null;
  out.samples = null;
}

console.log(JSON.stringify(out, null, 2));
