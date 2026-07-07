import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, "src")
from openjarvis.secrets.store import CF_WORKERS, LOCAL_PORTS, MODEL_ROLODEX, task_fit_for, ternary_model_class, worker_url, task_model_chain

print("=== CF Workers ===")
for k, v in CF_WORKERS.items():
    print(f"  {k:<22}  {v['base_url']}  [{v['status']}]")

print()
print("=== Local Ports ===")
for k, v in LOCAL_PORTS.items():
    if isinstance(v, dict) and "url" in v:
        print(f"  {k:<16}  {v['url']}")

print()
print("=== ModelRolodex ternary router ===")
for combo, cls in MODEL_ROLODEX["ternary_router"].items():
    print(f"  {combo:<28}  -> {cls}")

print()
print("=== Task classification ===")
tests = ["debug this python function", "what does hexagram 32 mean", "search arxiv for megatron", "show me the image"]
for t in tests:
    task = task_fit_for(t)
    model = task_model_chain(task)[0]
    print(f"  {t[:40]!r}  -> {task}  -> {model}")

print()
print("=== Ternary model class ===")
print(f"  sovereign+ASSERT  -> {ternary_model_class('sovereign', 'ASSERT')}")
print(f"  transformer+YIELD -> {ternary_model_class('transformer', 'YIELD')}")
print(f"  dissipator+ADAPT  -> {ternary_model_class('dissipator', 'ADAPT')}")
print(f"  boundary+WAIT     -> {ternary_model_class('boundary', 'WAIT')}")
