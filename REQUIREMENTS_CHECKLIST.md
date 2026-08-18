# Checklist de requisitos

- [x] CLI 0.3.1 com marca humana, ajuda sem estado e `donate` Pix offline
- [x] BR Code sem valor fixo, CRC16-CCITT e QR terminal com fallback ASCII
- [x] Banner/QR excluídos de capabilities, JSON legado e JSONL de batch

- [x] CLI 0.3.0: gates de número, participantes, convite por código e webhook 2.3.7
- [x] `invite_revoke` corrigido para POST com body; webhook mutante permanece plan/apply
- [x] Batch somente leitura inclui novas consultas sanitizadas; `@lid` restrito a histórico/leitura

- [x] CLI 0.2.0 com `--version`, `--pretty`, `capabilities` e lote agent-first JSON/JSONL
- [x] Protocolo `ad3-evolution.agent/v1` somente leitura, allowlist fixa, limites de 50 itens/1 MiB e redação
- [x] Respostas parciais JSONL, exit 2 em falha e visão `summary` para coleções em loops externos

- [x] Leitura read-only de chats e historico no perfil Evolution 2.3.7
- [x] Plano group_setup com validacao, reconciliacao e sem welcome automatico

- [x] CLI, demo/offline, planos SQLite, auditoria/redação/blacklist
- [x] Perfil Evolution 2.3.7 e matriz de rotas explícita
- [x] Onboarding com separação creator/admin e bloqueio `@lid`
- [x] Compose local fixado, localhost, healthchecks e volumes
- [x] Instalador/gerenciador PowerShell de análise estática
- [x] Skill, guia, licença, notices e release fail-closed
- [x] Testes locais e scripts de verificação
- [x] Backup ZIP e restore com confirmação textual; purge com confirmação forte
- [x] Release assinado, watermark, checksums e exclusão do núcleo fonte
- [x] Onboarding remoto resolve owners, valida phoneNumber e escolhe instância de welcome
