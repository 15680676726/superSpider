# Security Policy

If you believe you've found a security issue in `superSpider`, report it privately first.

## Reporting

Preferred channel:

- GitHub Security Advisory: `https://github.com/15680676726/superSpider/security`

If GitHub Security Advisories are unavailable for your report, open an issue only for non-sensitive problems:

- Issues: `https://github.com/15680676726/superSpider/issues`

Do not post secrets, credentials, private PoCs, or exploit details in a public issue.

## Include in a report

Please include:

1. title
2. affected version / commit
3. impacted component
4. reproduction steps
5. demonstrated impact
6. environment details
7. suggested remediation, if available

## Trust model

`superSpider` is designed as a trusted local execution system, not a hostile multi-tenant SaaS boundary.

- Operators sharing the same runtime/config are inside one trust boundary.
- Skills and local extensions are treated as trusted code for that runtime.
- Prompt injection alone is not a valid security report unless it crosses a documented auth, sandbox, or policy boundary.

## Out of scope

The following are generally out of scope:

- reports that require trusted local file/config write access
- behavior that depends on a user intentionally enabling a dangerous capability
- malicious behavior from trusted-installed skills without a boundary bypass
- unsupported multi-tenant assumptions on one shared local instance

## Operational guidance

- keep secrets out of the working directory when possible
- isolate mixed-trust users by host, OS user, or fully separate runtime
- run with least privilege
- review enabled skills and capability mounts regularly

## Documentation

Operational guidance and setup details live in:

- [README](README.md)
- public website docs: `website/src/pages/Docs.tsx`
- internal architecture docs: `docs/architecture/`
