---
name: ad3-whatsapp-evolution
description: Planeja e opera com segurança grupos, instâncias, mensagens, gates de leitura e onboarding do WhatsApp via Evolution API 2.3.7 para AD3 Digital.
---

# AD3 WhatsApp Evolution

Use a CLI local `ad3-evolution` no diretório do projeto. Comece em modo demo,
que é offline e altera somente o SQLite local:

```powershell
ad3-evolution --mode demo doctor
ad3-evolution capabilities
```

A versão 0.3.1 mostra a marca humana `EVOLUTION AD3 DIGITAL` sem argumentos ou
com `--help`. `donate --no-color` renderiza um QR Pix offline em ASCII; isso não
carrega estado e não deve ser misturado a saídas JSON/JSONL.

`capabilities` descreve o protocolo `ad3-evolution.agent/v1`. `agent batch`
aceita um objeto JSON, array JSON ou JSONL UTF-8, e expõe somente leituras. Use
`view: "summary"` em coleções para loops externos de baixo custo. O batch nunca
aceita apply, envio, criação, update, convite mutante, blacklist ou onboarding.

```powershell
'{"id":"health","op":"doctor","args":{}}' |
  ad3-evolution --mode demo agent batch
```

Leituras diretas incluem `number check --instance X --number N`, `group
participants --instance X --jid JID`, `group invite resolve --instance X --code
CODE` e `webhook get --instance X`. A leitura de webhook devolve somente flags,
eventos, origem e hash do destino; ela nunca mostra URL completo, query, headers
ou credenciais.

`chat messages` aceita JID de grupo, JID individual `@s.whatsapp.net` e `@lid`
somente para leitura. Não use `@lid` como número, destinatário mutante ou dado de
onboarding: operações mutantes exigem telefone válido.

Toda mutação continua em plano e confirmação exata. Revise ID, hash e alvo antes
de `apply --plan-id ID --confirm ID`. Planos usados, vencidos ou incertos não
recebem retry cego. Isso inclui criação/configuração de grupos, participantes,
admins, settings, convites mutantes, mensagens, onboarding e `webhook set-plan`.

```powershell
ad3-evolution webhook set-plan --instance X --url https://hooks.example.test/inbound --event MESSAGES_UPSERT
ad3-evolution apply --plan-id ID --confirm ID
```

O scheduler fica fora do batch e da CLI; use o wrapper externo autorizado. CRM e
NocoDB também compõem externamente esses gates. Nunca cole API keys, QR,
telefones completos ou dados de clientes em logs. Consulte [operações](references/operations.md),
[mapa de prompt](references/prompt-map.md) e a [matriz 2.3.7](references/route-matrix.md).
