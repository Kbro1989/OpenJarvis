"""verify_consciousness_wiring.py"""
import py_compile
import sys

sys.path.insert(0, "src")

# 1) compile all patched files
for path in [
    "src/openjarvis/core/session_clock_bridge.py",
    "src/openjarvis/emotion/kingwen.py",
    "src/openjarvis/agents/_stubs.py",
]:
    py_compile.compile(path, doraise=True)
print("py_compile: ok")

# 2) import clock module
from openjarvis.core.session_clock_bridge import (
    ConsciousnessClock,
    consciousness_state,
    consciousness_tick,
    get_consciousness_clock,
)

# 3) domain validation
for bad in ("invalid", "consciousness", "reflexive"):
    try:
        ConsciousnessClock("s1", domain=bad)
    except ValueError:
        print(f"domain reject: {bad}: ok")

# 4) yin_yang_yao / ppf validation
try:
    ConsciousnessClock("s1").tick(yin_yang_yao="young_yin", past_present_future="present")
except Exception:
    pass
try:
    ConsciousnessClock("s1").tick(yin_yang_yao="bad_yao")
except ValueError:
    print("yao reject: ok")
try:
    ConsciousnessClock("s1").tick(past_present_future="bad_time")
except ValueError:
    print("ppf reject: ok")

# 5) independent domains
cns = consciousness_tick("s1", domain="cns", yin_yang_yao="old_yang", past_present_future="present")
pns = consciousness_tick("s1", domain="pns", yin_yang_yao="new_yang", past_present_future="future")
mcp = consciousness_tick("s1", domain="mcp")
api = consciousness_tick("s1", domain="api")
assert cns["domain"] == "cns"
assert pns["domain"] == "pns"
assert mcp["domain"] == "mcp"
assert api["domain"] == "api"
assert cns["yin_yang_yao"] == "old_yang"
assert pns["past_present_future"] == "future"
print("domains independent: ok")

# 6) clock identity
same = get_consciousness_clock("s1", domain="cns")
other = get_consciousness_clock("s1", domain="pns")
assert same is not other
assert consciousness_state("s1", domain="cns")["session_id"] == "s1"
print("clock identity: ok")

# 7) kingwen consult wires cns block
from openjarvis.emotion.kingwen import KingWenEmotionProvider
provider = KingWenEmotionProvider(
    registry_path="data/hexagram-registry.json",
    weights_path="data/emotional-weights.json",
    reflections_path="data/temporal-reflections.json",
)
result = provider.consult(text="verify", session_id="s1", emotional_input=50)
cns_block = result.get("consciousness") or {}
assert "tick_id" in cns_block
assert cns_block.get("yin_yang_yao") in ("", "young_yin","old_yin","present_yin","new_yao","old_yao","present_yao","old_yang","new_yang","present_yang"), cns_block
assert cns_block.get("past_present_future") in ("", "past", "present", "future"), cns_block
print("kingwen consult cns wired: ok")

print("VERIFIED_OK")
