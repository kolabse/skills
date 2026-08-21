---
name: orchestrate-agent-work
description: "Coordinate explicitly requested subagents or parallel agent work by assigning bounded ownership, monitoring progress, reconciling outputs, and verifying the integrated result. Use when the user or project instructions request delegation or parallel agents; do not use merely because a task has several steps."
---

# Orchestrate Agent Work

Coordinate delegated work without surrendering responsibility for the outcome.

## Define the delegation boundary

1. Confirm that the user or applicable project instructions authorize subagents.
2. Split only work that is concrete, independently useful, and safe to run concurrently. Keep integration, shared decisions, and final verification with the coordinating agent.
3. Give each agent an exact deliverable, allowed resources and mutations, file ownership when worktrees are shared, required evidence, and any prohibition on further delegation.
4. Respect the available concurrency limit. Do not create user-visible tasks when internal subagents are intended.

Completion criterion: every assignment has a distinct outcome and no two agents can unknowingly overwrite the same work.

## Coordinate execution

- Continue useful coordinator work while agents run.
- Communicate material changes in assumptions promptly. Interrupt only when continuing would waste work or create risk.
- Prefer bounded waits and progress snapshots over repeated polling.
- Treat agent conclusions as inputs, not proof. Inspect evidence and reconcile contradictions.
- Never delegate approval decisions, secrets, destructive cleanup, or external mutations beyond the authority already granted.

## Integrate and verify

Collect every terminal result, account for incomplete assignments, inspect shared-worktree changes, and resolve overlaps deliberately. Run the checks appropriate to the combined result. Report delegated work as complete only after the integrated outcome—not merely each subtask—has been verified.

Completion criterion: all assignments are terminal or explicitly excluded, outputs agree or conflicts are explained, the integrated result passes relevant verification, and remaining risk is visible.
