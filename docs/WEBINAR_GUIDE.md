# Guia do webinar — AD3 WhatsApp Evolution

## Antes de começar

Este guia opera o produto AD3 Digital em modo seguro por planos.

Nunca compartilhe QR, telefone de cliente, API key ou arquivo `.env`.

Tenha autorização para administrar cada conta e grupo.

O produto não torna WhatsApp, PC ou dados automaticamente conformes à LGPD.

Avalie sua base legal, retenção, acesso e atendimento a titulares com orientação apropriada.

## Requisitos do modo local

- Windows 10/11 x64 ou ARM64.
- Pelo menos 8 GB de RAM e 15 GB livres.
- Virtualização habilitada no firmware.
- WSL 2.1.5 ou superior.
- Docker Desktop iniciado.
- Porta 8080 livre.

O computador local precisa ficar ligado e acordado.

Se ele desligar, hibernar ou perder rede, a stack e o webhook local param.

## Três modos

`demo` é a sala de treino: não faz rede e só grava estado simulado local.

`remote` usa uma Evolution API já administrada por você.

`local` usa Docker no próprio computador, somente em `127.0.0.1`.

Comece sempre em demo.

## Verificar a entrega antes de extrair

A AD3 envia o SHA-256 individualizado em uma mensagem separada e autenticada.

Não aceite o hash copiado de dentro do ZIP nem de um arquivo recebido junto por um terceiro.

Antes de extrair ou executar qualquer arquivo do pacote:

```powershell
$zip = (Resolve-Path .\AD3-Agente-WhatsApp-Evolution-Codex-SEU-NOME.zip).Path
$expected = 'COLE_AQUI_O_SHA256_RECEBIDO_SEPARADAMENTE_DA_AD3'
if ($expected -notmatch '^[A-Fa-f0-9]{64}$') { throw 'SHA-256 de entrega invalido' }
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $expected.ToUpperInvariant()) { throw 'Pacote diferente da entrega AD3' }
$package = Join-Path $env:LOCALAPPDATA 'AD3EvolutionVerifiedPackage'
if (Test-Path $package) { throw 'Use uma pasta nova e vazia para a extracao' }
Expand-Archive -LiteralPath $zip -DestinationPath $package
```

Essa comparação acontece antes da extração e antes de qualquer EXE ou script do pacote.

Mantenha `$zip`, `$expected` e `$package` na mesma sessão para os comandos abaixo.

## Diagnóstico sem alterações

Somente depois da verificação acima, execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$package\install\Install-AD3Evolution.ps1" -Mode demo -Diagnose -PackageRoot $package
```

Sem `-Apply`, o instalador é dry-run e não cria arquivos.

O diagnóstico mostra RAM, disco, WSL, Docker, virtualização e porta.

## Instalar demo

O pacote distribuído precisa conter executável, manifesto de licença, skill, install, deploy e este guia.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$package\install\Install-AD3Evolution.ps1" -Mode demo -Apply -PackageRoot $package -PackageArchive $zip -ExpectedPackageSha256 $expected
```

Demo instala somente o pacote e a skill; não chama rede nem Docker.

Abra uma nova sessão do Codex depois da instalação da skill.

## Instalar remoto

Não coloque chave de API na linha de comando, histórico ou chat.

No modo interativo, a chave é solicitada como SecureString.

No modo não interativo, forneça somente para o processo atual:

```powershell
$env:AD3_REMOTE_API_KEY = 'valor-local-temporario'
powershell -File "$package\install\Install-AD3Evolution.ps1" -Mode remote -Apply -NonInteractive -PackageRoot $package -PackageArchive $zip -ExpectedPackageSha256 $expected -RemoteUrl https://sua-api.example -RemoteInstance creator
Remove-Item Env:AD3_REMOTE_API_KEY
```

O instalador grava `.env` com ACL restrita ao usuário atual.

## Instalar local

Leia os termos de WSL e Docker antes de aceitar.

```powershell
powershell -File "$package\install\Install-AD3Evolution.ps1" -Mode local -Apply -PackageRoot $package -PackageArchive $zip -ExpectedPackageSha256 $expected -InstallWSL -InstallDocker -AcceptTerms -Elevate
```

Se houver reboot, execute somente:

```powershell
powershell -File .\install\Install-AD3Evolution.ps1 -Resume
```

O marcador não contém API key e expira em 24 horas.

O marcador pode guardar o caminho do ZIP e o SHA-256 público da entrega para retomar com segurança.

Não rode `-Apply` repetidamente sem ler a mensagem anterior.

## Chats e grupos-template

Leituras nao criam plano nem gravam historico no estado local:

```powershell
ad3-evolution --mode demo chat list --instance creator --limit 20
ad3-evolution --mode demo chat messages --instance creator --jid JID --limit 20
```

Para um grupo-template (webinar, alunos ou cliente), crie e revise um plano:

```powershell
ad3-evolution --mode demo group setup-plan --instance creator --subject "Webinar" --description "Avisos" --picture https://arquivo.example/foto.png --phone 5511888888888 --participant-instance client --admin-instance support --setting announcement --setting locked
ad3-evolution --mode demo apply --plan-id ID --confirm ID
```

O plano cria o grupo uma vez e aplica foto, admins e settings, sem enviar
welcome ou qualquer mensagem. Se ficar `uncertain`, liste os grupos e reconcilie
por subject antes de criar outro plano; nunca tente replay automatico.

## Primeiro doctor

```powershell
& "$env:LOCALAPPDATA\AD3Evolution\ad3-evolution.exe" --mode demo doctor
```

A resposta deve mostrar `network: disabled` em demo.

Para usar configuração instalada, execute no diretório instalado ou defina `AD3_EVOLUTION_CONFIG` para o `.env` local.

## Regra de plan/apply

Toda mutação gera um plano e um hash.

Revise alvo, descrição, participantes e instância antes de aplicar.

```powershell
ad3-evolution --mode demo group create --instance creator --subject "Projeto piloto" --phone 5511999999999
ad3-evolution --mode demo apply --plan-id ID --confirm ID
```

Substitua `ID` pelo id exibido pelo primeiro comando.

Plano aplicado, expirado, em execução ou incerto não é repetido automaticamente.

Se um plano ficar incerto, investigue o estado no WhatsApp/Evolution antes de criar um novo.

## QR e instâncias

Conexão de QR depende de contrato explícito da Evolution API e autorização do proprietário.

Não fotografe ou encaminhe QR.

Não conecte uma conta pessoal sem autorização formal.

Use o diagnóstico e a documentação da instância antes do QR.

## Criar e editar grupo

Criar grupo:

```powershell
ad3-evolution --mode demo group create --instance creator --subject "Cliente - Projeto" --phone 5511888888888
```

Alterar nome:

```powershell
ad3-evolution --mode demo group update subject --instance creator --jid JID --value "Novo nome"
```

Alterar descrição:

```powershell
ad3-evolution --mode demo group update description --instance creator --jid JID --value "Canal de atendimento"
```

Alterar foto:

```powershell
ad3-evolution --mode demo group update picture --instance creator --jid JID --value "https://arquivo-autorizado.example/foto.png"
```

Revise cada plano e aplique com confirmação exata.

## Participantes e administradores

Adicionar:

```powershell
ad3-evolution --mode demo group update participants --instance creator --jid JID --action add --phone 5511888888888
```

Promover:

```powershell
ad3-evolution --mode demo group update participants --instance creator --jid JID --action promote --phone 5511777777777
```

Remover e rebaixar usam `--action remove` e `--action demote`.

Não promova uma instância sem validar seu owner `phoneNumber`.

## Convites, mensagens e blacklist

```powershell
ad3-evolution --mode demo group invite get --instance creator --jid JID
ad3-evolution --mode demo blacklist add --phone 5511999999999
ad3-evolution --mode demo message plan-text --instance creator --number JID --content "Bem-vindo"
```

Mídia requer tipo e conteúdo:

```powershell
ad3-evolution --mode demo message plan-media --instance creator --number JID --mediatype image --media BASE64_OU_URL --caption "Arquivo"
```

Não envie campanhas ou mensagens sem base autorizada e revisão humana.

## Onboarding

Creator, participantes e admins precisam ser instâncias distintas.

O cliente precisa ter `phoneNumber`; identidade somente `@lid` falha fechada.

```powershell
ad3-evolution --mode demo onboarding plan --creator-instance creator --participant-instance client --admin-instance support --client-phone 5511888888888 --group-name "Cliente Exemplo"
```

Use `--welcome-instance support` para escolher explicitamente a instância que envia a mensagem.

Em remoto, o fluxo valida WhatsApp, cria grupo, aplica metadados, adiciona/promove, confirma participante e só então envia boas-vindas.

## Backup, restore, update e uninstall

```powershell
.\install\Manage-AD3Evolution.ps1 -Action doctor
.\install\Manage-AD3Evolution.ps1 -Action backup -BackupFile C:\Users\Public\ad3-backup.zip
```

Restore é destrutivo e mantém a API parada se DB ou volume falhar:

```powershell
.\install\Manage-AD3Evolution.ps1 -Action restore -BackupFile C:\Users\Public\ad3-backup.zip -Confirm RESTORE
```

Atualização aceita apenas versão allowlisted:

```powershell
.\install\Manage-AD3Evolution.ps1 -Action update -Version v2.3.7
```

Uninstall preserva volumes; purge exige confirmação forte:

```powershell
.\install\Manage-AD3Evolution.ps1 -Action uninstall
.\install\Manage-AD3Evolution.ps1 -Action uninstall -Purge -Confirm PURGE-VOLUMES
```

## Troubleshooting

Se Docker não responder, abra Docker Desktop e espere o daemon.

Se 8080 estiver ocupada, encerre o serviço concorrente ou altere o Compose de forma revisada.

Se WSL estiver antigo, atualize WSL e retome com `-Resume`.

Se a instância não estiver conectada, não tente aplicar onboarding.

Se houver `uncertain`, não reenvie: confira grupo, participantes e mensagem primeiro.

Se o PC suspender, reabra Docker Desktop e rode doctor.

## Licença

A licença é pessoal, gratuita e não transferível conforme `LICENSE.md`.

Não redistribua, revenda, sublicencie ou publique o núcleo protegido.

O manifesto assinado deve acompanhar o executável.

Controles técnicos reduzem cópia indevida, mas não oferecem proteção absoluta.
