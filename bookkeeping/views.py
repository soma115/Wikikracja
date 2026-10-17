import json
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db import transaction as db_transaction
from django.db.models import Count, Min, OuterRef, Q, Subquery
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from core.signals import transaction_created, transaction_updated
from core.utils import build_detail_navigation, build_site_url
from home.navigation import default_toolbar_views
from obywatele.models import Uzytkownik
from resources.models import LEGACY_FINANCIAL_ASSET_SOURCE, LEGACY_PHYSICAL_ASSET_SOURCE, LEGACY_RESOURCE_LISTING_SOURCE, Entity, LegacyEntityReference
from resources.services import delete_financial_asset_entity, sync_financial_asset_entity, sync_physical_asset_entity

from .forms import AssetForm, PhysicalAssetForm, ResourceEntityForm, TransactionForm
from .models import Asset, Category, Partner, PhysicalAsset, ResourceListing, Transaction
from .services import category_breakdown


class ProtectedDeleteView(LoginRequiredMixin, DeleteView):
    """DeleteView that refuses to delete an object still referenced by transactions.

    Subclasses set `protect_field` (the Transaction FK name pointing at `model`)
    and `protect_message` (shown to the user when deletion is blocked).
    """

    protect_field = None
    protect_message = None

    def _related_transactions(self):
        return Transaction.objects.filter(**{self.protect_field: self.object})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        related_transactions = self._related_transactions()
        context['related_transactions'] = related_transactions
        context['has_dependencies'] = related_transactions.exists()
        context['cancel_url'] = self.get_success_url()

        if 'delete_error' in self.request.session:
            context['error'] = self.request.session.pop('delete_error')

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self._related_transactions().exists():
            # str(): protect_message to gettext_lazy proxy, który nie serializuje się do sesji.
            request.session['delete_error'] = str(self.protect_message)
            return redirect(request.path)

        try:
            return super().delete(request, *args, **kwargs)
        except Exception as e:
            request.session['delete_error'] = str(e)
            return redirect(request.path)


# #########################  Asset ###########################


def _bookkeeping_toolbar(create_url=None, create_label=None):
    """Build CTA context for the shared toolbar in bookkeeping list views."""
    ctx = {'cta_end': True}
    if create_url:
        ctx['cta_url'] = create_url
        ctx['cta_label'] = create_label or _('Add')
        ctx['cta_icon'] = 'plus'
    return ctx


class BookkeepingListView(LoginRequiredMixin, ListView):
    """ListView injecting the shared add-button toolbar."""

    create_url_name = None
    create_label = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        create_url = reverse_lazy(self.create_url_name) if self.create_url_name else None
        context.update(_bookkeeping_toolbar(create_url=create_url, create_label=self.create_label))
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['detail_query'] = self.request.GET.urlencode()
        context['toolbar_views'] = default_toolbar_views()
        return context


class BookkeepingDetailView(LoginRequiredMixin, DetailView):
    """Shared authenticated detail view for bookkeeping models."""


class BookkeepingCreateView(LoginRequiredMixin, CreateView):
    """Shared authenticated create view with a declarative list redirect."""

    success_url_name = None

    def get_success_url(self):
        return reverse(self.success_url_name)


class BookkeepingUpdateView(LoginRequiredMixin, UpdateView):
    """Shared authenticated update view with a declarative list redirect."""

    success_url_name = None

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Saved.'))
        return response

    def get_success_url(self):
        return reverse(self.success_url_name)


class AssetListView(BookkeepingListView):
    model = Entity
    template_name = 'bookkeeping/asset_list.html'
    create_url_name = 'bookkeeping:asset_create'
    create_label = _('Add asset')

    def get_queryset(self):
        search_query = self.request.GET.get('q', '').strip()
        legacy_asset_pk = LegacyEntityReference.objects.filter(source_model=LEGACY_FINANCIAL_ASSET_SOURCE, entity_id=OuterRef('pk')).values('source_pk')[:1]
        queryset = Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).annotate(legacy_asset_pk=Subquery(legacy_asset_pk)).filter(legacy_asset_pk__isnull=False)
        if search_query:
            queryset = queryset.filter(Q(code__icontains=search_query) | Q(name__icontains=search_query) | Q(symbol__icontains=search_query))
        return queryset.order_by('code', 'pk')


def _financial_entity_for_legacy_asset_pk(source_pk):
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=source_pk, entity__entity_type=Entity.Type.FINANCIAL_ASSET)
    entity = reference.entity
    entity.legacy_asset_pk = source_pk
    return entity


class AssetDetailView(BookkeepingDetailView):
    model = Entity
    template_name = 'bookkeeping/asset_detail.html'
    context_object_name = 'asset'

    def get_object(self, queryset=None):
        return _financial_entity_for_legacy_asset_pk(self.kwargs['pk'])


class AssetCreateView(BookkeepingCreateView):
    model = Entity
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url_name = 'bookkeeping:asset_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Entity(entity_type=Entity.Type.FINANCIAL_ASSET)
        return kwargs

    def form_valid(self, form):
        with db_transaction.atomic():
            response = super().form_valid(form)
            legacy_asset = Asset.objects.create(
                code=self.object.code, name=self.object.name, symbol=self.object.symbol, decimal_places=self.object.decimal_places, is_currency=self.object.is_currency, is_default=self.object.is_default
            )
            sync_financial_asset_entity(legacy_asset)
            self.object.legacy_asset_pk = legacy_asset.pk
            return response


class AssetUpdateView(BookkeepingUpdateView):
    model = Entity
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url_name = 'bookkeeping:asset_list'

    def get_object(self, queryset=None):
        return _financial_entity_for_legacy_asset_pk(self.kwargs['pk'])

    def form_valid(self, form):
        legacy_asset_pk = self.object.legacy_asset_pk
        with db_transaction.atomic():
            response = super().form_valid(form)
            legacy_asset = get_object_or_404(Asset, pk=legacy_asset_pk)
            legacy_asset.code = self.object.code
            legacy_asset.name = self.object.name
            legacy_asset.symbol = self.object.symbol
            legacy_asset.decimal_places = self.object.decimal_places
            legacy_asset.is_currency = self.object.is_currency
            legacy_asset.is_default = self.object.is_default
            legacy_asset.save()
            sync_financial_asset_entity(legacy_asset)
            self.object.legacy_asset_pk = legacy_asset_pk
            return response


class AssetDeleteView(ProtectedDeleteView):
    model = Asset
    template_name = 'bookkeeping/asset_confirm_delete.html'
    success_url = reverse_lazy('bookkeeping:asset_list')
    protect_field = 'asset'
    protect_message = _("Cannot delete asset because it is in use. Remove all transactions that use it first.")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        source_pk = self.object.pk
        with db_transaction.atomic():
            response = super().post(request, *args, **kwargs)
            if not Asset.objects.filter(pk=source_pk).exists():
                delete_financial_asset_entity(source_pk)
            return response


class PhysicalAssetListView(BookkeepingListView):
    model = PhysicalAsset
    template_name = 'bookkeeping/physical_asset_list.html'
    context_object_name = 'physical_assets'
    create_url_name = 'bookkeeping:physical_asset_create'
    create_label = _('Add physical asset')

    def get_queryset(self):
        search_query = self.request.GET.get('q', '').strip()
        queryset = PhysicalAsset.objects.select_related('country')
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query) | Q(city__icontains=search_query) | Q(country__name__icontains=search_query))
        return queryset


class PhysicalAssetDetailView(BookkeepingDetailView):
    model = PhysicalAsset
    template_name = 'bookkeeping/physical_asset_detail.html'
    context_object_name = 'physical_asset'


class PhysicalAssetCreateView(BookkeepingCreateView):
    model = PhysicalAsset
    form_class = PhysicalAssetForm
    template_name = 'bookkeeping/physical_asset_form.html'
    success_url_name = 'bookkeeping:physical_asset_list'

    def form_valid(self, form):
        with db_transaction.atomic():
            response = super().form_valid(form)
            sync_physical_asset_entity(self.object, author=self.request.user, assignment_scope=form.cleaned_data['assignment_scope'], assigned_member=form.cleaned_data.get('assigned_member'))
            return response


class PhysicalAssetUpdateView(BookkeepingUpdateView):
    model = PhysicalAsset
    form_class = PhysicalAssetForm
    template_name = 'bookkeeping/physical_asset_form.html'
    success_url_name = 'bookkeeping:physical_asset_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference = LegacyEntityReference.objects.select_related('entity').filter(source_model=LEGACY_PHYSICAL_ASSET_SOURCE, source_pk=self.object.pk).first()
        entity = reference.entity if reference else None
        kwargs.update(assignment_entity=entity, can_assign=bool(entity and entity.author_id == self.request.user.pk))
        return kwargs

    def form_valid(self, form):
        with db_transaction.atomic():
            response = super().form_valid(form)
            sync_kwargs = {}
            if form.can_assign:
                sync_kwargs = {'assignment_scope': form.cleaned_data['assignment_scope'], 'assigned_member': form.cleaned_data.get('assigned_member')}
            sync_physical_asset_entity(self.object, **sync_kwargs)
            return response


# #########################  Resource listings ###########################


class ResourceListView(BookkeepingListView):
    model = Entity
    template_name = 'bookkeeping/resource_list.html'
    context_object_name = 'resource_listings'
    paginate_by = 24
    create_url_name = 'bookkeeping:resource_manage'
    create_label = _('Add resource')

    def get_queryset(self):
        queryset = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False).filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
        queryset = queryset.select_related('assigned_member__uid', 'assigned_member__voivodeship', 'author')
        query = (self.request.GET.get('q') or '').strip()
        kind = self.request.GET.get('kind')
        city = (self.request.GET.get('city') or '').strip()
        voivodeship = (self.request.GET.get('voivodeship') or '').strip()
        profile_id = (self.request.GET.get('profile') or '').strip()

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
        if kind in Entity.ResourceKind.values:
            queryset = queryset.filter(resource_kind=kind)
        if city:
            queryset = queryset.filter(assigned_member__city=city)
        if voivodeship:
            queryset = queryset.filter(assigned_member__voivodeship__name=voivodeship)
        if profile_id:
            try:
                profile_pk = int(profile_id) if profile_id.isascii() and profile_id.isdecimal() else 0
            except ValueError:
                profile_pk = 0
            max_pk = connection.ops.integer_field_range(Uzytkownik._meta.pk.get_internal_type())[1]
            queryset = queryset.filter(assigned_member_id=profile_pk) if 0 < profile_pk <= max_pk else queryset.none()
        return queryset.order_by('resource_kind', 'name', 'assigned_member__uid__last_name', 'assigned_member__uid__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listings = context['resource_listings']
        totals = self.object_list.aggregate(total=Count('pk'), needs=Count('pk', filter=Q(resource_kind=Entity.ResourceKind.NEED)))
        active_profiles = Uzytkownik.objects.filter(uid__is_active=True)
        context['offer_listings'] = [listing for listing in listings if listing.resource_kind != Entity.ResourceKind.NEED]
        context['need_listings'] = [listing for listing in listings if listing.resource_kind == Entity.ResourceKind.NEED]
        context['offer_count'] = totals['total'] - totals['needs']
        context['need_count'] = totals['needs']
        context['resource_kinds'] = Entity.ResourceKind.choices
        context['cities'] = active_profiles.exclude(city='').exclude(city__isnull=True).values_list('city', flat=True).distinct().order_by('city')
        context['voivodeships'] = active_profiles.exclude(voivodeship__isnull=True).values_list('voivodeship__name', flat=True).distinct().order_by('voivodeship__name')
        context['search_values'] = {key: self.request.GET.get(key, '') for key in ('q', 'kind', 'city', 'voivodeship', 'profile')}

        query = (self.request.GET.get('q') or '').strip()
        kind = self.request.GET.get('kind')
        city = (self.request.GET.get('city') or '').strip()
        voivodeship = (self.request.GET.get('voivodeship') or '').strip()
        if (city or voivodeship) and not query and kind not in Entity.ResourceKind.values and not self.request.GET.get('profile'):
            location_profiles = active_profiles.select_related('uid', 'voivodeship')
            if city:
                location_profiles = location_profiles.filter(city=city)
            if voivodeship:
                location_profiles = location_profiles.filter(voivodeship__name=voivodeship)
            context['location_profiles'] = location_profiles.order_by('uid__last_name', 'uid__first_name')
        else:
            context['location_profiles'] = []
        return context


def _can_manage_resource_entity(entity, user, profile):
    return entity.author_id == user.pk or entity.assigned_member_id == profile.pk or (entity.is_community_owned and user.is_active)


def _can_assign_resource_entity(entity, user, profile):
    return entity.author_id == user.pk or (entity.author_id is None and entity.assigned_member_id == profile.pk) or (entity.is_community_owned and user.is_active)


def _resource_manage_context(user, profile, resource_form=None, edit_entity=None, form_action=None):
    entities = list(
        Entity.objects.filter(entity_type=Entity.Type.RESOURCE)
        .filter(Q(author=user) | Q(assigned_member=profile) | Q(is_community_owned=True))
        .select_related('author', 'assigned_member__uid')
        .order_by('resource_kind', 'name', 'pk')
    )
    legacy_source_pks = dict(LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, entity_id__in=[entity.pk for entity in entities]).values_list('entity_id', 'source_pk'))
    for entity in entities:
        source_pk = legacy_source_pks.get(entity.pk)
        if source_pk is not None:
            entity.edit_url = reverse('bookkeeping:resource_update', kwargs={'pk': source_pk})
            entity.delete_url = reverse('bookkeeping:resource_delete', kwargs={'pk': source_pk})
            entity.toggle_closed_url = reverse('bookkeeping:resource_toggle_closed', kwargs={'pk': source_pk})
        else:
            entity.edit_url = reverse('bookkeeping:resource_entity_update', kwargs={'pk': entity.pk})
            entity.delete_url = reverse('bookkeeping:resource_entity_delete', kwargs={'pk': entity.pk})
            entity.toggle_closed_url = reverse('bookkeeping:resource_entity_toggle_closed', kwargs={'pk': entity.pk})

    return {
        'resource_form': resource_form if resource_form is not None else ResourceEntityForm(profile=profile),
        'resource_form_action': form_action or reverse('bookkeeping:resource_create'),
        'active_listings': [entity for entity in entities if not entity.is_closed],
        'closed_listings': [entity for entity in entities if entity.is_closed],
        'edit_listing': edit_entity,
    }


@login_required
def resource_manage(request):
    profile = request.user.uzytkownik
    return render(request, 'bookkeeping/resource_manage.html', _resource_manage_context(request.user, profile))


def _save_resource_entity(entity, form, user, *, create=False):
    entity.entity_type = Entity.Type.RESOURCE
    entity.name = form.cleaned_data['name']
    entity.description = form.cleaned_data['description']
    entity.resource_kind = form.cleaned_data['kind']
    if create:
        entity.author = user
    if form.can_assign:
        if form.cleaned_data['assignment_scope'] == Entity.AssignmentScope.COMMUNITY:
            entity.is_community_owned = True
            entity.assigned_member = None
        else:
            entity.is_community_owned = False
            entity.assigned_member = form.cleaned_data['assigned_member']
    if create:
        entity.full_clean()
    entity.save()
    return entity


def _sync_legacy_resource_shadow(entity, listing):
    ResourceListing.objects.filter(pk=listing.pk).update(
        profile_id=entity.assigned_member_id if not entity.is_community_owned else listing.profile_id,
        name=entity.name,
        description=entity.description,
        kind=entity.resource_kind,
        is_closed=entity.is_closed,
        updated_at=entity.updated_at,
    )


def _render_resource_update(request, entity, profile, *, legacy_listing=None, form_action):
    can_assign = _can_assign_resource_entity(entity, request.user, profile)
    form = ResourceEntityForm(request.POST if request.method == 'POST' else None, profile=profile, entity=entity, can_assign=can_assign)
    if request.method == 'POST' and form.is_valid():
        try:
            with db_transaction.atomic():
                _save_resource_entity(entity, form, request.user)
                if legacy_listing:
                    _sync_legacy_resource_shadow(entity, legacy_listing)
        except (IntegrityError, ValidationError) as error:
            if isinstance(error, IntegrityError):
                form.add_error('name', _('This item is already assigned with this type.'))
            else:
                form.add_error(None, error)
        else:
            return redirect('bookkeeping:resource_manage')

    context = _resource_manage_context(request.user, profile, resource_form=form, edit_entity=entity, form_action=form_action)
    return render(request, 'bookkeeping/resource_manage.html', context)


@login_required
@require_POST
def resource_create(request):
    profile = request.user.uzytkownik
    form = ResourceEntityForm(request.POST, profile=profile)
    if not form.is_valid():
        return render(request, 'bookkeeping/resource_manage.html', _resource_manage_context(request.user, profile, form))

    try:
        with db_transaction.atomic():
            _save_resource_entity(Entity(entity_type=Entity.Type.RESOURCE), form, request.user, create=True)
    except IntegrityError:
        form.add_error('name', _('This item is already assigned with this type.'))
    except ValidationError as error:
        form.add_error(None, error)
    if form.errors:
        return render(request, 'bookkeeping/resource_manage.html', _resource_manage_context(request.user, profile, form))
    return redirect('bookkeeping:resource_manage')


@login_required
def resource_update(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    listing = ResourceListing.objects.filter(pk=pk).first()
    return _render_resource_update(request, entity, profile, legacy_listing=listing, form_action=reverse('bookkeeping:resource_update', kwargs={'pk': pk}))


@login_required
def resource_entity_update(request, pk):
    profile = request.user.uzytkownik
    entity = get_object_or_404(Entity, pk=pk, entity_type=Entity.Type.RESOURCE)
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    source_pk = LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, entity_id=entity.pk).values_list('source_pk', flat=True).first()
    legacy_listing = ResourceListing.objects.filter(pk=source_pk).first() if source_pk else None
    return _render_resource_update(request, entity, profile, legacy_listing=legacy_listing, form_action=reverse('bookkeeping:resource_entity_update', kwargs={'pk': entity.pk}))


def _delete_resource_entity(entity, legacy_listing=None):
    with db_transaction.atomic():
        entity.delete()
        if legacy_listing:
            legacy_listing.delete()


@login_required
@require_POST
def resource_delete(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    listing = ResourceListing.objects.filter(pk=pk).first()
    _delete_resource_entity(entity, listing)
    return redirect('bookkeeping:resource_manage')


@login_required
@require_POST
def resource_entity_delete(request, pk):
    profile = request.user.uzytkownik
    entity = get_object_or_404(Entity, pk=pk, entity_type=Entity.Type.RESOURCE)
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    source_pk = LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, entity_id=entity.pk).values_list('source_pk', flat=True).first()
    legacy_listing = ResourceListing.objects.filter(pk=source_pk).first() if source_pk else None
    _delete_resource_entity(entity, legacy_listing)
    return redirect('bookkeeping:resource_manage')


def _set_resource_closed(entity, closed_value, legacy_listing=None):
    with db_transaction.atomic():
        entity.is_closed = closed_value
        entity.save(update_fields=['is_closed', 'updated_at'])
        if legacy_listing:
            ResourceListing.objects.filter(pk=legacy_listing.pk).update(is_closed=closed_value, updated_at=entity.updated_at)


@login_required
@require_POST
def resource_toggle_closed(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    listing = ResourceListing.objects.filter(pk=pk).first()
    closed_value = request.POST.get('closed')
    if closed_value not in ('0', '1'):
        return HttpResponseBadRequest()
    _set_resource_closed(entity, closed_value == '1', listing)
    return redirect('bookkeeping:resource_manage')


@login_required
@require_POST
def resource_entity_toggle_closed(request, pk):
    profile = request.user.uzytkownik
    entity = get_object_or_404(Entity, pk=pk, entity_type=Entity.Type.RESOURCE)
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    closed_value = request.POST.get('closed')
    if closed_value not in ('0', '1'):
        return HttpResponseBadRequest()
    source_pk = LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, entity_id=entity.pk).values_list('source_pk', flat=True).first()
    legacy_listing = ResourceListing.objects.filter(pk=source_pk).first() if source_pk else None
    _set_resource_closed(entity, closed_value == '1', legacy_listing)
    return redirect('bookkeeping:resource_manage')


@login_required
def resource_search(request):
    query = (request.GET.get('q') or '').strip()
    kind = request.GET.get('kind')
    listings = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False).filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
    if kind in Entity.ResourceKind.values:
        listings = listings.filter(resource_kind=kind)
    if query:
        listings = listings.filter(Q(name__icontains=query) | Q(description__icontains=query))
    items = listings.values('name').annotate(id=Min('pk')).order_by('name')[:20]
    return JsonResponse({'items': [{'id': item['id'], 'name': item['name']} for item in items]})


# #########################  Category ###########################


class CategoryListView(BookkeepingListView):
    model = Category
    template_name = 'bookkeeping/category_list.html'
    create_url_name = 'bookkeeping:category_create'
    create_label = _('Add category')

    def get_queryset(self):
        search_query = self.request.GET.get('q', '').strip()
        queryset = Category.objects.all()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        return queryset


class CategoryDetailView(BookkeepingDetailView):
    model = Category
    template_name = 'bookkeeping/category_detail.html'
    context_object_name = 'category'


class CategoryCreateView(BookkeepingCreateView):
    model = Category
    fields = ['name']
    success_url_name = 'bookkeeping:category_list'


class CategoryUpdateView(BookkeepingUpdateView):
    model = Category
    fields = ['name']
    success_url_name = 'bookkeeping:category_list'


class CategoryDeleteView(ProtectedDeleteView):
    model = Category
    success_url = reverse_lazy('bookkeeping:category_list')
    protect_field = 'category'
    protect_message = _("Cannot delete category because it is in use. Remove all transactions that use it first.")


# #########################  Partner ###########################


class PartnerListView(BookkeepingListView):
    model = Partner
    template_name = 'bookkeeping/partner_list.html'
    context_object_name = 'partners'
    create_url_name = 'bookkeeping:partner_create'
    create_label = _('Add partner')

    def get_queryset(self):
        sort = self.request.GET.get('sort', 'name')
        order = self.request.GET.get('order', 'asc')
        search_query = self.request.GET.get('q', '').strip()
        allowed = ['name', 'city', 'country', 'web_page', 'notes']
        if sort not in [*allowed, 'none']:
            sort = 'name'
        if sort == 'none':
            order = None
        elif order not in ('asc', 'desc'):
            order = 'asc'
        prefix = '-' if order == 'desc' else ''
        queryset = Partner.objects.all()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(city__icontains=search_query)
                | Q(country__icontains=search_query)
                | Q(street__icontains=search_query)
                | Q(house_number__icontains=search_query)
                | Q(web_page__icontains=search_query)
                | Q(notes__icontains=search_query)
            )
        return queryset if sort == 'none' else queryset.order_by(f'{prefix}{sort}')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_sort = self.request.GET.get('sort', 'name')
        current_order = self.request.GET.get('order', 'asc')
        fields = (('name', _('Name'), 'list'), ('city', _('City'), 'map-marker-alt'), ('web_page', _('Web Page'), 'globe'), ('notes', _('Notes'), 'file-lines'))
        if current_sort not in [field for field, _, _ in fields] + ['none']:
            current_sort = 'name'
        if current_sort == 'none':
            current_order = None
        elif current_order not in ('asc', 'desc'):
            current_order = 'asc'
        search_query = self.request.GET.get('q', '').strip()
        query_suffix = f'&q={quote_plus(search_query)}' if search_query else ''
        context['current_sort'] = current_sort
        context['current_order'] = current_order

        def state(field):
            return current_order if current_sort == field else 'none'

        def next_state(field):
            current = state(field)
            return 'asc' if current == 'none' else 'desc' if current == 'asc' else 'none'

        context['toolbar_sort_items'] = [
            {
                'url': f'?sort={field}&order={next_state(field)}{query_suffix}' if next_state(field) != 'none' else f'?sort=none{query_suffix}',
                'label': label,
                'active': current_sort == field,
                'state': state(field),
                'pre_icon': icon,
                'icon': 'up' if state(field) == 'asc' else 'down' if state(field) == 'desc' else None,
            }
            for field, label, icon in fields
        ]
        return context


class PartnerDetailView(BookkeepingDetailView):
    model = Partner
    template_name = 'bookkeeping/partner_detail.html'
    context_object_name = 'partner'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_ordering = Partner.objects.order_by('pk')
        ids = list(current_ordering.values_list('pk', flat=True))
        current_index = ids.index(self.object.pk)
        context['prev_partner'] = current_ordering[current_index - 1] if current_index > 0 else None
        context['next_partner'] = current_ordering[current_index + 1] if current_index < len(ids) - 1 else None
        return context


class PartnerCreateView(BookkeepingCreateView):
    model = Partner
    fields = ['name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number', 'notes']
    success_url_name = 'bookkeeping:partner_list'


class PartnerUpdateView(BookkeepingUpdateView):
    model = Partner
    fields = ['name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number', 'notes']
    success_url_name = 'bookkeeping:partner_list'


class PartnerDeleteView(ProtectedDeleteView):
    model = Partner
    success_url = reverse_lazy('bookkeeping:partner_list')
    protect_field = 'partner'
    protect_message = _("Cannot delete partner because it is in use. Remove all transactions that use it first.")


# #########################  Transaction ###########################


def _transaction_queryset(search_query=''):
    queryset = Transaction.objects.select_related('author', 'partner', 'category', 'entity', 'asset')
    if search_query:
        queryset = queryset.filter(
            Q(partner__name__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(entity__code__icontains=search_query)
            | Q(asset__code__icontains=search_query)
            | Q(note__icontains=search_query)
            | Q(author__username__icontains=search_query)
        )
    return queryset.order_by('-payment_received_date', '-id')


class TransactionListView(BookkeepingListView):
    model = Transaction
    template_name = 'bookkeeping/transaction_list.html'
    context_object_name = 'transactions'
    create_url_name = 'bookkeeping:transaction_create'
    create_label = _('Add transaction')

    def get_queryset(self):
        return _transaction_queryset(self.request.GET.get('q', '').strip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        detail_query = self.request.GET.urlencode()
        for item in context['transactions']:
            item.detail_url = reverse('bookkeeping:transaction_detail', kwargs={'pk': item.pk})
            if detail_query:
                item.detail_url = f"{item.detail_url}?{detail_query}"
        return context


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction

    def get_queryset(self):
        return Transaction.objects.select_related('author', 'partner', 'category', 'entity', 'asset')

    template_name = 'bookkeeping/transaction_detail.html'
    context_object_name = 'transaction'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '').strip()
        context.update(build_detail_navigation(self.request, _transaction_queryset(search_query), self.object.pk, 'bookkeeping:transaction_detail'))
        return context


def _asset_decimal_places_json():
    entities = Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET, legacy_references__source_model=LEGACY_FINANCIAL_ASSET_SOURCE).distinct()
    return json.dumps({str(entity.pk): entity.decimal_places for entity in entities})


class TransactionCreateView(LoginRequiredMixin, View):
    template_name = 'bookkeeping/transaction_form.html'

    def get(self, request):
        transaction_form = TransactionForm()
        return render(request, self.template_name, {'transaction_form': transaction_form, 'asset_decimal_places_json': _asset_decimal_places_json()})

    def post(self, request):
        transaction_form = TransactionForm(request.POST)

        if transaction_form.is_valid():
            transaction_data = transaction_form.cleaned_data

            transaction = Transaction(
                type=transaction_data['type'],
                entity=transaction_data['entity'],
                partner=transaction_data['partner'],
                category=transaction_data['category'],
                amount=transaction_data['amount'],
                payment_received_date=transaction_data['payment_received_date'],
                note=transaction_data['note'],
                author=request.user,
            )
            transaction.created_date = timezone.now()
            transaction.save()
            transaction_url = build_site_url(reverse('bookkeeping:transaction_detail', kwargs={'pk': transaction.pk}))
            db_transaction.on_commit(lambda: transaction_created.send(sender=Transaction, transaction=transaction, url=transaction_url))

            return redirect('bookkeeping:transaction_detail', pk=transaction.pk)

        return render(request, self.template_name, {'transaction_form': transaction_form, 'asset_decimal_places_json': _asset_decimal_places_json()})


class TransactionClaimView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not request.user.is_active:
            return HttpResponseForbidden()
        with db_transaction.atomic():
            transaction = get_object_or_404(Transaction.objects.select_for_update(), pk=pk)
            if transaction.author_id is not None:
                return redirect('bookkeeping:transaction_detail', pk=pk)
            transaction.author = request.user
            transaction.save(update_fields=['author'])
        return redirect('bookkeeping:transaction_detail', pk=pk)


class TransactionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'bookkeeping/transaction_form.html'

    def test_func(self):
        transaction = self.get_object()
        return self.request.user == transaction.author

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url
        return reverse_lazy('bookkeeping:transaction_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Saved.'))
        transaction = self.object
        transaction_url = build_site_url(reverse('bookkeeping:transaction_detail', kwargs={'pk': transaction.pk}))
        db_transaction.on_commit(lambda: transaction_updated.send(sender=Transaction, transaction=transaction, url=transaction_url))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' in context:
            context['transaction_form'] = context['form']
        context['asset_decimal_places_json'] = _asset_decimal_places_json()
        return context


class TransactionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Transaction
    template_name = 'bookkeeping/transaction_confirm_delete.html'
    success_url = reverse_lazy('bookkeeping:transaction_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('bookkeeping:transaction_detail', kwargs={'pk': self.object.pk})
        return context

    def test_func(self):
        transaction = self.get_object()
        return self.request.user == transaction.author


# #########################  Report ###########################


class ReportView(LoginRequiredMixin, View):
    template_name = 'bookkeeping/report_list.html'

    def get(self, request, year=None):
        try:
            year = int(request.GET.get('year', year)) if year or request.GET.get('year') else timezone.now().year
        except (ValueError, TypeError):
            year = timezone.now().year

        year_pivot, year_assets, year_totals = category_breakdown(year=year)
        all_pivot, all_assets, all_totals = category_breakdown()

        available_years = Transaction.objects.dates('payment_received_date', 'year').values_list('payment_received_date__year', flat=True).distinct().order_by('-payment_received_date__year')

        context = {
            'year_pivot': year_pivot,
            'year_assets': year_assets,
            'year_totals': year_totals,
            'year_uses_fallback': len(year_assets) > self.MAX_ASSETS_FOR_PIVOT,
            'all_pivot': all_pivot,
            'all_assets': all_assets,
            'all_totals': all_totals,
            'all_uses_fallback': len(all_assets) > self.MAX_ASSETS_FOR_PIVOT,
            'year': year,
            'available_years': available_years,
        }

        return render(request, self.template_name, context)

    # Próg powyżej którego pivot kategorie × aktywa staje się nieczytelny (za szeroki).
    # Wtedy template przełącza się na fallback "sekcje per waluta" (Wzorzec 1).
    MAX_ASSETS_FOR_PIVOT = 5
