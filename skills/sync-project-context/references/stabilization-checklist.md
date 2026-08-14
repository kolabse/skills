# Stabilization checklist

Use this checklist before changing `sync-project-context` from experimental to
stable.

## Deterministic acceptance

Run the dependency-free two-machine simulation:

```shell
python <skill-root>/scripts/context_sync_acceptance.py --streams 20 --json
```

Require exact title restoration, ordered baseline-plus-delta history,
idempotent repeated restore, unique checkpoint identifiers, no unexpected
conflict, and a valid audit from both simulated machines.

## Real-device acceptance

On two physical computers using the approved Google Drive account:

1. Configure the same repository identity independently.
2. Save several new and existing desktop chat streams on computer A.
3. Restore them on computer B and verify exact titles and one task per stream.
4. Append changes on B, synchronize on A, and verify ordered deltas.
5. Rename one title on each side, create one intentional content conflict, and
   verify that the affected stream blocks without losing either head.
6. Interrupt one upload after creation, retry by exact checkpoint name, and
   verify readback plus audit.
7. Exercise a paginated Drive folder and report the desktop discovery limit.

Record only sanitized counts, opaque IDs, pass/fail outcomes, and product/tool
versions. Do not copy account identities, Drive links, transcripts, paths,
source, or raw logs into the repository.

## Promotion gate

Keep the skill experimental until deterministic acceptance passes on all CI
platforms, the real-device procedure passes twice without manual data repair,
the release holdout includes the stable trigger surface, and every known
limitation has an explicit fail-closed behavior or documented coverage bound.
