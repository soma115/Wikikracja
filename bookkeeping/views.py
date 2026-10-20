import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db import transaction as db_transaction
from django.db.models import CharField, Count, Min, OuterRef, Q, Subquery
from django.db.models.functions import Cast
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryItemsAPI, CategoryReorderAPI
from core.signals import transaction_created, transaction_updated
from core.utils import build_detail_navigation, build_site_url
from home.navigation import default_toolbar_views
from obywatele.models import Uzytkownik
from resources.models import LEGACY_FINANCIAL_ASSET_SOURCE, LEGACY_RESOURCE_LISTING_SOURCE, Entity, LegacyEntityReference
from resources.services import match_active_offers_for_needs, search_entities

from .forms import AssetForm, PartnerForm, ResourceEntityForm, TransactionForm
from .models import Category, Partner, Transaction
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
        queryset = Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).annotate(legacy_asset_pk=Subquery(legacy_asset_pk))
        if search_query:
            queryset = queryset.filter(Q(code__icontains=search_query) | Q(name__icontains=search_query) | Q(symbol__icontains=search_query))
        return queryset.order_by('code', 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for entity in context['object_list']:
            _set_financial_asset_urls(entity)
        return context


def _set_financial_asset_urls(entity):
    if not hasattr(entity, 'legacy_asset_pk'):
        legacy_asset_pk = LegacyEntityReference.objects.filter(source_model=LEGACY_FINANCIAL_ASSET_SOURCE, entity_id=entity.pk).values_list('source_pk', flat=True).first()
        entity.legacy_asset_pk = legacy_asset_pk
    else:
        legacy_asset_pk = entity.legacy_asset_pk

    if legacy_asset_pk is None:
        route_names = ('bookkeeping:asset_entity_detail', 'bookkeeping:asset_entity_update', 'bookkeeping:asset_entity_delete')
        route_pk = entity.pk
    else:
        route_names = ('bookkeeping:asset_detail', 'bookkeeping:asset_update', 'bookkeeping:asset_delete')
        route_pk = legacy_asset_pk
    entity.detail_url, entity.update_url, entity.delete_url = (reverse(route_name, kwargs={'pk': route_pk}) for route_name in route_names)


def _financial_entity_for_legacy_asset_pk(source_pk):
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=source_pk, entity__entity_type=Entity.Type.FINANCIAL_ASSET)
    entity = reference.entity
    entity.legacy_asset_pk = source_pk
    return entity


def _financial_entity_for_entity_pk(entity_pk):
    return get_object_or_404(Entity, pk=entity_pk, entity_type=Entity.Type.FINANCIAL_ASSET)


class AssetDetailView(BookkeepingDetailView):
    model = Entity
    template_name = 'bookkeeping/asset_detail.html'
    context_object_name = 'asset'

    def get_object(self, queryset=None):
        return _financial_entity_for_legacy_asset_pk(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _set_financial_asset_urls(context['asset'])
        return context


class AssetEntityDetailView(AssetDetailView):
    def get_object(self, queryset=None):
        return _financial_entity_for_entity_pk(self.kwargs['pk'])


class AssetCreateView(BookkeepingCreateView):
    model = Entity
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url_name = 'bookkeeping:asset_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Entity(entity_type=Entity.Type.FINANCIAL_ASSET)
        return kwargs


class AssetUpdateView(BookkeepingUpdateView):
    model = Entity
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url_name = 'bookkeeping:asset_list'

    def get_object(self, queryset=None):
        return _financial_entity_for_legacy_asset_pk(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _set_financial_asset_urls(context['object'])
        return context


class AssetEntityUpdateView(AssetUpdateView):
    def get_object(self, queryset=None):
        return _financial_entity_for_entity_pk(self.kwargs['pk'])


class AssetDeleteView(ProtectedDeleteView):
    model = Entity
    template_name = 'bookkeeping/asset_confirm_delete.html'
    success_url = reverse_lazy('bookkeeping:asset_list')
    protect_field = 'entity'
    protect_message = _("Cannot delete asset because it is in use. Remove all transactions that use it first.")

    def get_queryset(self):
        return Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET)

    def get_object(self, queryset=None):
        return _financial_entity_for_legacy_asset_pk(self.kwargs['pk'])


class AssetEntityDeleteView(AssetDeleteView):
    def get_object(self, queryset=None):
        return _financial_entity_for_entity_pk(self.kwargs['pk'])


# #########################  Resource listings ###########################


class ResourceListView(BookkeepingListView):
    model = Entity
    template_name = 'bookkeeping/resource_list.html'
    context_object_name = 'resource_listings'
    paginate_by = 24
    create_url_name = 'bookkeeping:resource_list'
    create_label = _('Add resource')

    def get_queryset(self):
        params = self.request.GET
        self.search_values = {
            'entity_type': params.get('entity_type', Entity.Type.RESOURCE),
            'q': (params.get('q') or '').strip(),
            'kind': params.get('kind', ''),
            'city': (params.get('city') or '').strip(),
            'voivodeship': (params.get('voivodeship') or '').strip(),
            'country': (params.get('country') or '').strip(),
            'status': params.get('status', 'active'),
            'assignment': params.get('assignment', 'all'),
        }
        if self.search_values['entity_type'] not in ('all', *Entity.Type.values):
            self.search_values['entity_type'] = Entity.Type.RESOURCE
        if self.search_values['status'] not in ('active', 'closed', 'all'):
            self.search_values['status'] = 'active'
        if self.search_values['assignment'] not in ('all', *Entity.AssignmentScope.values):
            self.search_values['assignment'] = 'all'

        queryset = search_entities(
            self.request.user,
            entity_type=self.search_values['entity_type'],
            query=self.search_values['q'],
            resource_kind=self.search_values['kind'],
            city=self.search_values['city'],
            voivodeship=self.search_values['voivodeship'],
            country=self.search_values['country'],
            status=self.search_values['status'],
            assignment=self.search_values['assignment'],
        )
        profile_id = (params.get('profile') or '').strip()
        if profile_id:
            try:
                profile_pk = int(profile_id) if profile_id.isascii() and profile_id.isdecimal() else 0
            except ValueError:
                profile_pk = 0
            max_pk = connection.ops.integer_field_range(Uzytkownik._meta.pk.get_internal_type())[1]
            queryset = queryset.filter(assigned_member_id=profile_pk) if 0 < profile_pk <= max_pk else queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_entities = context['resource_listings']
        resources = [entity for entity in page_entities if entity.entity_type == Entity.Type.RESOURCE]
        profile = self.request.user.uzytkownik
        _set_resource_management_urls(resources)
        for entity in resources:
            entity.can_manage = _can_manage_resource_entity(entity, self.request.user, profile)
        context['entity_results'] = page_entities
        context['resource_listings'] = resources
        totals = self.object_list.aggregate(
            offers=Count('pk', filter=Q(entity_type=Entity.Type.RESOURCE) & ~Q(resource_kind=Entity.ResourceKind.NEED)),
            needs=Count('pk', filter=Q(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.NEED)),
            financial_assets=Count('pk', filter=Q(entity_type=Entity.Type.FINANCIAL_ASSET)),
        )
        active_profiles = Uzytkownik.objects.filter(uid__is_active=True)
        context['offer_listings'] = [entity for entity in resources if entity.resource_kind != Entity.ResourceKind.NEED]
        context['need_listings'] = [entity for entity in resources if entity.resource_kind == Entity.ResourceKind.NEED]
        context['offer_count'] = totals['offers']
        context['need_count'] = totals['needs']
        context['financial_assets'] = [entity for entity in page_entities if entity.entity_type == Entity.Type.FINANCIAL_ASSET]
        context['financial_asset_count'] = totals['financial_assets']
        context['entity_types'] = [('all', _('All entity types')), (Entity.Type.FINANCIAL_ASSET, _('Financial asset')), (Entity.Type.RESOURCE, _('Resource'))]
        context['resource_kinds'] = Entity.ResourceKind.choices
        context['voivodeships'] = active_profiles.exclude(voivodeship__isnull=True).values_list('voivodeship__name', flat=True).distinct().order_by('voivodeship__name')
        context['status_choices'] = [('active', _('Active')), ('closed', _('Closed')), ('all', _('All statuses'))]
        context['assignment_choices'] = [
            ('all', _('All assignments')),
            (Entity.AssignmentScope.MEMBER, _('Assigned to a member')),
            (Entity.AssignmentScope.COMMUNITY, _('Shared community ownership')),
            (Entity.AssignmentScope.UNASSIGNED, _('Unassigned')),
        ]
        context['search_values'] = {**self.search_values, 'profile': self.request.GET.get('profile', '')}
        context.setdefault('resource_form', ResourceEntityForm(profile=profile))
        context.setdefault('resource_form_action', reverse('bookkeeping:resource_create'))
        context.setdefault('open_resource_modal', self.request.GET.get('add_resource') == '1')
        context['matching_needs'] = match_active_offers_for_needs(self.request.user, profile)
        context['cta_url'] = ''
        context['cta_button'] = 'resourceAddButton'
        context['cta_modal_id'] = 'resource-form'
        context['cta_label'] = self.create_label
        context['cta_icon'] = 'plus'

        query = self.search_values['q']
        kind = self.search_values['kind']
        city = self.search_values['city']
        voivodeship = self.search_values['voivodeship']
        if (
            self.search_values['entity_type'] == Entity.Type.RESOURCE
            and self.search_values['status'] == 'active'
            and self.search_values['assignment'] == 'all'
            and (city or voivodeship)
            and not query
            and kind not in Entity.ResourceKind.values
            and not self.request.GET.get('profile')
        ):
            location_profiles = active_profiles.select_related('uid', 'voivodeship')
            if city:
                location_profiles = location_profiles.filter(city__icontains=city)
            if voivodeship:
                location_profiles = location_profiles.filter(voivodeship__name__iexact=voivodeship)
            context['location_profiles'] = location_profiles.order_by('uid__last_name', 'uid__first_name')
        else:
            context['location_profiles'] = []
        return context


def _can_manage_resource_entity(entity, user, profile):
    return entity.author_id == user.pk or entity.assigned_member_id == profile.pk or (entity.is_community_owned and user.is_active)


def _can_assign_resource_entity(entity, user, profile):
    return entity.author_id == user.pk or (entity.author_id is None and entity.assigned_member_id == profile.pk) or (entity.is_community_owned and user.is_active)


def _set_resource_management_urls(entities):
    legacy_source_pks = dict(LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, entity_id__in=[entity.pk for entity in entities]).values_list('entity_id', 'source_pk'))
    for entity in entities:
        source_pk = legacy_source_pks.get(entity.pk)
        if source_pk is None:
            route_names = ('bookkeeping:resource_entity_update', 'bookkeeping:resource_entity_delete', 'bookkeeping:resource_entity_toggle_closed')
            route_pk = entity.pk
        else:
            route_names = ('bookkeeping:resource_update', 'bookkeeping:resource_delete', 'bookkeeping:resource_toggle_closed')
            route_pk = source_pk
        entity.edit_url, entity.delete_url, entity.toggle_closed_url = (reverse(route_name, kwargs={'pk': route_pk}) for route_name in route_names)


def _render_resource_list(request, **context):
    view = ResourceListView(extra_context=context)
    view.setup(request)
    view.object_list = view.get_queryset()
    return render(request, view.template_name, view.get_context_data())


def _save_resource_entity(entity, form, user, *, create=False):
    entity.entity_type = Entity.Type.RESOURCE
    entity.name = form.cleaned_data['name']
    entity.description = form.cleaned_data['description']
    entity.resource_kind = form.cleaned_data['kind']
    entity.country = form.cleaned_data['country']
    entity.city = form.cleaned_data['city']
    entity.street = form.cleaned_data['street']
    entity.house_number = form.cleaned_data['house_number']
    entity.apartment_number = form.cleaned_data['apartment_number']
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


def _render_resource_update(request, entity, profile, *, form_action):
    can_assign = _can_assign_resource_entity(entity, request.user, profile)
    form = ResourceEntityForm(request.POST if request.method == 'POST' else None, profile=profile, entity=entity, can_assign=can_assign)
    if request.method == 'POST' and form.is_valid():
        try:
            with db_transaction.atomic():
                _save_resource_entity(entity, form, request.user)
        except (IntegrityError, ValidationError) as error:
            if isinstance(error, IntegrityError):
                form.add_error('name', _('This item is already assigned with this type.'))
            else:
                form.add_error(None, error)
        else:
            return redirect('bookkeeping:resource_list')

    return _render_resource_list(request, resource_form=form, resource_form_action=form_action, edit_listing=entity)


@login_required
@require_POST
def resource_create(request):
    profile = request.user.uzytkownik
    form = ResourceEntityForm(request.POST, profile=profile)
    if not form.is_valid():
        return _render_resource_list(request, resource_form=form, open_resource_modal=True)

    try:
        with db_transaction.atomic():
            _save_resource_entity(Entity(entity_type=Entity.Type.RESOURCE), form, request.user, create=True)
    except IntegrityError:
        form.add_error('name', _('This item is already assigned with this type.'))
    except ValidationError as error:
        form.add_error(None, error)
    if form.errors:
        return _render_resource_list(request, resource_form=form, open_resource_modal=True)
    return redirect('bookkeeping:resource_list')


@login_required
def resource_update(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    return _render_resource_update(request, entity, profile, form_action=reverse('bookkeeping:resource_update', kwargs={'pk': pk}))


@login_required
def resource_entity_update(request, pk):
    profile = request.user.uzytkownik
    entity = get_object_or_404(Entity, pk=pk, entity_type=Entity.Type.RESOURCE)
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    return _render_resource_update(request, entity, profile, form_action=reverse('bookkeeping:resource_entity_update', kwargs={'pk': entity.pk}))


def _delete_resource_entity(entity):
    with db_transaction.atomic():
        entity.delete()


@login_required
@require_POST
def resource_delete(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    _delete_resource_entity(entity)
    return redirect('bookkeeping:resource_list')


@login_required
@require_POST
def resource_entity_delete(request, pk):
    profile = request.user.uzytkownik
    entity = get_object_or_404(Entity, pk=pk, entity_type=Entity.Type.RESOURCE)
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    _delete_resource_entity(entity)
    return redirect('bookkeeping:resource_list')


def _set_resource_closed(entity, closed_value):
    with db_transaction.atomic():
        entity.is_closed = closed_value
        entity.save(update_fields=['is_closed', 'updated_at'])


@login_required
@require_POST
def resource_toggle_closed(request, pk):
    profile = request.user.uzytkownik
    reference = get_object_or_404(LegacyEntityReference.objects.select_related('entity'), source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=pk, entity__entity_type=Entity.Type.RESOURCE)
    entity = reference.entity
    if not _can_manage_resource_entity(entity, request.user, profile):
        raise Http404
    closed_value = request.POST.get('closed')
    if closed_value not in ('0', '1'):
        return HttpResponseBadRequest()
    _set_resource_closed(entity, closed_value == '1')
    return redirect('bookkeeping:resource_list')


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
    _set_resource_closed(entity, closed_value == '1')
    return redirect('bookkeeping:resource_list')


@login_required
def resource_search(request):
    query = (request.GET.get('q') or '').strip()
    kind = request.GET.get('kind')
    entity_type = request.GET.get('entity_type')
    if entity_type and entity_type not in ('all', Entity.Type.RESOURCE):
        return JsonResponse({'items': []})
    listings = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False).filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
    if kind in Entity.ResourceKind.values:
        listings = listings.filter(resource_kind=kind)
    if query:
        listings = listings.filter(Q(name__icontains=query) | Q(description__icontains=query))
    items = listings.values('name').annotate(id=Min('pk')).order_by('name')[:20]
    return JsonResponse({'items': [{'id': item['id'], 'name': item['name']} for item in items]})


# #########################  Category ###########################


def _category_name_error(name, *, exclude_pk=None):
    if not name:
        return _('Category name is required.')
    if len(name) > Category._meta.get_field('name').max_length:
        return _('Category name is too long.')
    duplicates = Category.objects.filter(name=name)
    if exclude_pk is not None:
        duplicates = duplicates.exclude(pk=exclude_pk)
    if duplicates.exists():
        return _('A category with this name already exists.')
    return None


class BookkeepingCategoryAPI(CategoryAPIBase):
    model = Category
    related_count_field = 'transaction'
    order_field = 'order'

    def post(self, request):
        name = (request.POST.get('name') or '').strip()
        error = _category_name_error(name)
        if error:
            return JsonResponse({'error': str(error)}, status=400)
        try:
            return super().post(request)
        except IntegrityError:
            return JsonResponse({'error': str(_('A category with this name already exists.'))}, status=409)


class BookkeepingCategoryEditAPI(CategoryEditAPI):
    model = Category

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        if category.is_protected:
            return JsonResponse({'error': str(_('This category is protected and cannot be edited.'))}, status=403)
        name = (request.POST.get('name') or '').strip()
        error = _category_name_error(name, exclude_pk=category.pk)
        if error:
            return JsonResponse({'error': str(error)}, status=400)
        try:
            return super().post(request, pk)
        except IntegrityError:
            return JsonResponse({'error': str(_('A category with this name already exists.'))}, status=409)


class BookkeepingCategoryDeleteAPI(CategoryDeleteAPI):
    model = Category

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        if category.is_protected:
            return JsonResponse({'error': str(_('This category is protected and cannot be deleted.'))}, status=403)
        if category.transaction_set.exists():
            return JsonResponse({'error': str(CategoryDeleteView.protect_message)}, status=409)
        category.delete()
        self.after_write()
        return JsonResponse({'ok': True})


class BookkeepingCategoryItemsAPI(CategoryItemsAPI):
    model = Category
    related_field = 'transaction_set'
    item_label_field = 'partner__name'


class BookkeepingCategoryReorderAPI(CategoryReorderAPI):
    model = Category
    order_field = 'order'


class CategoryListView(BookkeepingListView):
    model = Category
    template_name = 'bookkeeping/category_list.html'
    create_url_name = None
    create_label = _('Add category')

    def get_queryset(self):
        search_query = self.request.GET.get('q', '').strip()
        queryset = Category.objects.all()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(cta_url='', cta_button='manageCategoriesButton', cta_modal_id='manageCategoriesModal', cta_icon='gear', cta_label=_('Manage categories'))
        return context


class CategoryDetailView(BookkeepingDetailView):
    model = Category
    template_name = 'bookkeeping/category_detail.html'
    context_object_name = 'category'


class CategoryCreateView(BookkeepingCreateView):
    model = Category
    fields = ['name', 'description']
    success_url_name = 'bookkeeping:category_list'


class CategoryUpdateView(BookkeepingUpdateView):
    model = Category
    fields = ['name', 'description']
    success_url_name = 'bookkeeping:category_list'

    def get_object(self, queryset=None):
        category = super().get_object(queryset)
        if category.is_protected:
            raise Http404
        return category


class CategoryDeleteView(ProtectedDeleteView):
    model = Category
    success_url = reverse_lazy('bookkeeping:category_list')
    protect_field = 'category'
    protect_message = _("Cannot delete category because it is in use. Remove all transactions that use it first.")

    def get_object(self, queryset=None):
        category = super().get_object(queryset)
        if category.is_protected:
            raise Http404
        return category


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
    form_class = PartnerForm
    success_url_name = 'bookkeeping:partner_list'


class PartnerUpdateView(BookkeepingUpdateView):
    model = Partner
    form_class = PartnerForm
    success_url_name = 'bookkeeping:partner_list'


class PartnerDeleteView(ProtectedDeleteView):
    model = Partner
    success_url = reverse_lazy('bookkeeping:partner_list')
    protect_field = 'partner'
    protect_message = _("Cannot delete partner because it is in use. Remove all transactions that use it first.")


# #########################  Transaction ###########################


def _transaction_list_filters(params):
    category_ids = []
    max_category_pk = connection.ops.integer_field_range(Category._meta.pk.get_internal_type())[1]
    for raw_category_id in params.getlist('category'):
        try:
            category_id = int(raw_category_id) if raw_category_id.isascii() and raw_category_id.isdecimal() else 0
        except ValueError:
            category_id = 0
        if 0 < category_id <= max_category_pk:
            category_ids.append(category_id)

    category_ids = list(Category.objects.filter(pk__in=set(category_ids)).values_list('pk', flat=True))
    transaction_type = params.get('type', '')
    if transaction_type not in dict(Transaction.TYPES):
        transaction_type = ''

    def date_value(key):
        value = (params.get(key) or '').strip()
        if not value:
            return None
        try:
            return parse_date(value)
        except ValueError:
            return None

    sort = params.get('sort', 'date')
    if sort not in ('date', 'none'):
        sort = 'date'
    order = params.get('order', 'desc')
    if order not in ('asc', 'desc'):
        order = 'desc'
    if sort == 'none':
        order = None

    search_query = (params.get('q') or '').strip()
    if len(search_query) < 2:
        search_query = ''

    return {
        'search_query': search_query,
        'category_ids': category_ids,
        'transaction_type': transaction_type,
        'date_from': date_value('date_from'),
        'date_to': date_value('date_to'),
        'date_from_value': (params.get('date_from') or '').strip(),
        'date_to_value': (params.get('date_to') or '').strip(),
        'sort': sort,
        'order': order,
    }


def _transaction_queryset(*, search_query='', category_ids=(), transaction_type='', date_from=None, date_to=None, sort='date', order='desc'):
    queryset = Transaction.objects.select_related('author', 'partner', 'category', 'entity')
    if search_query:
        queryset = queryset.annotate(_search_amount=Cast('amount', output_field=CharField()), _search_payment_date=Cast('payment_received_date', output_field=CharField()))
        search_filter = Q()
        for term in search_query.split():
            term_filter = (
                Q(partner__name__icontains=term)
                | Q(category__name__icontains=term)
                | Q(entity__code__icontains=term)
                | Q(entity__name__icontains=term)
                | Q(entity__symbol__icontains=term)
                | Q(note__icontains=term)
                | Q(author__username__icontains=term)
                | Q(author__first_name__icontains=term)
                | Q(author__last_name__icontains=term)
                | Q(_search_amount__icontains=term)
                | Q(_search_payment_date__icontains=term)
            )
            amount_query = term.replace(',', '.')
            if amount_query != term:
                term_filter |= Q(_search_amount__icontains=amount_query)
            try:
                amount_value = Decimal(amount_query)
                if amount_value.is_finite():
                    term_filter |= Q(amount=amount_value)
            except InvalidOperation:
                pass

            search_date = None
            try:
                search_date = parse_date(term)
            except ValueError:
                pass
            if search_date is None:
                for date_format in ('%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y'):
                    try:
                        search_date = datetime.strptime(term, date_format).date()
                        break
                    except ValueError:
                        continue
            if search_date is not None:
                term_filter |= Q(payment_received_date=search_date)

            normalized_term = term.casefold()
            for type_value, type_label in Transaction.TYPES:
                if normalized_term in str(type_label).casefold():
                    term_filter |= Q(type=type_value)
            search_filter |= term_filter
        queryset = queryset.filter(search_filter)
    if category_ids:
        queryset = queryset.filter(category_id__in=category_ids)
    if transaction_type:
        queryset = queryset.filter(type=transaction_type)
    if date_from:
        queryset = queryset.filter(payment_received_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(payment_received_date__lte=date_to)
    if sort == 'none':
        return queryset.order_by('pk')
    prefix = '-' if order == 'desc' else ''
    return queryset.order_by(f'{prefix}payment_received_date', f'{prefix}pk')


def _transaction_queryset_for_filters(filters):
    return _transaction_queryset(
        search_query=filters['search_query'],
        category_ids=filters['category_ids'],
        transaction_type=filters['transaction_type'],
        date_from=filters['date_from'],
        date_to=filters['date_to'],
        sort=filters['sort'],
        order=filters['order'],
    )


def _transaction_sort_items(request, filters):
    sort = filters['sort']
    order = filters['order']
    state = order if sort == 'date' else 'none'
    next_state = 'asc' if state == 'none' else 'desc' if state == 'asc' else 'none'
    params = request.GET.copy()
    params['sort'] = 'date' if next_state != 'none' else 'none'
    if next_state == 'none':
        params.pop('order', None)
    else:
        params['order'] = next_state
    query = params.urlencode()
    return [
        {
            'url': f"{reverse('bookkeeping:transaction_list')}?{query}",
            'label': _('Date'),
            'active': state != 'none',
            'state': state,
            'pre_icon': 'clock',
            'icon': 'up' if state == 'asc' else 'down' if state == 'desc' else None,
        }
    ]


class TransactionListView(BookkeepingListView):
    model = Transaction
    template_name = 'bookkeeping/transaction_list.html'
    context_object_name = 'transactions'
    create_url_name = 'bookkeeping:transaction_create'
    create_label = _('Add transaction')

    def get_queryset(self):
        self.filter_values = _transaction_list_filters(self.request.GET)
        return _transaction_queryset_for_filters(self.filter_values)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        detail_query = self.request.GET.urlencode()
        for item in context['transactions']:
            item.detail_url = reverse('bookkeeping:transaction_detail', kwargs={'pk': item.pk})
            if detail_query:
                item.detail_url = f"{item.detail_url}?{detail_query}"
        context.update(
            {
                'search_query': self.filter_values['search_query'],
                'category_list': list(Category.objects.order_by('order', 'name', 'pk')),
                'current_categories': self.filter_values['category_ids'],
                'current_sort': self.filter_values['sort'],
                'current_order': self.filter_values['order'],
                'toolbar_sort_items': _transaction_sort_items(self.request, self.filter_values),
            }
        )
        return context


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction

    def get_queryset(self):
        return Transaction.objects.select_related('author', 'partner', 'category', 'entity')

    template_name = 'bookkeeping/transaction_detail.html'
    context_object_name = 'transaction'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _transaction_list_filters(self.request.GET)
        context.update(build_detail_navigation(self.request, _transaction_queryset_for_filters(filters), self.object.pk, 'bookkeeping:transaction_detail'))
        return context


def _asset_decimal_places_json():
    entities = Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET)
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
