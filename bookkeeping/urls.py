from django.urls import path

from .views import (
    AssetCreateView,
    AssetDeleteView,
    AssetListView,
    AssetUpdateView,
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    PartnerCreateView,
    PartnerDeleteView,
    PartnerDetailView,
    PartnerListView,
    PartnerUpdateView,
    ReportView,
    TransactionCreateView,
    TransactionDeleteView,
    TransactionListView,
    TransactionUpdateView,
)

app_name = 'bookkeeping'

urlpatterns = [
    # Transaction URL (combined incoming/outgoing)
    path('transaction/', TransactionListView.as_view(), name='transaction_list'),
    path('transaction/create/', TransactionCreateView.as_view(), name='transaction_create'),
    path('transaction/<int:pk>/update/', TransactionUpdateView.as_view(), name='transaction_update'),
    path('transaction/<int:pk>/delete/', TransactionDeleteView.as_view(), name='transaction_delete'),

    # Asset URLs
    path('asset/', AssetListView.as_view(), name='asset_list'),
    path('asset/create/', AssetCreateView.as_view(), name='asset_create'),
    path('asset/<int:pk>/update/', AssetUpdateView.as_view(), name='asset_update'),
    path('asset/<int:pk>/delete/', AssetDeleteView.as_view(), name='asset_delete'),

    # Partner URLs
    path('partner/', PartnerListView.as_view(), name='partner_list'),
    path('partner/create/', PartnerCreateView.as_view(), name='partner_create'),
    path('partner/<int:pk>/', PartnerDetailView.as_view(), name='partner_detail'),
    path('partner/<int:pk>/update/', PartnerUpdateView.as_view(), name='partner_update'),
    path('partner/<int:pk>/delete/', PartnerDeleteView.as_view(), name='partner_delete'),

    # Category URLs
    path('category/', CategoryListView.as_view(), name='category_list'),
    path('category/create/', CategoryCreateView.as_view(), name='category_create'),
    path('category/<int:pk>/update/', CategoryUpdateView.as_view(), name='category_update'),
    path('category/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category_delete'),

    # Report URLs
    path('report/', ReportView.as_view(), name='report_list'),
    path('report/<int:year>/', ReportView.as_view(), name='report_by_year'),

    # Default view
    path('', TransactionListView.as_view(), name='index'),
]
