# CI baseline control — never merge

This disposable branch compares base a316271cc0742b6939e8bda97cb340a4def7acc5 with candidate 7ff6539e756bf4ad24274d7c636297c929d1a502.
Only pyproject.toml is copied byte-for-byte from the candidate; application code, tests, hooks and workflows remain at the base.
The purpose is a full base-versus-candidate CI comparison using the same declared installation inputs and workflow.
Old SDK API usage paired with the candidate dependency environment may legitimately fail; classify failures from observed evidence.
Do not assume every failure predates the candidate or claim this reproduces the original unbounded dependency environment.
This control branch is evidence only, must never be merged, and makes no claim that CI is green.
