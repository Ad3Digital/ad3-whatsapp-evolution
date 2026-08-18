# Provisionamento de instância 2.3.7

Use somente plano/aplicação explícitos para criar instância. O contrato usa `POST /instance/create`, header `apikey`, `instanceName`, `integration: WHATSAPP-BAILEYS` e `qrcode: true`. Há divergência documentada entre `Integration` e `integration`; o cliente deve preferir lowercase e testar em fake antes de compatibilidade dupla. QR pode retornar pairing code/base64; nunca registre base64 completo. A instalação local permanece fail-closed até o fluxo CLI possuir plano explícito para criação e conexão.
