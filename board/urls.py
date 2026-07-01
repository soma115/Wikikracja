from django.urls import path

from . import views

app_name = 'board'

urlpatterns = [
    path('', views.board, name='start'),
    path('create/', views.create_post, name='create_post'),
    path('edit/<int:pk>/', views.edit_post, name='edit_post'),
    path('view/<int:pk>/', views.view_post, name='view_post'),
    path('view/<slug:slug>/', views.view_post_by_slug, name='view_post_by_slug'),
    path('delete/<int:pk>/', views.delete_post, name='delete_post'),
    path('edit/<int:pk>/attachment/<int:attachment_id>/delete/', views.delete_attachment, name='delete_attachment'),
    path('api/categories/', views.PostCategoryAPI.as_view(), name='api_categories'),
    path('api/categories/<int:pk>/edit/', views.PostCategoryEditAPI.as_view(), name='api_category_edit'),
    path('api/categories/<int:pk>/delete/', views.PostCategoryDeleteAPI.as_view(), name='api_category_delete'),
    path('api/categories/<int:pk>/items/', views.PostCategoryItemsAPI.as_view(), name='api_category_items'),
    path('api/categories/reorder/', views.PostCategoryReorderAPI.as_view(), name='api_category_reorder'),
]
