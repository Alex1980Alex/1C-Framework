"""Real BP-fire validation script — roadmap 260508 P1 acceptance.

Long-lived RDBGClient session (~75s) with ping_loop auto-attach for
new worker targets. After BP set the user triggers a UI action which
hits the BP. Script collects post-BP-fire validation: stack/vars/eval/step.
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, r"C:/1С-Framework/tools/bsl-debug-server")
from mcp_debug_server import RDBGClient

INFOBASE = "IBTransportManagementDevelop"
CONFIG_VERSION = "39473d56e455bd4087b48823b4a6c24900000000"
OBJ_UUID = "75e77f99-b9d1-4bc0-93aa-c77a93d760d3"
PROP_UUID = "d5963243-262e-4398-b4d7-fb16d06484f6"
LINE = 67
WAIT_SECONDS = 75


async def main(infobase: str):
    c = RDBGClient(infobase_alias=infobase)
    report = {"infobase": infobase, "validations": {}, "errors": []}
    try:
        report["api_version"] = await c.get_api_version()
        att = await c.attach()
        report["attach_result"] = att["result"]
        await c.init_settings()

        targets = await c.get_targets()
        ids = [t["id"] for t in targets if t.get("id")]
        if ids:
            await c.attach_debug_targets(ids)
            c._known_attached_targets.update(ids)
        report["initial_targets"] = ids

        await c.set_breakpoints(
            module_type="ConfigModule",
            object_id=OBJ_UUID,
            property_id=PROP_UUID,
            lines=[LINE],
            version=CONFIG_VERSION,
        )
        report["bp_set"] = {"line": LINE, "version": CONFIG_VERSION}
        print(f"[setup OK] BP set, {len(ids)} targets attached", file=sys.stderr)
        print(f"[user-action] perform UI action in 1C, waiting {WAIT_SECONDS}s", file=sys.stderr)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + WAIT_SECONDS
        while loop.time() < deadline:
            if c.last_stopped_target_id:
                break
            await asyncio.sleep(1.0)

        if not c.last_stopped_target_id:
            report["errors"].append(
                f"No BP fire after {WAIT_SECONDS}s. "
                f"Targets attached: {len(c._known_attached_targets)}"
            )
            return report

        target = c.last_stopped_target_id
        report["bp_fired"] = {
            "target": target,
            "reason": c._stop_reason_by_target.get(target),
        }
        print(f"[BP FIRED] target={target}", file=sys.stderr)

        stack = await c.get_call_stack()
        report["validations"]["stack_frames"] = len(stack)
        report["validations"]["stack_first_frame"] = stack[0] if stack else None

        variables = await c.eval_local_variables()
        report["validations"]["variables_count"] = len(variables)
        report["validations"]["variables_sample"] = variables[:3] if variables else []

        eval_now = await c.eval_expression(expression="CurrentDate()")
        report["validations"]["eval_currentdate"] = eval_now[:1] if eval_now else None

        eval_user = await c.eval_expression(
            expression="SessionParameters.CurrentUser",
            view_interface="context",
        )
        report["validations"]["eval_with_view_interface"] = eval_user[:1] if eval_user else None

        await c.step(action="Continue")
        report["validations"]["step_resumed"] = c.last_stopped_target_id is None

    except Exception as e:
        report["errors"].append(f"{type(e).__name__}: {e}")
    finally:
        try:
            await c.close()
        except Exception:
            pass
    return report


if __name__ == "__main__":
    ib = sys.argv[1] if len(sys.argv) > 1 else INFOBASE
    res = asyncio.run(main(ib))
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
