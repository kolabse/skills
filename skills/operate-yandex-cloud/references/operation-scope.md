# Bind scope to the operation

The general preflight is a point-in-time observation. It does not constrain a
later process. YC Cloud/Folder flags set defaults; lookups by resource ID can
ignore those defaults. Verify the returned resource's ownership before acting.
See the official [CLI context rules](https://yandex.cloud/en/docs/cli/concepts/)
and [instance get interface](https://yandex.cloud/en/docs/compute/cli-ref/instance/get).

## Bounded Compute VM wrapper

Use `scripts/yc_project.py` for these exact command shapes:

```shell
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance list
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance get --id <instance-id>
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance start --id <instance-id>
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance stop --id <instance-id>
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance restart --id <instance-id>
```

Mutation examples apply only when the user's existing request authorizes that
action on that VM. The helper does not supply authorization.

The wrapper requires a configured Cloud ID, Folder ID and explicit `yc_profile`
using the existing shared/local configuration. It does not switch the active
profile or repair global configuration. Additional arguments, names instead
of IDs, aliases, arbitrary commands, output selectors and context overrides
are unsupported and rejected before invoking YC.

Each invocation pins the resolved YC executable and takes one environment
snapshot. Every call uses explicit project Cloud/Folder/profile arguments.
It observes the authenticated subject, verifies access to the cloud, and checks
that the folder belongs to it. For a selected VM, a fresh `get` must return the
requested ID and configured folder before any mutation. A list must contain
only instances in that folder. The project configuration is rechecked before
execution so changed inputs cannot silently replace the checked scope.

Start/stop/restart use native synchronous execution without `--async`, followed
by a fresh `get` checking ownership and the expected VM status. A successful
process exit alone is insufficient. The helper reports only a sanitized JSON
summary: target IDs, statuses, phase, exit code and whether mutation was
attempted. It does not forward resource metadata, names, credentials or raw CLI
errors. A failure after execution is an unverified outcome, not proof that the
mutation did not happen. Inspect current state before retrying.

These are operation-scoped checks, not reusable authorization receipts. Run
them again for each operation. They do not create a global preflight cache.

## Identity and concurrency limits

The environment snapshot preserves approved credential mechanisms, including
`YC_IAM_TOKEN`. Selecting a profile does not independently attest credentials;
the identity check observes the effective subject. The helper does not copy
tokens to arguments or persist them. Do not modify the selected profile or
credential files concurrently with an operation.

Ownership checks are not an atomic IAM boundary. Use appropriately restricted
project/folder permissions and coordinate concurrent moves or deletion of the
target. A local helper cannot lock cloud resources between lookup and action.
The supported operations do not accept additional cross-folder references;
creation, update, IAM changes and other service operations require their own
reviewed ownership checks.

## Other tools and repository wrappers

The Compute wrapper does not constrain SSH, Ansible, Terraform, Helm,
Kubernetes, arbitrary scripts or another YC process. Before accepting a global
context warning for any such operation:

1. Read the exact repository-owned entrypoint and its downstream invocations.
   Identify scope inputs and show that required inputs are validated, explicitly
   forwarded, and cannot fall back to ambient defaults. If that cannot be
   established, stop the mutation and correct the wrapper within task scope.
2. Validate each resource reference against the configured project. For SSH or
   OS Login, bind the verified VM ID to the current inventory address and
   expected SSH host identity; a matching IP alone is insufficient. For
   Terraform, inspect provider scope, workspace and saved plan; for Kubernetes,
   inspect the explicit context, cluster and namespace used by every command.
3. Record the reviewed wrapper revision, exact non-secret target inputs and
   checks immediately before execution. Do not treat a command hash as proof
   that a shell script or its transitive commands enforce scope.
4. If short-lived access expires, use the repository's approved refresh helper,
   then repeat identity, scope and target checks before a bounded retry. Check
   whether a previous attempt changed state before repeating a mutation.

## Targeted apply after a broad preview

When a full configuration-management preview exposes unrelated drift or a
check-mode dependency, preserve its result and leave those changes unapplied.
Identify a reviewed, narrowly scoped task or role that performs the requested
change, including its dependencies and handlers. Host limits or tags alone do
not prove that unrelated tasks, delegated hosts or handlers are excluded.

For example, installing one reviewed deployment helper should target the exact
host and file task, with the required owner, mode and source artifact. Inspect
task selection and dependencies; use a supported narrow preview when possible.
If check mode cannot model a generated prerequisite, explain that limitation
and inspect the prerequisite explicitly. Do not infer a successful dry run or
widen the authorized change to make the preview pass.

Apply the bounded operation only within the existing authorization. Verify
the remote file checksum against the reviewed source, remote syntax, owner and
mode, and any requested service behavior. Report remaining drift separately.
If the narrow operation still requires an unrequested destructive change or
material scope expansion, prepare that concrete change for the user's decision.
