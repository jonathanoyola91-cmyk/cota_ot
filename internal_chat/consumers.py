import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversacion, Mensaje, MensajeLeido


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope["user"]
        self.conversacion_id = self.scope["url_route"]["kwargs"]["conversacion_id"]

        if not self.user.is_authenticated:
            await self.close()
            return

        permitido = await self.usuario_pertenece_conversacion()

        if not permitido:
            await self.close()
            return

        self.room_group_name = f"chat_{self.conversacion_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        destinatarios = await self.obtener_destinatarios()

        for destinatario_id in destinatarios:
            await self.channel_layer.group_send(
                f"user_{destinatario_id}",
                {
                    "type": "presence_probe",
                    "requester_channel": self.channel_name,
                    "usuario_id": destinatario_id,
                }
            )

        estados_leidos = await self.marcar_mensajes_como_leidos()

        if estados_leidos:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "messages_read",
                    "estados": estados_leidos,
                    "usuario_id": self.user.id,
                }
            )

            total_no_leidos = await self.obtener_no_leidos_usuario(
                self.user.id
            )

            await self.channel_layer.group_send(
                f"user_{self.user.id}",
                {
                    "type": "unread_count",
                    "count": total_no_leidos,
                }
            )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        tipo = data.get("type", "chat_message")

        if tipo == "chat_message":
            texto = data.get("message", "").strip()
            client_message_id = str(
                data.get("client_message_id", "")
            )[:100]

            if not texto:
                return

            texto = texto[:5000]

            mensaje = await self.guardar_mensaje(texto)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "mensaje_id": mensaje["id"],
                    "client_message_id": client_message_id,
                    "message": mensaje["texto"],
                    "autor": mensaje["autor"],
                    "autor_id": mensaje["autor_id"],
                    "creado_en": mensaje["creado_en"],
                    "tipo_conversacion": mensaje["tipo_conversacion"],
                    "leidos": 0,
                    "total_destinatarios": mensaje["total_destinatarios"],
                }
            )

            destinatarios = await self.obtener_destinatarios()

            for destinatario_id in destinatarios:
                total_no_leidos = await self.obtener_no_leidos_usuario(
                    destinatario_id
                )

                await self.channel_layer.group_send(
                    f"user_{destinatario_id}",
                    {
                        "type": "new_message_notification",
                        "conversation_id": int(self.conversacion_id),
                        "message_id": mensaje["id"],
                        "sender": mensaje["autor"],
                        "message": mensaje["texto"],
                        "count": total_no_leidos,
                    }
                )

        elif tipo == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_status",
                    "usuario_id": self.user.id,
                    "usuario_nombre": (
                        self.user.get_full_name()
                        or self.user.username
                    ),
                    "is_typing": bool(data.get("is_typing")),
                }
            )

        elif tipo == "mark_read":
            estados_leidos = await self.marcar_mensajes_como_leidos()

            if estados_leidos:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "messages_read",
                        "estados": estados_leidos,
                        "usuario_id": self.user.id,
                    }
                )

                total_no_leidos = await self.obtener_no_leidos_usuario(
                    self.user.id
                )

                await self.channel_layer.group_send(
                    f"user_{self.user.id}",
                    {
                        "type": "unread_count",
                        "count": total_no_leidos,
                    }
                )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "chat_message",
                "mensaje_id": event["mensaje_id"],
                "client_message_id": event.get("client_message_id", ""),
                "message": event["message"],
                "autor": event["autor"],
                "autor_id": event["autor_id"],
                "creado_en": event["creado_en"],
                "tipo_conversacion": event["tipo_conversacion"],
                "leidos": event["leidos"],
                "total_destinatarios": event["total_destinatarios"],
            })
        )

    async def chat_attachment(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "chat_attachment",
                "mensaje_id": event["mensaje_id"],
                "autor": event["autor"],
                "autor_id": event["autor_id"],
                "creado_en": event["creado_en"],
                "adjunto_id": event["adjunto_id"],
                "nombre": event["nombre"],
                "tipo_mime": event["tipo_mime"],
                "tamano": event["tamano"],
                "es_imagen": event["es_imagen"],
                "url": event["url"],
                "tipo_conversacion": event["tipo_conversacion"],
                "leidos": event["leidos"],
                "total_destinatarios": event["total_destinatarios"],
            })
        )

    async def messages_read(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "messages_read",
                "estados": event["estados"],
                "usuario_id": event["usuario_id"],
            })
        )

    async def typing_status(self, event):
        if event["usuario_id"] == self.user.id:
            return

        await self.send(
            text_data=json.dumps({
                "type": "typing_status",
                "usuario_id": event["usuario_id"],
                "usuario_nombre": event["usuario_nombre"],
                "is_typing": event["is_typing"],
            })
        )

    async def presence_status(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "presence_status",
                "usuario_id": event["usuario_id"],
                "online": event["online"],
            })
        )

    @database_sync_to_async
    def usuario_pertenece_conversacion(self):
        return Conversacion.objects.filter(
            id=self.conversacion_id,
            activa=True,
            participantes=self.user
        ).exists()

    @database_sync_to_async
    def guardar_mensaje(self, texto):
        conversacion = Conversacion.objects.get(
            id=self.conversacion_id,
            activa=True
        )

        mensaje = Mensaje.objects.create(
            conversacion=conversacion,
            autor=self.user,
            texto=texto
        )

        conversacion.save(
            update_fields=["actualizado_en"]
        )

        total_destinatarios = max(
            conversacion.participantes.count() - 1,
            1,
        )

        return {
            "id": mensaje.id,
            "texto": mensaje.texto,
            "autor": (
                self.user.get_full_name()
                or self.user.username
            ),
            "autor_id": self.user.id,
            "creado_en": timezone.localtime(
                mensaje.creado_en
            ).strftime("%H:%M"),
            "tipo_conversacion": conversacion.tipo,
            "total_destinatarios": total_destinatarios,
        }

    @database_sync_to_async
    def marcar_mensajes_como_leidos(self):
        mensajes = list(
            Mensaje.objects
            .filter(
                conversacion_id=self.conversacion_id,
                eliminado=False
            )
            .exclude(
                autor=self.user
            )
            .exclude(
                lecturas__usuario=self.user
            )
        )

        if not mensajes:
            return []

        MensajeLeido.objects.bulk_create(
            [
                MensajeLeido(
                    mensaje=mensaje,
                    usuario=self.user
                )
                for mensaje in mensajes
            ],
            ignore_conflicts=True
        )

        conversacion = Conversacion.objects.get(
            id=self.conversacion_id
        )

        total_destinatarios = max(
            conversacion.participantes.count() - 1,
            1,
        )

        estados = []

        for mensaje in mensajes:
            leidos = MensajeLeido.objects.filter(
                mensaje=mensaje
            ).exclude(
                usuario=mensaje.autor
            ).count()

            estados.append({
                "mensaje_id": mensaje.id,
                "leidos": leidos,
                "total_destinatarios": total_destinatarios,
                "tipo_conversacion": conversacion.tipo,
            })

        return estados

    @database_sync_to_async
    def obtener_destinatarios(self):
        return list(
            Conversacion.objects
            .get(
                id=self.conversacion_id,
                activa=True
            )
            .participantes
            .exclude(id=self.user.id)
            .values_list("id", flat=True)
        )

    @database_sync_to_async
    def obtener_no_leidos_usuario(self, usuario_id):
        return (
            Mensaje.objects
            .filter(
                conversacion__participantes__id=usuario_id,
                conversacion__activa=True,
                eliminado=False,
            )
            .exclude(
                autor_id=usuario_id
            )
            .exclude(
                lecturas__usuario_id=usuario_id
            )
            .distinct()
            .count()
        )


class NotificationConsumer(AsyncWebsocketConsumer):

    PRESENCE_GROUP = "presence_all_users"

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group_name = f"user_{self.user.id}"

        # Grupo privado del usuario:
        # notificaciones, no leídos y respuestas de presencia.
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        # Un único grupo liviano para presencia.
        await self.channel_layer.group_add(
            self.PRESENCE_GROUP,
            self.channel_name
        )

        await self.accept()

        # Avisar una sola vez que este usuario está conectado.
        await self.channel_layer.group_send(
            self.PRESENCE_GROUP,
            {
                "type": "presence_broadcast",
                "usuario_id": self.user.id,
                "online": True,
            }
        )

        # Solicitar una fotografía de los usuarios que están
        # conectados en este momento. Cada socket global activo
        # responde directamente al grupo privado del solicitante.
        await self.channel_layer.group_send(
            self.PRESENCE_GROUP,
            {
                "type": "presence_snapshot_request",
                "requester_user_id": self.user.id,
            }
        )

        total = await self.obtener_total_no_leidos()

        await self.send(
            text_data=json.dumps({
                "type": "unread_count",
                "count": total,
            })
        )

    async def disconnect(self, close_code):
        if not getattr(self, "user", None):
            return

        if not self.user.is_authenticated:
            return

        # Un solo evento de salida, sin recorrer conversaciones
        # ni contactos.
        await self.channel_layer.group_send(
            self.PRESENCE_GROUP,
            {
                "type": "presence_broadcast",
                "usuario_id": self.user.id,
                "online": False,
            }
        )

        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

        await self.channel_layer.group_discard(
            self.PRESENCE_GROUP,
            self.channel_name
        )

    async def presence_broadcast(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "presence_global",
                "usuario_id": event["usuario_id"],
                "online": event["online"],
            })
        )

    async def presence_snapshot_request(self, event):
        requester_user_id = int(
            event["requester_user_id"]
        )

        # No necesitamos respondernos a nosotros mismos.
        if requester_user_id == self.user.id:
            return

        await self.channel_layer.group_send(
            f"user_{requester_user_id}",
            {
                "type": "presence_global",
                "usuario_id": self.user.id,
                "online": True,
            }
        )

    async def presence_global(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "presence_global",
                "usuario_id": event["usuario_id"],
                "online": event["online"],
            })
        )

    async def unread_count(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "unread_count",
                "count": event["count"],
            })
        )

    async def new_message_notification(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "new_message",
                "conversation_id": event["conversation_id"],
                "message_id": event["message_id"],
                "sender": event["sender"],
                "message": event["message"],
                "count": event["count"],
            })
        )

    @database_sync_to_async
    def obtener_total_no_leidos(self):
        return (
            Mensaje.objects
            .filter(
                conversacion__participantes=self.user,
                conversacion__activa=True,
                eliminado=False,
            )
            .exclude(
                autor=self.user
            )
            .exclude(
                lecturas__usuario=self.user
            )
            .distinct()
            .count()
        )
