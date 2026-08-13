# Security Policy

## Supported versions

Security fixes are applied to the latest released version of GELA. Older builds
may be asked to upgrade before a report is investigated.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Contact Softcurse Systems
privately through https://softcurse-website.pages.dev/ and include:

- affected version and Windows version;
- reproducible steps or a minimal proof of concept;
- expected impact; and
- whether any credentials or personal data may have been exposed.

Please allow reasonable time for investigation and a coordinated fix before
public disclosure.

## Security boundaries

GELA executes only registered commands and catalog targets after its wake gate.
Hardware integrations must authenticate the paired device, validate every
message, enforce an allowlist on the Windows host, and never expose a general
shell or arbitrary command endpoint. Do not commit private keys, tokens, code-
signing certificates, personal catalogs, logs, or speech recordings without the
speaker's explicit publication consent.
