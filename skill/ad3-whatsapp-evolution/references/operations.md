# Operações v0.3.0

Perfil suportado: Evolution 2.3.7. Configure remote/local somente por ambiente
ou `.env` local; não coloque segredos na linha de comando.

`donate --no-color` é uma saída humana Pix offline da versão 0.3.1. Não a use
em automações, capabilities ou `agent batch`.

## Leituras e gates

```powershell
ad3-evolution instance list
ad3-evolution number check --instance X --number N
ad3-evolution group participants --instance X --jid JID
ad3-evolution group invite resolve --instance X --code CODE
ad3-evolution webhook get --instance X
```

`number check` valida números antes de uma rotina. Participantes permitem
conferir admins e a presença de `phoneNumber`; uma identidade somente `@lid`
não autoriza mutação. Histórico de chat aceita grupo, JID individual e `@lid`
apenas para leitura.

Webhook get é sanitizado. Set-plan exige HTTPS, salvo `localhost`/`127.0.0.1`,
rejeita query, fragmento, userinfo e headers nesta versão, e aceita somente os
eventos oficiais do perfil.

## Protocolo de agente

```powershell
@'
{"id":"instances","op":"instance.list","args":{"view":"summary"}}
{"id":"numbers","op":"number.check","args":{"instance":"X","numbers":["N"]}}
'@ | ad3-evolution agent batch
```

O lote aceita JSON, array ou JSONL UTF-8, no máximo 50 itens e 1 MiB. Ele é
read-only; uma falha gera resposta própria e exit 2, sem interromper os demais
itens. Use `capabilities` antes de montar um cliente de loop.

## Mutações

Criação/configuração de grupo, mudanças de participantes/admins/settings,
convites mutantes, mensagem, onboarding e webhook usam `plan` e `apply`. Não
faça retry de plano incerto; reconcilie o estado antes de novo plano.

```powershell
ad3-evolution group setup-plan --instance X --subject "Grupo exemplo"
ad3-evolution apply --plan-id ID --confirm ID
```

Agendamento continua no wrapper externo. CRM e NocoDB não fazem parte desta CLI
e podem compor os resultados de leitura externamente.
