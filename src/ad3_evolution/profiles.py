"""Version-pinned outbound Evolution API 2.3.7 contract."""
from __future__ import annotations

from dataclasses import dataclass
import re

EVOLUTION_2_3_7 = "evolution-2.3.7"
UPSTREAM_TAG = "2.3.7"
UPSTREAM_SOURCE = "https://github.com/evolution-foundation/evolution-api/tree/2.3.7"


@dataclass(frozen=True)
class ApiOperation:
    method: str
    path: str
    read_only: bool
    upload_file: bool = False
    download_file: bool = False
    restricted: bool = False


# Existing focused commands retain their stable operation identifiers.
ROUTES = {
    "instance_create": ("POST", "/instance/create"),
    "instance_list": ("GET", "/instance/fetchInstances"),
    "instance_status": ("GET", "/instance/connectionState/{instance}"),
    "chat_list": ("POST", "/chat/findChats/{instance}"),
    "message_history": ("POST", "/chat/findMessages/{instance}"),
    "instance_qr": ("GET", "/instance/connect/{instance}"),
    "group_list": ("GET", "/group/fetchAllGroups/{instance}"),
    "group_info": ("GET", "/group/findGroupInfos/{instance}"),
    "group_participants": ("GET", "/group/participants/{instance}"),
    "invite_info": ("GET", "/group/inviteInfo/{instance}"),
    "group_create": ("POST", "/group/create/{instance}"),
    "whatsapp_validate": ("POST", "/chat/whatsappNumbers/{instance}"),
    "group_subject": ("POST", "/group/updateGroupSubject/{instance}"),
    "group_description": ("POST", "/group/updateGroupDescription/{instance}"),
    "group_picture": ("POST", "/group/updateGroupPicture/{instance}"),
    "participants_add": ("POST", "/group/updateParticipant/{instance}"),
    "participants_remove": ("POST", "/group/updateParticipant/{instance}"),
    "participants_promote": ("POST", "/group/updateParticipant/{instance}"),
    "participants_demote": ("POST", "/group/updateParticipant/{instance}"),
    "group_settings": ("POST", "/group/updateSetting/{instance}"),
    "invite_get": ("GET", "/group/inviteCode/{instance}"),
    "invite_revoke": ("POST", "/group/revokeInviteCode/{instance}"),
    "invite_send": ("POST", "/group/sendInvite/{instance}"),
    "group_leave": ("DELETE", "/group/leaveGroup/{instance}"),
    "send_text": ("POST", "/message/sendText/{instance}"),
    "send_media": ("POST", "/message/sendMedia/{instance}"),
    "webhook_find": ("GET", "/webhook/find/{instance}"),
    "webhook_set": ("POST", "/webhook/set/{instance}"),
}
IDEMPOTENT = {
    "instance_list",
    "instance_status",
    "instance_qr",
    "chat_list",
    "message_history",
    "group_list",
    "group_info",
    "group_participants",
    "invite_info",
    "whatsapp_validate",
    "invite_get",
    "webhook_find",
}
MUTATING = set(ROUTES) - IDEMPOTENT

# Leituras que varrem a conta inteira nao cabem no timeout padrao: numa conta com
# muitos grupos, `fetchAllGroups` estoura os 10s, as tres tentativas de leitura
# repetem o estouro e o operador recebe uma falha generica depois de meio minuto.
# O piso vale por operacao; um `EVOLUTION_TIMEOUT` maior continua prevalecendo.
SLOW_READS = {
    "group_list": 90.0,
    "group.fetch-all": 90.0,
    "chat_list": 30.0,
    "chat.find-chats": 30.0,
    "message_history": 30.0,
    "chat.find-messages": 30.0,
}


# Every client-callable route from the upstream 2.3.7 tag. Inbound webhook
# receivers, the Manager UI, and metrics are server surfaces, not CLI calls.
API_OPERATIONS = {
    "server.health": ApiOperation("GET", "/", True),
    "server.verify-credentials": ApiOperation("POST", "/verify-creds", False, False, False, True),

    "instance.create": ApiOperation("POST", "/instance/create", False),
    "instance.restart": ApiOperation("POST", "/instance/restart/{instance}", False),
    "instance.connect": ApiOperation("GET", "/instance/connect/{instance}", False),
    "instance.connection-state": ApiOperation("GET", "/instance/connectionState/{instance}", True),
    "instance.fetch": ApiOperation("GET", "/instance/fetchInstances", True),
    "instance.set-presence": ApiOperation("POST", "/instance/setPresence/{instance}", False),
    "instance.logout": ApiOperation("DELETE", "/instance/logout/{instance}", False),
    "instance.delete": ApiOperation("DELETE", "/instance/delete/{instance}", False),

    "message.send-template": ApiOperation("POST", "/message/sendTemplate/{instance}", False),
    "message.send-text": ApiOperation("POST", "/message/sendText/{instance}", False),
    "message.send-media": ApiOperation("POST", "/message/sendMedia/{instance}", False, True),
    "message.send-ptv": ApiOperation("POST", "/message/sendPtv/{instance}", False, True),
    "message.send-whatsapp-audio": ApiOperation("POST", "/message/sendWhatsAppAudio/{instance}", False, True),
    "message.send-status": ApiOperation("POST", "/message/sendStatus/{instance}", False, True),
    "message.send-sticker": ApiOperation("POST", "/message/sendSticker/{instance}", False, True),
    "message.send-location": ApiOperation("POST", "/message/sendLocation/{instance}", False),
    "message.send-contact": ApiOperation("POST", "/message/sendContact/{instance}", False),
    "message.send-reaction": ApiOperation("POST", "/message/sendReaction/{instance}", False),
    "message.send-poll": ApiOperation("POST", "/message/sendPoll/{instance}", False),
    "message.send-list": ApiOperation("POST", "/message/sendList/{instance}", False),
    "message.send-buttons": ApiOperation("POST", "/message/sendButtons/{instance}", False),

    "call.offer": ApiOperation("POST", "/call/offer/{instance}", False),

    "chat.whatsapp-numbers": ApiOperation("POST", "/chat/whatsappNumbers/{instance}", True),
    "chat.mark-message-read": ApiOperation("POST", "/chat/markMessageAsRead/{instance}", False),
    "chat.archive": ApiOperation("POST", "/chat/archiveChat/{instance}", False),
    "chat.mark-unread": ApiOperation("POST", "/chat/markChatUnread/{instance}", False),
    "chat.delete-message-for-everyone": ApiOperation("DELETE", "/chat/deleteMessageForEveryone/{instance}", False),
    "chat.fetch-profile-picture-url": ApiOperation("POST", "/chat/fetchProfilePictureUrl/{instance}", True),
    "chat.get-base64-from-media-message": ApiOperation("POST", "/chat/getBase64FromMediaMessage/{instance}", False, False, True),
    "chat.update-message": ApiOperation("POST", "/chat/updateMessage/{instance}", False),
    "chat.send-presence": ApiOperation("POST", "/chat/sendPresence/{instance}", False),
    "chat.update-block-status": ApiOperation("POST", "/chat/updateBlockStatus/{instance}", False),
    "chat.find-contacts": ApiOperation("POST", "/chat/findContacts/{instance}", True),
    "chat.find-messages": ApiOperation("POST", "/chat/findMessages/{instance}", True),
    "chat.find-status-message": ApiOperation("POST", "/chat/findStatusMessage/{instance}", True),
    "chat.find-chats": ApiOperation("POST", "/chat/findChats/{instance}", True),
    "chat.find-by-remote-jid": ApiOperation("GET", "/chat/findChatByRemoteJid/{instance}", True),
    "chat.fetch-business-profile": ApiOperation("POST", "/chat/fetchBusinessProfile/{instance}", True),
    "chat.fetch-profile": ApiOperation("POST", "/chat/fetchProfile/{instance}", True),
    "chat.update-profile-name": ApiOperation("POST", "/chat/updateProfileName/{instance}", False),
    "chat.update-profile-status": ApiOperation("POST", "/chat/updateProfileStatus/{instance}", False),
    "chat.update-profile-picture": ApiOperation("POST", "/chat/updateProfilePicture/{instance}", False),
    "chat.remove-profile-picture": ApiOperation("DELETE", "/chat/removeProfilePicture/{instance}", False),
    "chat.fetch-privacy-settings": ApiOperation("GET", "/chat/fetchPrivacySettings/{instance}", True),
    "chat.update-privacy-settings": ApiOperation("POST", "/chat/updatePrivacySettings/{instance}", False),

    "business.get-catalog": ApiOperation("POST", "/business/getCatalog/{instance}", True),
    "business.get-collections": ApiOperation("POST", "/business/getCollections/{instance}", True),

    "group.create": ApiOperation("POST", "/group/create/{instance}", False),
    "group.update-subject": ApiOperation("POST", "/group/updateGroupSubject/{instance}", False),
    "group.update-picture": ApiOperation("POST", "/group/updateGroupPicture/{instance}", False),
    "group.update-description": ApiOperation("POST", "/group/updateGroupDescription/{instance}", False),
    "group.find-info": ApiOperation("GET", "/group/findGroupInfos/{instance}", True),
    "group.fetch-all": ApiOperation("GET", "/group/fetchAllGroups/{instance}", True),
    "group.participants": ApiOperation("GET", "/group/participants/{instance}", True),
    "group.invite-code": ApiOperation("GET", "/group/inviteCode/{instance}", True),
    "group.invite-info": ApiOperation("GET", "/group/inviteInfo/{instance}", True),
    "group.accept-invite-code": ApiOperation("GET", "/group/acceptInviteCode/{instance}", False),
    "group.send-invite": ApiOperation("POST", "/group/sendInvite/{instance}", False),
    "group.revoke-invite-code": ApiOperation("POST", "/group/revokeInviteCode/{instance}", False),
    "group.update-participant": ApiOperation("POST", "/group/updateParticipant/{instance}", False),
    "group.update-setting": ApiOperation("POST", "/group/updateSetting/{instance}", False),
    "group.toggle-ephemeral": ApiOperation("POST", "/group/toggleEphemeral/{instance}", False),
    "group.leave": ApiOperation("DELETE", "/group/leaveGroup/{instance}", False),

    "template.create": ApiOperation("POST", "/template/create/{instance}", False),
    "template.edit": ApiOperation("POST", "/template/edit/{instance}", False),
    "template.delete": ApiOperation("DELETE", "/template/delete/{instance}", False),
    "template.find": ApiOperation("GET", "/template/find/{instance}", True),
    "settings.set": ApiOperation("POST", "/settings/set/{instance}", False),
    "settings.find": ApiOperation("GET", "/settings/find/{instance}", True),
    "proxy.set": ApiOperation("POST", "/proxy/set/{instance}", False),
    "proxy.find": ApiOperation("GET", "/proxy/find/{instance}", True),
    "label.find": ApiOperation("GET", "/label/findLabels/{instance}", True),
    "label.handle": ApiOperation("POST", "/label/handleLabel/{instance}", False),

    "webhook.set": ApiOperation("POST", "/webhook/set/{instance}", False),
    "webhook.find": ApiOperation("GET", "/webhook/find/{instance}", True),
    "websocket.set": ApiOperation("POST", "/websocket/set/{instance}", False),
    "websocket.find": ApiOperation("GET", "/websocket/find/{instance}", True),
    "rabbitmq.set": ApiOperation("POST", "/rabbitmq/set/{instance}", False),
    "rabbitmq.find": ApiOperation("GET", "/rabbitmq/find/{instance}", True),
    "nats.set": ApiOperation("POST", "/nats/set/{instance}", False),
    "nats.find": ApiOperation("GET", "/nats/find/{instance}", True),
    "pusher.set": ApiOperation("POST", "/pusher/set/{instance}", False),
    "pusher.find": ApiOperation("GET", "/pusher/find/{instance}", True),
    "sqs.set": ApiOperation("POST", "/sqs/set/{instance}", False),
    "sqs.find": ApiOperation("GET", "/sqs/find/{instance}", True),
    "kafka.set": ApiOperation("POST", "/kafka/set/{instance}", False),
    "kafka.find": ApiOperation("GET", "/kafka/find/{instance}", True),

    "evolution-bot.create": ApiOperation("POST", "/evolutionBot/create/{instance}", False),
    "evolution-bot.find": ApiOperation("GET", "/evolutionBot/find/{instance}", True),
    "evolution-bot.fetch": ApiOperation("GET", "/evolutionBot/fetch/{evolutionBotId}/{instance}", True),
    "evolution-bot.update": ApiOperation("PUT", "/evolutionBot/update/{evolutionBotId}/{instance}", False),
    "evolution-bot.delete": ApiOperation("DELETE", "/evolutionBot/delete/{evolutionBotId}/{instance}", False),
    "evolution-bot.settings": ApiOperation("POST", "/evolutionBot/settings/{instance}", False),
    "evolution-bot.fetch-settings": ApiOperation("GET", "/evolutionBot/fetchSettings/{instance}", True),
    "evolution-bot.change-status": ApiOperation("POST", "/evolutionBot/changeStatus/{instance}", False),
    "evolution-bot.fetch-sessions": ApiOperation("GET", "/evolutionBot/fetchSessions/{evolutionBotId}/{instance}", True),
    "evolution-bot.ignore-jid": ApiOperation("POST", "/evolutionBot/ignoreJid/{instance}", False),

    "chatwoot.set": ApiOperation("POST", "/chatwoot/set/{instance}", False),
    "chatwoot.find": ApiOperation("GET", "/chatwoot/find/{instance}", True),

    "typebot.create": ApiOperation("POST", "/typebot/create/{instance}", False),
    "typebot.find": ApiOperation("GET", "/typebot/find/{instance}", True),
    "typebot.fetch": ApiOperation("GET", "/typebot/fetch/{typebotId}/{instance}", True),
    "typebot.update": ApiOperation("PUT", "/typebot/update/{typebotId}/{instance}", False),
    "typebot.delete": ApiOperation("DELETE", "/typebot/delete/{typebotId}/{instance}", False),
    "typebot.settings": ApiOperation("POST", "/typebot/settings/{instance}", False),
    "typebot.fetch-settings": ApiOperation("GET", "/typebot/fetchSettings/{instance}", True),
    "typebot.start": ApiOperation("POST", "/typebot/start/{instance}", False),
    "typebot.change-status": ApiOperation("POST", "/typebot/changeStatus/{instance}", False),
    "typebot.fetch-sessions": ApiOperation("GET", "/typebot/fetchSessions/{typebotId}/{instance}", True),
    "typebot.ignore-jid": ApiOperation("POST", "/typebot/ignoreJid/{instance}", False),

    "openai.create-credentials": ApiOperation("POST", "/openai/creds/{instance}", False),
    "openai.find-credentials": ApiOperation("GET", "/openai/creds/{instance}", True),
    "openai.delete-credentials": ApiOperation("DELETE", "/openai/creds/{openaiCredsId}/{instance}", False),
    "openai.create": ApiOperation("POST", "/openai/create/{instance}", False),
    "openai.find": ApiOperation("GET", "/openai/find/{instance}", True),
    "openai.fetch": ApiOperation("GET", "/openai/fetch/{openaiBotId}/{instance}", True),
    "openai.update": ApiOperation("PUT", "/openai/update/{openaiBotId}/{instance}", False),
    "openai.delete": ApiOperation("DELETE", "/openai/delete/{openaiBotId}/{instance}", False),
    "openai.settings": ApiOperation("POST", "/openai/settings/{instance}", False),
    "openai.fetch-settings": ApiOperation("GET", "/openai/fetchSettings/{instance}", True),
    "openai.change-status": ApiOperation("POST", "/openai/changeStatus/{instance}", False),
    "openai.fetch-sessions": ApiOperation("GET", "/openai/fetchSessions/{openaiBotId}/{instance}", True),
    "openai.ignore-jid": ApiOperation("POST", "/openai/ignoreJid/{instance}", False),
    "openai.get-models": ApiOperation("GET", "/openai/getModels/{instance}", True),

    "dify.create": ApiOperation("POST", "/dify/create/{instance}", False),
    "dify.find": ApiOperation("GET", "/dify/find/{instance}", True),
    "dify.fetch": ApiOperation("GET", "/dify/fetch/{difyId}/{instance}", True),
    "dify.update": ApiOperation("PUT", "/dify/update/{difyId}/{instance}", False),
    "dify.delete": ApiOperation("DELETE", "/dify/delete/{difyId}/{instance}", False),
    "dify.settings": ApiOperation("POST", "/dify/settings/{instance}", False),
    "dify.fetch-settings": ApiOperation("GET", "/dify/fetchSettings/{instance}", True),
    "dify.change-status": ApiOperation("POST", "/dify/changeStatus/{instance}", False),
    "dify.fetch-sessions": ApiOperation("GET", "/dify/fetchSessions/{difyId}/{instance}", True),
    "dify.ignore-jid": ApiOperation("POST", "/dify/ignoreJid/{instance}", False),

    "flowise.create": ApiOperation("POST", "/flowise/create/{instance}", False),
    "flowise.find": ApiOperation("GET", "/flowise/find/{instance}", True),
    "flowise.fetch": ApiOperation("GET", "/flowise/fetch/{flowiseId}/{instance}", True),
    "flowise.update": ApiOperation("PUT", "/flowise/update/{flowiseId}/{instance}", False),
    "flowise.delete": ApiOperation("DELETE", "/flowise/delete/{flowiseId}/{instance}", False),
    "flowise.settings": ApiOperation("POST", "/flowise/settings/{instance}", False),
    "flowise.fetch-settings": ApiOperation("GET", "/flowise/fetchSettings/{instance}", True),
    "flowise.change-status": ApiOperation("POST", "/flowise/changeStatus/{instance}", False),
    "flowise.fetch-sessions": ApiOperation("GET", "/flowise/fetchSessions/{flowiseId}/{instance}", True),
    "flowise.ignore-jid": ApiOperation("POST", "/flowise/ignoreJid/{instance}", False),

    "n8n.create": ApiOperation("POST", "/n8n/create/{instance}", False),
    "n8n.find": ApiOperation("GET", "/n8n/find/{instance}", True),
    "n8n.fetch": ApiOperation("GET", "/n8n/fetch/{n8nId}/{instance}", True),
    "n8n.update": ApiOperation("PUT", "/n8n/update/{n8nId}/{instance}", False),
    "n8n.delete": ApiOperation("DELETE", "/n8n/delete/{n8nId}/{instance}", False),
    "n8n.settings": ApiOperation("POST", "/n8n/settings/{instance}", False),
    "n8n.fetch-settings": ApiOperation("GET", "/n8n/fetchSettings/{instance}", True),
    "n8n.change-status": ApiOperation("POST", "/n8n/changeStatus/{instance}", False),
    "n8n.fetch-sessions": ApiOperation("GET", "/n8n/fetchSessions/{n8nId}/{instance}", True),
    "n8n.ignore-jid": ApiOperation("POST", "/n8n/ignoreJid/{instance}", False),

    "evoai.create": ApiOperation("POST", "/evoai/create/{instance}", False),
    "evoai.find": ApiOperation("GET", "/evoai/find/{instance}", True),
    "evoai.fetch": ApiOperation("GET", "/evoai/fetch/{evoaiId}/{instance}", True),
    "evoai.update": ApiOperation("PUT", "/evoai/update/{evoaiId}/{instance}", False),
    "evoai.delete": ApiOperation("DELETE", "/evoai/delete/{evoaiId}/{instance}", False),
    "evoai.settings": ApiOperation("POST", "/evoai/settings/{instance}", False),
    "evoai.fetch-settings": ApiOperation("GET", "/evoai/fetchSettings/{instance}", True),
    "evoai.change-status": ApiOperation("POST", "/evoai/changeStatus/{instance}", False),
    "evoai.fetch-sessions": ApiOperation("GET", "/evoai/fetchSessions/{evoaiId}/{instance}", True),
    "evoai.ignore-jid": ApiOperation("POST", "/evoai/ignoreJid/{instance}", False),

    "baileys.on-whatsapp": ApiOperation("POST", "/baileys/onWhatsapp/{instance}", True),
    "baileys.profile-picture-url": ApiOperation("POST", "/baileys/profilePictureUrl/{instance}", True),
    "baileys.assert-sessions": ApiOperation("POST", "/baileys/assertSessions/{instance}", False),
    "baileys.create-participant-nodes": ApiOperation("POST", "/baileys/createParticipantNodes/{instance}", False),
    "baileys.get-usync-devices": ApiOperation("POST", "/baileys/getUSyncDevices/{instance}", True),
    "baileys.generate-message-tag": ApiOperation("POST", "/baileys/generateMessageTag/{instance}", True),
    "baileys.send-node": ApiOperation("POST", "/baileys/sendNode/{instance}", False),
    "baileys.decrypt-message": ApiOperation("POST", "/baileys/signalRepositoryDecryptMessage/{instance}", False),
    "baileys.get-auth-state": ApiOperation("POST", "/baileys/getAuthState/{instance}", False, False, False, True),

    "s3.get-media": ApiOperation("POST", "/s3/getMedia/{instance}", True),
    "s3.get-media-url": ApiOperation("POST", "/s3/getMediaUrl/{instance}", True),
}

_PATH_PARAMETER = re.compile(r"{([A-Za-z][A-Za-z0-9_]*)}")


def api_operation(name: str) -> ApiOperation:
    if not isinstance(name, str):
        raise ValueError("API operation is not in the Evolution 2.3.7 catalog")
    try:
        return API_OPERATIONS[name]
    except KeyError as exc:
        raise ValueError("API operation is not in the Evolution 2.3.7 catalog") from exc


def api_path_parameters(name: str) -> tuple[str, ...]:
    return tuple(_PATH_PARAMETER.findall(api_operation(name).path))


def api_catalog(prefix: str | None = None) -> dict:
    if prefix is not None and (not isinstance(prefix, str) or not prefix.strip()):
        raise ValueError("catalog prefix is invalid")
    selected = (
        (name, operation)
        for name, operation in sorted(API_OPERATIONS.items())
        if prefix is None or name.startswith(prefix)
    )
    return {
        "profile": EVOLUTION_2_3_7,
        "upstream_tag": UPSTREAM_TAG,
        "upstream_source": UPSTREAM_SOURCE,
        "operations": [
            {
                "id": name,
                "method": operation.method,
                "path": operation.path,
                "execution": "restricted" if operation.restricted else "download" if operation.download_file else "read" if operation.read_only else "plan",
                "upload_file": operation.upload_file,
                "download_file": operation.download_file,
                "restricted": operation.restricted,
            }
            for name, operation in selected
        ],
    }
