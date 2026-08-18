# Evolution 2.3.7 matrix

Chat read-only: `POST /chat/findChats/{instance}` com `{ "take": N }` e
`POST /chat/findMessages/{instance}` com `{ "where": { "key": {
"remoteJid": "JID" } }, "take": N }`. Templates usam `group setup-plan`;
settings chamam `group/updateSetting` com `action` igual a `announcement`,
`not_announcement`, `locked` ou `unlocked`.

Use only the explicit profile. Instance creation is `POST /instance/create` with `instanceName`, `integration: WHATSAPP-BAILEYS`, and `qrcode: true`; plan it with `instance create-plan`, then apply the returned id. Group list/info/invite reads use the selected instance and query parameters; group mutations are planned POST operations. QR base64 is never printed: request `--qr-file` inside the configured state directory.

Useful commands: `doctor`, `instance list`, `instance status --instance NAME`, `instance create-plan --instance NAME --qr-file PATH`, `group create`, `group update`, `message plan-text`, `message plan-media`, `blacklist`, and `onboarding plan`.
