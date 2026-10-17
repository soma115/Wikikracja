from django.urls import path

from .views import (
    AssetCreateView,
    AssetDeleteView,
    AssetDetailView,
    AssetListView,
    AssetUpdateView,
    CategoryCreateView,
    CategoryDeleteView,
    CategoryDetailView,
    CategoryListView,
    CategoryUpdateView,
    PartnerCreateView,
    PartnerDeleteView,
    PartnerDetailView,
    PartnerListView,
    PartnerUpdateView,
    PhysicalAssetCreateView,
    PhysicalAssetDetailView,
    PhysicalAssetListView,
    PhysicalAssetUpdateView,
    ReportView,
    ResourceListView,
    TransactionClaimView,
    TransactionCreateView,
    TransactionDeleteView,
    TransactionDetailView,
    TransactionListView,
    TransactionUpdateView,
    resource_create,
    resource_delete,
    resource_manage,
    resource_search,
    resource_toggle_closed,
    resource_update,
)

app_name = 'bookkeeping'

urlpatterns = [
    # Transaction URL (combined incoming/outgoing)
    path('transaction/', TransactionListView.as_view(), name='transaction_list'),
    path('transaction/create/', TransactionCreateView.as_view(), name='transaction_create'),
    path('transaction/<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),
    path('transaction/<int:pk>/claim/', TransactionClaimView.as_view(), name='transaction_claim'),
    path('transaction/<int:pk>/update/', TransactionUpdateView.as_view(), name='transaction_update'),
    path('transaction/<int:pk>/delete/', TransactionDeleteView.as_view(), name='transaction_delete'),
    # Asset URLs
    path('asset/', AssetListView.as_view(), name='asset_list'),
    path('asset/create/', AssetCreateView.as_view(), name='asset_create'),
    path('asset/<int:pk>/', AssetDetailView.as_view(), name='asset_detail'),
    path('asset/<int:pk>/update/', AssetUpdateView.as_view(), name='asset_update'),
    path('asset/<int:pk>/delete/', AssetDeleteView.as_view(), name='asset_delete'),
    # Physical assets are separate from financial Asset units.
    path('physical-asset/', PhysicalAssetListView.as_view(), name='physical_asset_list'),
    path('physical-asset/create/', PhysicalAssetCreateView.as_view(), name='physical_asset_create'),
    path('physical-asset/<int:pk>/', PhysicalAssetDetailView.as_view(), name='physical_asset_detail'),
    path('physical-asset/<int:pk>/update/', PhysicalAssetUpdateView.as_view(), name='physical_asset_update'),
    # Partner URLs
    path('partner/', PartnerListView.as_view(), name='partner_list'),
    path('partner/create/', PartnerCreateView.as_view(), name='partner_create'),
    path('partner/<int:pk>/', PartnerDetailView.as_view(), name='partner_detail'),
    path('partner/<int:pk>/update/', PartnerUpdateView.as_view(), name='partner_update'),
    path('partner/<int:pk>/delete/', PartnerDeleteView.as_view(), name='partner_delete'),
    # Category URLs
    path('category/', CategoryListView.as_view(), name='category_list'),
    path('category/create/', CategoryCreateView.as_view(), name='category_create'),
    path('category/<int:pk>/', CategoryDetailView.as_view(), name='category_detail'),
    path('category/<int:pk>/update/', CategoryUpdateView.as_view(), name='category_update'),
    path('category/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category_delete'),
    # Report URLs
    path('report/', ReportView.as_view(), name='report_list'),
    path('report/<int:year>/', ReportView.as_view(), name='report_by_year'),
    # Member offers and needs, kept separate from financial Asset records.
    path('resource/', ResourceListView.as_view(), name='resource_list'),
    path('resource/manage/', resource_manage, name='resource_manage'),
    path('resource/create/', resource_create, name='resource_create'),
    path('resource/<int:pk>/update/', resource_update, name='resource_update'),
    path('resource/<int:pk>/delete/', resource_delete, name='resource_delete'),
    path('resource/<int:pk>/close/', resource_toggle_closed, name='resource_toggle_closed'),
    path('resource/search/', resource_search, name='resource_search'),
    # Default view
    path('', TransactionListView.as_view(), name='index'),
]
