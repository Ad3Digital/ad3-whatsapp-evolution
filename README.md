# AD3 WhatsApp Evolution CLI

Uma CLI local para operações seguras com Evolution API 2.3.7, feita para
reduzir a saída e o contexto consumido por agentes de IA. A versão 0.4.0
mantém os comandos focados e acrescenta o catálogo integral do perfil para
operações avançadas sem abrir despacho HTTP arbitrário.

## Economia de saída para agentes

Medição autorizada em 2026-08-18, sobre a mesma operação `instance.list` com
oito instâncias. Nenhum nome, telefone, URL, estado individual ou dado bruto é
publicado.

| Saída | Caracteres | Resultado |
| --- | ---: | --- |
| Completa compacta | 11.160 | Referência legada |
| `agent batch` com `view: "summary"` | 157 | 11.003 caracteres a menos |
| Redução | 98,6% | Saída cerca de 71,1x menor |

[Metodologia, cálculo e limites](docs/ECONOMIA_DE_TOKENS.md). Caracteres são a
medida reproduzível desta comparação. Tokens e custo exato variam conforme o
modelo, tokenizador e preço usados pelo agente.

## Quick start

Requer Python 3.11 ou posterior.

```powershell
py -3 -m pip install -e .
ad3-evolution --mode demo doctor
ad3-evolution capabilities
ad3-evolution api catalog --prefix message.
```

O modo `demo` é offline. Para `remote` ou `local`, configure ambiente ou `.env`
local; nunca passe chave de API pela linha de comando.

```text
AD3_EVOLUTION_MODE=remote
EVOLUTION_BASE_URL=http://127.0.0.1:8080
EVOLUTION_API_KEY=definida-no-ambiente-local
```

## API integral 2.3.7

`api catalog` expõe as 177 operações de cliente do tag oficial 2.3.7, com
método, rota, parâmetros de caminho, suporte a upload/download e modo de
execução. Callbacks de entrada, Manager e métricas pertencem ao servidor e não
aparecem como comandos de cliente. Duas rotas que devolvem credenciais ficam
catalogadas como `restricted`, mas não são despachadas pela CLI.

Use `api read` somente para operações marcadas como `read`; ele aceita payload
e query como objeto JSON. O único item marcado como `download` grava a mídia
Base64 diretamente em arquivo, sem expor o conteúdo no terminal. Toda operação
marcada como `plan`, inclusive envio, configuração, exclusão e rotas de baixo
nível, gera um plano hashado e só sai após `apply` com o mesmo ID.

```powershell
ad3-evolution api read --operation chat.find-contacts --instance aula --payload-file .\find-contacts.json
ad3-evolution api download --operation chat.get-base64-from-media-message --instance aula --payload-file .\media.json --output-file .\media.bin
ad3-evolution api plan --operation message.send-poll --instance aula --payload-file .\poll.json
ad3-evolution apply --plan-id ID --confirm ID
```

Rotas com identificador adicional usam `--param NOME=VALOR`. Para os cinco
endpoints de mídia multipart, passe `--file`; o plano registra hash e tamanho
do arquivo e recusa a aplicação se o arquivo mudar. Prefira `--payload-file`
UTF-8 para dados sensíveis, pois `--payload` fica exposto ao histórico do
shell. Respostas com Base64, token, chave, senha ou autorização são redigidas
antes de qualquer saída.

Os payloads continuam iguais aos do contrato oficial. O catálogo deliberadamente
não cria uma segunda sintaxe por endpoint: isso mantém a cobertura completa sem
inventar campos nem permitir URL ou método arbitrários.


## Protocolo para agentes

`capabilities` descreve deterministicamente o protocolo
`ad3-evolution.agent/v1`. O lote aceita um objeto JSON, array JSON ou JSONL
UTF-8, com até 50 itens e 1 MiB. A allowlist é somente leitura; erros de um item
não impedem as respostas dos demais e resultam em exit 2.

```powershell
@'
{"id":"health","op":"doctor","args":{}}
{"id":"instances","op":"instance.list","args":{"view":"summary"}}
'@ | ad3-evolution --mode demo agent batch
```

Mecanismos que reduzem contexto e aumentam previsibilidade:

- `view: "summary"` para coleções;
- allowlist read-only, sem dispatch dinâmico;
- JSONL para lotes e loops externos;
- `capabilities` compactas e determinísticas;
- redação de telefone/segredo e sanitização de webhook;
- ausência de banner, QR ou Pix em capabilities, JSON legado e JSONL.

O scheduler fica fora da CLI e do batch. CRM e NocoDB podem compor essas leituras
externamente.

## Segurança operacional

Toda mutação continua em `plan`/`apply`: revise ID, hash e alvo, então confirme
com o mesmo ID. Planos usados, vencidos ou incertos não recebem retry cego.
Criação/configuração de grupos, participantes, admins, settings, mensagens,
onboarding e webhook seguem esse fluxo. `@lid` só é aceito em leituras de chat;
mutações exigem telefone válido.

`webhook get` retorna estado, eventos, flags, origem e hash do destino, sem URL
integral, query, userinfo ou headers. O protocolo também oferece `number.check`,
`group.participants` e `group.invite.resolve` como gates de leitura.

## Interface humana e doação

Sem argumentos e com `--help`, a CLI mostra **EVOLUTION AD3 DIGITAL** e a frase
de que foi feita para economizar tokens de agentes de IA. `donate --no-color`
mostra QR Pix offline em ASCII. Essa saída humana não se mistura à superfície de
máquina.

## Verificação

```powershell
py -3 -m unittest discover -s tests -v
py -3 scripts\verify.py
py -3 scripts\quick_validate.py
```

## Licença

O código-fonte fica visível neste repositório público, sob licença proprietária
AD3 Digital. Visualização e forks dentro do GitHub seguem os termos do serviço;
não há concessão de uso comercial, redistribuição externa ou oferta como serviço
sem autorização escrita. Leia [LICENSE.md](LICENSE.md).
