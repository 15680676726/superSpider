# Governance

## Project model

`superSpider` is currently maintained under a maintainer-led model.

The repository owner and listed code owners decide:

- release timing
- merge and revert decisions
- architecture direction
- repository policy, moderation, and security handling

## How changes are proposed

- Small fixes can be sent directly as pull requests.
- Larger changes should start with an issue or discussion so the direction is
  explicit before implementation.
- Security-sensitive changes should follow [SECURITY.md](SECURITY.md).

## Becoming a maintainer

The project is open to adding more maintainers.

Contributors can be invited into the maintainer group after sustained,
high-signal work such as:

- repeated merged pull requests across runtime, state, tests, or docs
- good review quality and low-regression changes
- reliable follow-through on issues, release prep, or support load
- alignment with the repository architecture and contribution rules

Maintainer access is granted by the current maintainers. When the maintainer
group grows, code ownership and merge responsibility should move from a single
owner model toward a shared maintainer model.

## Decision rule

The project prefers explicit technical decisions over silent drift. When there
is disagreement, maintainers make the final merge decision based on repository
architecture, operational risk, and maintenance cost.

## Maintainers

Current code ownership is defined in [.github/CODEOWNERS](.github/CODEOWNERS).
