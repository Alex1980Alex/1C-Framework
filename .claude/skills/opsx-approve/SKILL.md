---
name: opsx-approve
description: Approve or reject an OpenSpec change design before implementation. Use when reviewing specs, approving designs, or rejecting changes with feedback.
license: MIT
metadata:
  author: 1c-framework
  version: "1.0"
---

Review and approve or reject an OpenSpec change design.

**Input**: `$ARGUMENTS` — change name (optional), `--reject` flag (optional), `--comment "reason"` (optional)

**Steps**

1. **Select the change**

   Parse `$ARGUMENTS` for change name, `--reject`, `--comment "..."`.

   If no name provided:
   - Run `openspec list --json` to get active changes
   - If only one active change, auto-select it
   - If multiple, use **AskUserQuestion** to let user select

   Announce: "Reviewing change: **<name>**"

2. **Show review summary**

   Read the change artifacts:
   - `openspec/changes/<name>/proposal.md`
   - `openspec/changes/<name>/specs/` (all spec files)
   - `openspec/changes/<name>/design.md`
   - `openspec/changes/<name>/tasks.md`

   Display a concise review card:

   ```
   ## Review: <change-name>

   ### Proposal
   <1-2 sentence summary of what and why>

   ### Specs
   <N requirements, M scenarios (Given/When/Then)>

   ### Design
   <architecture approach, key technical decisions>

   ### Tasks
   <N tasks listed>

   ### Current Approval Status
   <pending | approved | rejected>
   ```

3. **Handle rejection**

   If `--reject` in arguments:
   - A comment is REQUIRED for rejection (extract from `--comment` or ask user)
   - Update `.openspec.yaml` — add/replace the `approval` section:
     ```yaml
     approval:
       status: rejected
       reviewed_by: human
       reviewed_at: <YYYY-MM-DDTHH:MM:SS>
       comment: "<rejection reason>"
     ```
   - Show: "Change **<name>** rejected. Reason: <comment>"
   - Suggest: "Update the design with `/opsx:explore <name>`, then re-approve."
   - Exit

4. **Approve the change**

   If NOT rejected:
   - Update `.openspec.yaml` — add/replace the `approval` section:
     ```yaml
     approval:
       status: approved
       reviewed_by: human
       reviewed_at: <YYYY-MM-DDTHH:MM:SS>
       comment: <comment if provided, or null>
     ```
   - Show confirmation:
     ```
     Change "<name>" approved.
     Ready for implementation: /opsx:apply <name>
     ```

**How to update .openspec.yaml**

Read the existing file. If it already has an `approval:` section, replace it entirely.
If not, append the approval section at the end. Use the Read tool first, then Edit tool.

Example final `.openspec.yaml`:
```yaml
schema: spec-driven
created: 2026-04-01
approval:
  status: approved
  reviewed_by: human
  reviewed_at: 2026-04-01T21:30:00
  comment: null
```

**Guardrails**
- ALWAYS show the review summary before approving or rejecting
- Never auto-approve — this skill is invoked explicitly by the human
- For rejection, REQUIRE a comment (ask if not provided)
- Only modify `.openspec.yaml`, never touch other artifacts
- If `.openspec.yaml` doesn't exist, create it with `schema: spec-driven` + approval section
