# Security and Disclosure Policy

AgentLink is early-stage infrastructure research / product development. The production core is private.

## Public repository boundary

This showcase repository must not contain:

- passwords, API keys, tokens, cookies, or credentials
- private URLs, VPN addresses, internal hostnames, or private network topology
- customer or user data
- authentication bypass instructions
- detailed production authorization internals
- production source copied from the private core without explicit review

## Execution philosophy

Agent execution should follow least-authority principles. Sensitive operations may require stronger controls than ordinary read-only or reversible actions.

Important categories include:

- legal commitments
- financial transactions
- identity / KYC actions
- irreversible deletion or publication
- privileged infrastructure changes
- sensitive personal or customer data access

## Public continuity engine security notes

The independently MIT-licensed public continuity demo has a focused [security review](./demos/chat-long-turn-continuity/SECURITY_REVIEW.md) with its trust boundaries and residual risks. It provides no remote worker authentication, external-effect guarantee or general-purpose secret store. The private production AgentLink runtime is **not** covered by the public review.

## Automated public Git secret scanning

The public repository scans incoming changes on pull requests and pushes with the pinned Gitleaks Action. **Every workflow run also performs an independent full-history scan of all fetched Git refs**, using Gitleaks CLI with an official release archive verified by SHA-256. The workflow fetches full Git history and runs on PRs, pushes, a weekly schedule, and manual dispatch. The scanner uses redaction and does not post findings as pull request comments, job summaries, or downloadable results artifacts. The workflow only receives read-only repository permissions.

If a leak is suspected, **do not paste the value into a public issue or comment**. Revoke and rotate the affected credential immediately, assess exposure and connected systems, and use private disclosure. Deleting a file in a new commit does not remove the prior secret from history. History rewrites need coordination with all collaborators and cannot replace credential rotation. No scanner guarantees detection of every secret.

The scanner is limited to the **public repository** and does not examine the private AgentLink production core or its local deployments.

## Reporting a security issue

Do not publish a suspected vulnerability in a public GitHub Issue if it contains exploit details or sensitive information. Contact the project owner privately through the GitHub profile until a dedicated security contact is published.

## No security guarantee

Nothing in this repository should be interpreted as a certification, audit, or guarantee that AgentLink is suitable for production security-sensitive workloads today. Security hardening, formal threat modeling, and independent review are part of the development roadmap.