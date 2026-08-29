# Matriz Evolution 2.3.7

O CLI mantém os comandos especializados para instâncias, chats, grupos,
mensagens, onboarding e webhook. Para a superfície integral, use `api catalog`;
ele lista 177 operações de cliente do tag 2.3.7, com método, rota e o gate
`read`, `download`, `plan` ou `restricted`.

`api read` só executa leituras aprovadas. A mídia Base64 usa `api download` com
arquivo de destino e não é impressa. Itens `restricted` retornam credenciais e
não recebem despacho. `api plan` cobre qualquer outra operação permitida,
preserva a confirmação por ID e nunca aceita URL, método ou rota livres.
Identificadores adicionais usam `--param NOME=VALOR`; endpoints multipart usam
`--file` e verificam o hash do arquivo antes da aplicação.

Callbacks de entrada, Manager e métricas pertencem ao servidor e ficam fora da
CLI.
