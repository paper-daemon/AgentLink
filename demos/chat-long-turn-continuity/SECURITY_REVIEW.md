# Public Continuity Engine: Threat Model and Security Review

**Review date:** 2026-11-05 (JST)
**Scope:** The MIT-licensed public demos/chat-long-turn-continuity/ package, its tests and GitHub Actions. **Not** the private AgentLink production core.
**Status:** Focused maintainer-assisted hardening, **not** an independent security audit, penetration test, or production certification.

## Trust boundaries

| Boundary | Assumption | What this code does and does not protect |
|---|---|---|
| Caller → package | Caller is trusted | The package does **not** authenticate users, workers, or agents. Worker names are labels, not identities. |
| Package → SQLite | Directory belongs to the local account | SQLite transactions serialize local writes; POSIX file creation uses owner-only permissions. Processes already able to edit the DB can forge or destroy evidence. |
| Worker → external service | External service is independent | An execute_once result is **not** a remote success receipt. Remote effects must be queried or independently verified before confirmation/retry. |
| CI → untrusted PR code | Untrusted changes may execute tests | Actions have read-only GitHub tokens, nonpersistent checkout credentials and pinned action revisions. Do not add secrets to PR-triggered jobs. |

## Findings and mitigations

1. **SQLite file disclosure (confirmed in a clean POSIX environment).** The original SQLite creation inherited umask 022, yielding a 0644 database. **Mitigation:** create new files with 0600, reject existing group/world-readable files, reject symlinked DB paths, check current-user ownership. A rollback journal was separately tested with owner-only permissions.
2. **Log/record injection and memory amplification through unbounded text (code review).** Long IDs or control characters could enter event records and local metadata. **Mitigation:** cap job IDs, step names, worker names and receipt keys at 256 printable characters; evidence references at 512; and step count at 1,024. Reject invalid lease duration and non-finite clocks.
3. **Concurrent lease race (tested).** Independent workers can attempt to claim the same job simultaneously. **Mitigation:** serialized BEGIN IMMEDIATE claims, explicit lease fencing and a simultaneous-claim regression test; only one worker may claim while its lease remains valid.
4. **GitHub Actions supply-chain and token scope (review).** Some workflows omitted explicit token permissions and used movable action tags. **Mitigation:** set contents: read, pin first-party checkout/setup-python actions to verified full commit SHAs, and disable credential persistence. A repository-wide regression check prevents policy drift.

These controls were tested against public demo fixtures. They do **not** imply that the system is safe against arbitrary same-account code execution.

## Follow-up hardening (2026-11-05)

- **Unexpected or incomplete SQLite schemas:** re-opening an existing database now validates its four known tables and columns, rejects unsupported schema versions, and does not silently recreate missing tables. Compatible legacy schema version 0 is checked before being marked version 1.
- **Corrupted persisted execution state:** before claiming or advancing a job, the engine verifies step ordering, allowed statuses, local/effect distinctions, receipt consistency and job completion. An unknown status never falls through to execution permission.
- **Multi-process contention:** five separately launched Python processes race for the same live job lease. The regression requires exactly one winner.
- **Path hardening:** reject hardlinked databases, symlinked parents, and directories owned by another user or writable by group/others. Recheck path metadata before every new connection.
- **Log-safety hardening:** reject bidirectional format characters and invisible Unicode control text in identifiers and evidence references.

These checks reduce accidental corruption and common filesystem abuse. They are not proof against a hostile process with the same account privileges, hostile code already executing inside the program, or a provider with ambiguous remote operation outcomes.

## JSON demonstration checkpoint integrity (2026-11-05)

The earlier simple JSON demo previously overwrote state directly and allowed `init` to overwrite an existing interrupted job. This could truncate state during an interrupted write or erase an effect receipt during reinitialization.

- Checkpoints now use a fsynced, same-directory temporary file and atomic replacement.
- Initial checkpoint creation uses an exclusive hard link, so an existing job is never clobbered.
- Existing checkpoint reads validate JSON structure with the public inspector, enforce a 1 MiB size limit and reject non-private/symlinked POSIX paths.
- The simulator requires a trusted local parent directory and creates checkpoint files with owner-only permissions.
- Dedicated tests cover interrupted receipt preservation, replacement failure, concurrent initializers from separate processes, corrupt state and unsafe file paths.

**Residual limitation:** the JSON demo remains deliberately **single-writer**. Atomic replacement is not a substitute for locking or database transactions. Concurrent workers that execute steps against one JSON file may still lose updates; use the separate SQLite engine for real concurrent claim tests. Windows requires caller-supplied private directory ACLs.

## Critical residual risks

- **No worker authentication:** a process with access to the SQLite database can still claim work or forge local evidence. Never expose this library as an unauthenticated remote service.
- **No external exactly-once guarantee:** a remote API may process a request even if the local process crashes. Fence tokens constrain local state changes, not an already-sent request. Use provider-supported idempotency and authoritative reconciliation.
- **Local evidence is not cryptographic proof:** external_evidence_ref is caller-supplied text. The library cannot verify its authenticity. Do not treat a string alone as confirmation.
- **Directory trust and TOCTOU:** the database must be stored in an owner-controlled directory, ideally mode 0700. The POSIX file-mode check cannot defend against a malicious peer able to rewrite/replace files in that directory after the check.
- **Clock behavior:** lease expiry uses wall-clock time. Large clock jumps can change ownership timing. Use a stable, trusted host clock; do not share a single SQLite DB over unreliable network filesystems.
- **Windows ACLs:** POSIX mode checks do not apply on Windows. Provision an ACL-limited private user directory before creating the database there.
- **Evidence privacy:** database records and snapshots are not encrypted. Store opaque, nonsecret references, not tokens, customer data, or complete API response bodies.
- **Static scanning:** a pinned CodeQL workflow now runs extended security queries for Python and JavaScript/TypeScript on pull requests, main pushes, and weekly. Only its SARIF upload receives `security-events: write`, while other workflows retain read-only permissions. This does not replace independent triage, secret scanning, or manual code review.
- **Supply-chain review remains necessary:** hashed dependency lockfiles, dedicated secret scanning, CodeQL, independent reviews, controlled packaging/release signing and stronger permission boundaries remain future work.

## Upgrading an old public-demo database

If an existing, **trusted** POSIX database fails with PermissionError, verify its owner and path first. Then, as its owning user, use chmod 700 on its parent private directory and chmod 600 on the SQLite file. Do not silently change permissions on an unknown or externally owned DB. Review any SQLite sidecar files and retain a backup before migration.

## Tests

From the demos/chat-long-turn-continuity/ directory, run:

    python3 -m unittest -v test_public_engine.py test_security_hardening.py

The security suite covers POSIX DB/journal permissions, unsafe existing files, symlinks, control-character and size limits, lease timestamps, and eight simultaneous claimers. CI also runs tools/test_workflow_security.py to enforce GitHub Actions policy.

**Security disclosure:** use the process in the repository-level SECURITY.md. Do not submit secrets, private topology, operational logs, or exploit details in public issues.
