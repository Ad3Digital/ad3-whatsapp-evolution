# AD3 Agente WhatsApp Evolution para Codex

## Marca humana e Pix offline

Na versão 0.3.1, a execução sem argumentos, `--help` e `donate` são superfícies
humanas locais. Elas não carregam Config/Store. `donate` produz BR Code Pix sem
valor fixo e QR terminal offline via `qrcode` 8.2; `--no-color` usa ASCII.
Nenhuma dessas saídas entra em capabilities, comandos JSON legados ou JSONL.

## API integral 2.3.7

Na versão 0.4.0, `profiles.py` cataloga as 177 operações de cliente do tag
oficial 2.3.7. `api catalog` retorna ID, método, rota, parâmetros de caminho,
modo (`read`, `download`, `plan` ou `restricted`) e suporte a arquivo multipart.
O catálogo exclui callbacks de entrada, Manager e métricas, que são superfícies
do servidor. As duas rotas que retornam credenciais são listadas como
`restricted` e não recebem despacho de terminal.

`api read` executa somente as leituras explicitamente classificadas. A operação
de mídia Base64 usa `api download --output-file`, que grava o arquivo sem
imprimir seu conteúdo. `api plan` cobre as outras operações permitidas e
conserva o mesmo `apply` hashado, idempotência local e estado `uncertain` dos
comandos especializados. `--param` preenche somente placeholders declarados;
não existe URL, método ou dispatch arbitrário. Upload multipart registra caminho,
tamanho e SHA-256 no plano cifrado e a aplicação falha fechada se o arquivo
mudar. Saídas redigem Base64, token, chave, senha e autorização.

## Protocolo local para agentes v1

Na versão 0.3.0, a CLI inclui `ad3-evolution.agent/v1`: lote UTF-8 de objeto,
array JSON ou JSONL, limitado a 50 requisições e 1 MiB. Cada linha de resposta
tem `schema`, `id`, `ok` e `data` ou `error`. O protocolo usa uma allowlist
estática de leituras (`doctor`, instâncias, chats, grupos e status de plano),
valida todos os argumentos e redige toda saída. Não há dispatch de método,
import, shell, URL de entrada nem operação mutante. Falhas individuais produzem
resposta própria e o lote prossegue; ao menos uma falha resulta no exit code 2.

Coleções aceitam `view: "full" | "summary"`; resumo retorna contagem e, para
instâncias, contagem por estado e conexão. Isso reduz a resposta em loops externos sem
alterar a CLI legada. `capabilities` descreve o contrato compactamente e
`agent batch [--input-file PATH]` reutiliza a mesma instância Service/Store.

## Gates operacionais 2.3.7

A CLI oferece leitura normalizada de grupos, participantes, convite por código,
validação lógica de números e webhook. `invite_revoke` usa POST com body
`groupJid`, conforme a rota oficial. Webhook mutante permanece em plano e exige
URL HTTPS, salvo localhost/127.0.0.1; não aceita query, fragmento, userinfo ou
headers nesta versão. A leitura de webhook é sanitizada. Histórico de chat aceita
somente JID de grupo, individual ou `@lid`, e `@lid` não pode entrar em mutações.

## Chats e grupos-template

Leitura usa somente `POST /chat/findChats/{instance}` e
`POST /chat/findMessages/{instance}` do perfil 2.3.7. Estas operacoes nao criam
planos nem persistem historico no SQLite/auditoria.

`group_setup` e um plano explicito para templates webinar, alunos e cliente.
Ele valida creator, instancias, telefones, blacklist e settings e nunca envia
mensagem. Falha apos criar o grupo deixa o plano `uncertain`; liste e reconcilie
por subject antes de criar um novo plano.

CLI Python stdlib-first, com `demo` offline, `remote` para API existente e `local` para Compose local. Mutação só ocorre com plano hashado e confirmação exata; tanto os comandos focados quanto o catálogo integral usam o perfil explicitamente preso a Evolution 2.3.7 e não possuem fallback mutante.

Onboarding exige creator separado, conexão, número de telefone do cliente e falha fechada para `@lid` sem telefone. Rollback é limitado a operações objetivamente seguras e nunca promete apagar mensagens.

Rastreabilidade: `profiles.py` mantém os contratos focado e integral 2.3.7; `client.py` resolve somente rotas catalogadas e multipart; `service.py` aplica planos e onboarding; `store.py` guarda auditoria/idempotência; `install/` é a superfície Windows; `deploy/local/compose.yaml` é a stack; `tests/` cobre a simulação, contrato e gates de segurança.
