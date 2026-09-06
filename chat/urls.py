from django.urls import path

from . import push_api, views

app_name = 'chat'

urlpatterns = [
    path('', views.chat, name='chat'),
    path('dm/<int:pk>/', views.open_dm, name='open_dm'),
    path('add_room/', views.add_room, name='add_room'),
    path('upload/', views.upload_image),
    # Push notification API endpoints
    path('api/push/register/', push_api.PushDeviceRegisterView.as_view(), name='push_register'),
    path('api/push/unregister/', push_api.PushDeviceUnregisterView.as_view(), name='push_unregister'),
    path('api/push/ack/', push_api.PushNotificationAckView.as_view(), name='push_ack'),
    # Unread count API (used by home page badge refresh)
    path('api/unread-count/', views.unread_count, name='unread_count'),
    # Rename room
    path('api/room/<int:room_id>/rename/', views.rename_room, name='rename_room'),
    # Anonymous guest message submission
    path('guest-message/', views.guest_message, name='guest_message'),
]
