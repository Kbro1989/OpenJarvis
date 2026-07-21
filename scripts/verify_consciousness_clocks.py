"""verify_consciousness_clocks.py"""
import py_compile
import sys

sys.path.insert(0, "src")
py_compile.compile(
    "src/openjarvis/core/session_clock_bridge.py", doraise=True
)

from openjarvis.core.session_clock_bridge import (
    ConsciousnessClock,
    get_consciousness_clock,
    consciousness_tick,
    consciousness_state,
)

try:
    ConsciousnessClock("s1", domain="invalid")
except ValueError:
    print("domain-reject ok")

try:
    ConsciousnessClock("s1").tick(yin_yang_yao="invalid_yao")
except ValueError:
    print("yao-reject ok")

try:
    ConsciousnessClock("s1").tick(past_present_future="invalid_time")
except ValueError:
    print("ppf-reject ok")

c1 = consciousness_tick(
    "s1", domain="consciousness", yin_yang_yao="old_yang", past_present_future="present"
)
c2 = consciousness_state("s1", domain="consciousness")
assert c1["tick_id"] == 1
assert c1["yin_yang_yao"] == "old_yang"
assert c1["past_present_future"] == "present"
assert c2["tick_id"] == 1
assert c2["yin_yang_yao"] == "old_yang"

same = get_consciousness_clock("s1", domain="consciousness")
other = get_consciousness_clock("s1", domain="reflexive")
assert same is not other
print("identity ok")
print("verify-clocks ok")
