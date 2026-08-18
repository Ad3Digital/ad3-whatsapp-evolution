# Mapa de prompts v0.3.0

| Intenção | Rota segura |
| --- | --- |
| Marca ou doação humana | Sem argumentos/`--help`; `donate --no-color`, nunca JSON/JSONL |
| Ver capacidade e montar loop | `capabilities`; `agent batch` read-only com JSON/JSONL |
| Monitorar sem volume | `instance.list` com `view: "summary"` |
| Validar destino | `number check --instance X --number N` |
| Consultar histórico | `chat messages --instance X --jid JID`; grupo, individual e `@lid` só em leitura |
| Conferir grupo antes/depois | `group info` e `group participants` |
| Resolver código de convite | `group invite resolve --instance X --code CODE` |
| Criar ou configurar grupo | `group create` ou `group setup-plan`, então `apply` |
| Alterar membros, admins ou settings | Comando legados de plano, então `apply` |
| Mensagem imediata | `message plan-text` ou `message plan-media`, então `apply` |
| Onboarding | `onboarding plan`, revisar e `apply` |
| Consultar webhook | `webhook get --instance X` sanitizado |
| Configurar webhook | `webhook set-plan`, revisar e `apply` |
| Agendar rotina | Wrapper externo autorizado, nunca batch |

Não exponha telefones, URLs de webhook, QR, API keys ou dados de CRM. Não inclua
mutações no batch e não faça retry cego após plano incerto. CRM/NocoDB compõem
fora da CLI.
