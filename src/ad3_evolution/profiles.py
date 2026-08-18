"""Explicit Evolution v2.3.7 route contract. No mutating route fallback is permitted."""
EVOLUTION_2_3_7 = "evolution-2.3.7"
ROUTES = {
 "instance_create": ("POST", "/instance/create"), "instance_list": ("GET", "/instance/fetchInstances"), "instance_status": ("GET", "/instance/connectionState/{instance}"),
 "chat_list": ("POST", "/chat/findChats/{instance}"), "message_history": ("POST", "/chat/findMessages/{instance}"),
 "instance_qr": ("GET", "/instance/connect/{instance}"), "group_list": ("GET", "/group/fetchAllGroups/{instance}"),
 "group_info": ("GET", "/group/findGroupInfos/{instance}"), "group_participants": ("GET", "/group/participants/{instance}"), "invite_info": ("GET", "/group/inviteInfo/{instance}"), "group_create": ("POST", "/group/create/{instance}"), "whatsapp_validate": ("POST", "/chat/whatsappNumbers/{instance}"),
 "group_subject": ("POST", "/group/updateGroupSubject/{instance}"), "group_description": ("POST", "/group/updateGroupDescription/{instance}"),
 "group_picture": ("POST", "/group/updateGroupPicture/{instance}"), "participants_add": ("POST", "/group/updateParticipant/{instance}"), "participants_remove": ("POST", "/group/updateParticipant/{instance}"),
 "participants_promote": ("POST", "/group/updateParticipant/{instance}"), "participants_demote": ("POST", "/group/updateParticipant/{instance}"),
 "group_settings": ("POST", "/group/updateSetting/{instance}"), "invite_get": ("GET", "/group/inviteCode/{instance}"), "invite_revoke": ("POST", "/group/revokeInviteCode/{instance}"), "invite_send": ("POST", "/group/sendInvite/{instance}"),
 "group_leave": ("DELETE", "/group/leaveGroup/{instance}"), "send_text": ("POST", "/message/sendText/{instance}"), "send_media": ("POST", "/message/sendMedia/{instance}"),
 "webhook_find": ("GET", "/webhook/find/{instance}"), "webhook_set": ("POST", "/webhook/set/{instance}"),
}
IDEMPOTENT = {"instance_list", "instance_status", "instance_qr", "chat_list", "message_history", "group_list", "group_info", "group_participants", "invite_info", "whatsapp_validate", "invite_get", "webhook_find"}
MUTATING = set(ROUTES) - IDEMPOTENT
