# Ponte MCP privada para o ChatGPT

Esta ponte chama a CLI `ad3-evolution` existente. Oferece listagem de instâncias,
chats, mensagens e envio de texto em duas etapas (`plan_text` e
`send_approved_plan`). Não contém credenciais nem despacha rotas arbitrárias.

## Executar na máquina onde a CLI já funciona

Requer Python 3.11+ e a CLI configurada para Evolution. Instale o SDK MCP no
mesmo ambiente: `python -m pip install 'mcp>=1.0,<2'`. Execute
`python -m mcp_bridge.server` a partir da raiz do repositório. O serviço escuta
somente em `127.0.0.1:8765/mcp` por padrão. Defina `AD3_MCP_PORT` se necessário.
`AD3_EVOLUTION_CLI` pode apontar para o executável da CLI.

Para conectar no ChatGPT em modo desenvolvedor, use o **Secure MCP Tunnel** para
alcançar este endpoint privado. Não encaminhe a porta publicamente sem antes
implementar autenticação MCP com controle de acesso individual para você e Dani.
Uma instalação separada por pessoa também exige autorização no servidor, não
apenas a seleção do plugin na interface.

Teste primeiro com `AD3_EVOLUTION_MODE=demo`, sem WhatsApp real. Confirme que
`list_instances` e `list_chats` respondem, depois teste `plan_text` e revise o
alvo e o texto. `send_approved_plan` só deve ser invocado após confirmação
explícita do usuário sobre aquele plano. Não repita `apply` automaticamente.

O servidor não foi implantado na VPS nem conectado a contas ChatGPT por este
repositório. Nenhuma chave deve ser enviada ao GitHub.
