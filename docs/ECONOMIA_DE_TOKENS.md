# Economia de saída para agentes de IA

## Hipótese

Quando um loop precisa apenas de estado agregado, `agent batch` com
`view: "summary"` deve transferir menos contexto do que uma resposta completa da
mesma operação. O protocolo não calcula tokens nem custo: ele entrega uma saída
estruturada menor.

## Medição registrada

Em 2026-08-18, uma leitura autorizada de `instance.list` com oito instâncias
produziu 11.160 caracteres na saída completa compacta e 157 caracteres no batch
com summary.

```text
economia de caracteres = 11.160 - 157 = 11.003
redução percentual = 11.003 / 11.160 × 100 = 98,6%
razão de tamanho = 11.160 / 157 ≈ 71,1
```

Não publicamos nomes, telefones, URLs, estados individuais, segredos nem a saída
bruta da medição.

## Reprodução genérica

Use uma instância de teste autorizada e compare a quantidade de caracteres da
saída compacta com a resposta summary do mesmo conjunto de dados:

```powershell
ad3-evolution instance list | Measure-Object -Character
@'
{"id":"instances","op":"instance.list","args":{"view":"summary"}}
'@ | ad3-evolution agent batch | Measure-Object -Character
```

Mantenha o mesmo modo, instância, momento e conjunto de dados nas duas leituras.
Não registre nem publique a saída completa se ela contiver dados operacionais.

## Limitações

Caracteres são uma medida reproduzível de tamanho de saída. Tokens e custo não
são lineares em caracteres e variam por modelo, tokenizador, preço, idioma e
contexto do agente. Portanto, esta página não afirma economia em reais nem um
número exato de tokens.
