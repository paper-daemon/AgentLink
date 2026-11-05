## Why

Explain the observable problem or test gap in 2-3 sentences. Link the issue if one exists.

## Changes

- 
- 

## Scope and public/private boundary

- [ ] The changed code/docs are public and explicitly licensed for contribution.
- [ ] No private AgentLink production code, URLs, credentials, personal data, operational logs or network topology were copied.
- [ ] I checked the affected directory's license instead of assuming a repository-wide license.

## Verification

Describe the **exact command(s)** run and results. If tests were not run, state why.

```text
# command and brief outcome
```

- [ ] I checked the regression/failure mode I am changing.
- [ ] I verified the existing public-demo behavior remains correct.
- [ ] New tests are deterministic and do not call production services.

## Safety contract

- [ ] An ambiguous external outcome is not treated as a failed request or blindly retried.
- [ ] Authentication, approval, and cooldown boundaries are not bypassed.
- [ ] I am not claiming real-world exactly-once behavior, remote worker authentication, or security certification without independent evidence.

If a checkbox does not apply, write **N/A** and explain briefly. Do not paste secrets or vulnerability details here; use the private reporting route in [SECURITY.md](../SECURITY.md).

## Notes for reviewers

Anything that could surprise a maintainer, including compatibility, migration, unsupported operating systems, test limitations, or follow-up work?
