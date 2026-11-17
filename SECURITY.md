# Security policy

## Supported versions

Only the latest minor release of pytemplate-uv receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub security advisories](https://github.com/yuxuzi/pytemplate-uv/security/advisories/new).
Do not open a public issue for a vulnerability.

Include the pytemplate-uv version, the command or request that triggers the problem, and the
impact you expect. You can expect an acknowledgement within a week.

## Scope

In scope: the generator (path handling, template pack safety checks, rendering), the published
package and its release process, and the files the bundled templates generate when they create an
insecure default.

Out of scope: vulnerabilities in the dependencies of a generated project (report them upstream),
and the contents of third-party template packs.
