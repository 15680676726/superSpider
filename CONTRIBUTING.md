# Contributing to superSpider

## Welcome

Thanks for contributing to `superSpider`.

Repository:
- GitHub: `https://github.com/15680676726/superSpider`
- Issues: `https://github.com/15680676726/superSpider/issues`
- Discussions: `https://github.com/15680676726/superSpider/discussions`
- Support: [SUPPORT.md](SUPPORT.md)
- Governance: [GOVERNANCE.md](GOVERNANCE.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

Current runtime package / CLI name remains `copaw`, so code, install commands, and tests still use that name.

## Mainline-first workflow

- The default development branch is `main`.
- Do not create feature branches, worktrees, or backup branches unless maintainers explicitly approve it for the task.
- Before calling work done, the change must be committed on `main`, pushed to `origin/main`, and the working tree must be clean.

## Local gate

Run the relevant checks before pushing:

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
pytest
```

If your change touches `console/` or `website/`, also run:

```bash
cd console && npm run format
cd website && npm run format
```

## Commit format

We use Conventional Commits:

```text
<type>(<scope>): <subject>
```

Examples:

```bash
feat(runtime): add executor recovery projection
fix(console): correct runtime center route handling
docs(readme): update open-source setup guidance
```

## Contribution scope

Good contributions include:

- bug fixes
- docs improvements
- test hardening
- frontend/runtime-center improvements
- capability, runtime, and evidence-chain cleanup aligned with the repository architecture

For larger changes, open or claim an issue first so the direction is explicit before implementation starts.

## Maintainer path

This repository is open to adding more maintainers over time. Sustained,
high-quality contributors may be invited into a maintainer role after repeated
merged work, reliable reviews, and consistent follow-through on issues or
release tasks.

## Documentation

- Update docs when user-visible behavior changes.
- Public-facing website docs live in `website/src/pages/Docs.tsx`.
- Internal engineering, migration, and architecture docs live under `docs/architecture/`.
- Retired public-site markdown and historical technical records live under `docs/archive/`.
- Architecture / migration work must keep the root planning and status docs in sync when applicable.

## Pull requests and reviews

- Keep changes focused.
- Do not mix unrelated changes into one PR or one commit.
- If pre-commit rewrites files, commit the rewritten result and rerun checks.

## Questions and support

- General discussion: `https://github.com/15680676726/superSpider/discussions`
- Bugs / feature requests: `https://github.com/15680676726/superSpider/issues`
