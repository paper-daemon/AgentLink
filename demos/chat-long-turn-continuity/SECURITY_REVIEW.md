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

## Critical residual risks

- **No worker authentication:** a process with access to the SQLite database can still claim work or forge local evidence. Never expose this library as an unauthenticated remote service.
- **No external exactly-once guarantee:** a remote API may process a request even if the local process crashes. Fence tokens constrain local state changes, not an already-sent request. Use provider-supported idempotency and authoritative reconciliation.
- **Local evidence is not cryptographic proof:** external_evidence_ref is caller-supplied text. The library cannot verify its authenticity. Do not treat a string alone as confirmation.
- **Directory trust and TOCTOU:** the database must be stored in an owner-controlled directory, ideally mode 0700. The POSIX file-mode check cannot defend against a malicious peer able to rewrite/replace files in that directory after the check.
- **Clock behavior:** lease expiry uses wall-clock time. Large clock jumps can change ownership timing. Use a stable, trusted host clock; do not share a single SQLite DB over unreliable network filesystems.
- **Windows ACLs:** POSIX mode checks do not apply on Windows. Provision an ACL-limited private user directory before creating the database there.
- **Evidence privacy:** database records and snapshots are not encrypted. Store opaque, nonsecret references, not tokens, customer data, or complete API response bodies.
- **Supply-chain review remains necessary:** hashed dependency lockfiles, dedicated secret scanning, CodeQL, independent reviews, controlled packaging/release signing and stronger permission boundaries remain future work.

## Upgrading an old public-demo database

If an existing, **trusted** POSIX database fails with PermissionError, verify its owner and path first. Then, as its owning user, use chmod 700 on its parent private directory and chmod 600 on the SQLite file. Do not silently change permissions on an unknown or externally owned DB. Review any SQLite sidecar files and retain a backup before migration.

## Tests

From the demos/chat-long-turn-continuity/ directory, run:

    python3 -m unittest -v test_public_engine.py test_security_hardening.py

The security suite covers POSIX DB/journal permissions, unsafe existing files, symlinks, control-character and size limits, lease timestamps, and eight simultaneous claimers. CI also runs tools/test_workflow_security.py to enforce GitHub Actions policy.

**Security disclosure:** use the process in the repository-level SECURITY.md. Do not submit secrets, private topology, operational logs, or exploit details in public issues.
