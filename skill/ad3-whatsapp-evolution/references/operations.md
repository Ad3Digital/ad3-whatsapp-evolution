# Operações v0.4.0

Perfil suportado: Evolution 2.3.7. Configure remote/local somente por ambiente
ou `.env` local; não coloque segredos na linha de comando.

`donate --no-color` é uma saída humana Pix offline da versão 0.4.0. Não a use
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

## Catálogo integral

```powershell
ad3-evolution api catalog --prefix message.
ad3-evolution api read --operation chat.find-contacts --instance X --payload-file .\consulta.json
ad3-evolution api download --operation chat.get-base64-from-media-message --instance X --payload-file .\media.json --output-file .\media.bin
ad3-evolution api plan --operation message.send-poll --instance X --payload-file .\enquete.json
ad3-evolution apply --plan-id ID --confirm ID
```

O catálogo contém as 177 operações de cliente do tag oficial 2.3.7. Cada item
informa se é leitura direta (`read`), download seguro (`download`), plano
(`plan`) ou restrito (`restricted`). Os dois itens restritos devolvem credenciais
e não recebem despacho. `--param NOME=VALOR` preenche identificadores adicionais
da rota. Os cinco endpoints de mídia multipart aceitam `--file`; o plano confere
SHA-256 e tamanho do arquivo antes do envio. A mídia Base64 é gravada por
`api download` e nunca aparece no terminal. Callbacks de entrada, Manager e
métricas não são comandos de cliente.


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
