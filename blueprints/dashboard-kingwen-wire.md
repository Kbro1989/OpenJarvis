# Blueprint: Dashboard King Wen Wire

## Intent
Wire King Wen reactive state into every reactive dashboard surface in OpenJarvis: overview energy/cost, journey timeline, agent status, artifact selection/inspection, and blueprint execution. 3D avatar usage is already applied; this blueprint covers the remaining dashboard consumers.

## Sources of Truth
- `C:\Users\krist\Desktop\OpenJarvis\frontend\src\pages\DashboardPage.tsx`
- `C:\Users\krist\Desktop\OpenJarvis\frontend\src\components\Dashboard\KingwenAdvisoryPanel.tsx`
- `C:\Users\krist\Desktop\OpenJarvis\frontend\src\components\Dashboard\KingwenAvatar3D.tsx`
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\core\neurological_map.py`
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\sovereign\immunology.py`
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\sovereign\pulse_monitor.py`

## Observed Gaps
1. `DashboardPage.tsx` imports `KingwenAdvisoryPanel` but never renders it. The 3D avatar panel is also absent from tabs.
2. `KingwenAdvisoryPanel.tsx` hardcodes `/v1/kingwen/consult` without auth headers, fallback, or session recovery.
3. No unified client for `/v1/kingwen` endpoints in `frontend/src/lib/api.ts`.
4. Reactive tabs (Overview, Journey, Agents, Artifacts, Blueprints) have no King Wen emotional/phase/porosity overlay.
5. No 64-node sovereign health view on the dashboard, even though `JarvisNeurologicalMap` and `NodeTester` are live in backend.

## Acceptance Criteria
- Dashboard renders a living King Wen advisory and avatar state sourced from live API.
- Reactive surfaces can consume porosity/coherence/voiceWeight/chaos/whimsy/darkTone without refactoring tab internals.
- All King Wen API calls use the same `getBase()`/`authHeaders()` pattern as the rest of the frontend.
- No stub/placeholder content; state derives from backend endpoints or local immutable-table fallback.

## Implementation Contract
Use this order:
1. Add `frontend/src/lib/kingwenDashboard.ts` for dashboard-scoped King Wen state/polling.
2. Update `DashboardPage.tsx` to include that state and add a sovereign/King Wen section in Overview and Journey tabs.
3. Replace raw `fetch('/v1/kingwen/...')` in `KingwenAdvisoryPanel.tsx` with the new client.

## Verification
- Build passes: `cd frontend && pnpm build` or `pnpm dev` renders dashboard without console errors.
- Runtime: dashboard shows advisory text, avatar payload, and sovereign pulse without blank panels.
