import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from .forms import AssetForm, TransactionForm
from .models import Asset, Category, Partner, Transaction
from .services import asset_balances, category_breakdown


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

        if 'delete_error' in self.request.session:
            context['error'] = self.request.session.pop('delete_error')

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self._related_transactions().exists():
            request.session['delete_error'] = self.protect_message
            return redirect(request.path)

        try:
            return super().delete(request, *args, **kwargs)
        except Exception as e:
            request.session['delete_error'] = str(e)
            return redirect(request.path)


# #########################  Asset ###########################


def _bookkeeping_toolbar(active_item, create_url=None, create_label=None):
    """Build toolbar data for bookkeeping list views."""
    items = [
        {'name': 'transactions', 'label': _('Transactions'), 'url_name': 'bookkeeping:transaction_list'},
        {'name': 'partners', 'label': _('Partners'), 'url_name': 'bookkeeping:partner_list'},
        {'name': 'categories', 'label': _('Categories'), 'url_name': 'bookkeeping:category_list'},
        {'name': 'assets', 'label': _('Assets'), 'url_name': 'bookkeeping:asset_list'},
        {'name': 'reports', 'label': _('Reports'), 'url_name': 'bookkeeping:report_list'},
    ]
    from django.urls import reverse

    sort_items = []
    for item in items:
        sort_items.append({'label': item['label'], 'url': reverse(item['url_name']), 'active': item['name'] == active_item})
    ctx = {'sort_items': sort_items, 'cta_end': True}
    if create_url:
        ctx['cta_url'] = create_url
        ctx['cta_label'] = create_label or _('Add')
        ctx['cta_icon'] = 'plus'
    return ctx


class AssetListView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = 'bookkeeping/asset_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_bookkeeping_toolbar('assets', create_url=reverse_lazy('bookkeeping:asset_create'), create_label=_('Add asset')))
        return context


class AssetCreateView(LoginRequiredMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url = reverse_lazy('bookkeeping:asset_list')


class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = Asset
    form_class = AssetForm
    template_name = 'bookkeeping/asset_form.html'
    success_url = reverse_lazy('bookkeeping:asset_list')


class AssetDeleteView(ProtectedDeleteView):
    model = Asset
    template_name = 'bookkeeping/asset_confirm_delete.html'
    success_url = reverse_lazy('bookkeeping:asset_list')
    protect_field = 'asset'
    protect_message = _("Cannot delete asset because it is in use. Remove all transactions that use it first.")


# #########################  Category ###########################


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'bookkeeping/category_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_bookkeeping_toolbar('categories', create_url=reverse_lazy('bookkeeping:category_create'), create_label=_('Add category')))
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = '__all__'
    success_url = reverse_lazy('bookkeeping:category_list')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = '__all__'
    success_url = reverse_lazy('bookkeeping:category_list')


class CategoryDeleteView(ProtectedDeleteView):
    model = Category
    success_url = reverse_lazy('bookkeeping:category_list')
    protect_field = 'category'
    protect_message = _("Cannot delete category because it is in use. Remove all transactions that use it first.")


# #########################  Partner ###########################


class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = 'bookkeeping/partner_list.html'
    context_object_name = 'partners'

    def get_queryset(self):
        sort = self.request.GET.get('sort', 'name')
        order = self.request.GET.get('order', 'asc')
        allowed = ['name', 'city', 'country', 'web_page', 'notes']
        if sort not in allowed:
            sort = 'name'
        prefix = '-' if order == 'desc' else ''
        return Partner.objects.order_by(f'{prefix}{sort}')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_bookkeeping_toolbar('partners', create_url=reverse_lazy('bookkeeping:partner_create'), create_label=_('Add partner')))
        context['current_sort'] = self.request.GET.get('sort', 'name')
        context['current_order'] = self.request.GET.get('order', 'asc')
        return context


class PartnerDetailView(LoginRequiredMixin, DetailView):
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


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    fields = '__all__'
    success_url = reverse_lazy('bookkeeping:partner_list')


class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    model = Partner
    fields = '__all__'
    success_url = reverse_lazy('bookkeeping:partner_list')


class PartnerDeleteView(ProtectedDeleteView):
    model = Partner
    success_url = reverse_lazy('bookkeeping:partner_list')
    protect_field = 'partner'
    protect_message = _("Cannot delete partner because it is in use. Remove all transactions that use it first.")


# #########################  Transaction ###########################


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'bookkeeping/transaction_list.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return Transaction.objects.select_related('partner', 'category', 'asset').order_by('-payment_received_date', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_bookkeeping_toolbar('transactions', create_url=reverse_lazy('bookkeeping:transaction_create'), create_label=_('Add transaction')))
        # Pasek sald per asset z CAŁEJ historii — nad tabelą, jako kontekst dla użytkownika.
        # Sortowanie z asset_balances: default asset pierwszy, reszta wg code alfabetycznie.
        context['balances_by_asset'] = asset_balances()
        return context


def _asset_decimal_places_json():
    return json.dumps({str(a.pk): a.decimal_places for a in Asset.objects.all()})


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
                asset=transaction_data['asset'],
                partner=transaction_data['partner'],
                category=transaction_data['category'],
                amount=transaction_data['amount'],
                payment_received_date=transaction_data['payment_received_date'],
                note=transaction_data['note'],
                author=request.user,
            )
            transaction.created_date = timezone.now()
            transaction.save()

            return redirect('bookkeeping:transaction_list')

        return render(request, self.template_name, {'transaction_form': transaction_form, 'asset_decimal_places_json': _asset_decimal_places_json()})


class TransactionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'bookkeeping/transaction_form.html'

    def test_func(self):
        transaction = self.get_object()
        return self.request.user == transaction.author

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('bookkeeping:transaction_list')

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

    def test_func(self):
        transaction = self.get_object()
        return self.request.user == transaction.author


# #########################  Report ###########################


class ReportView(LoginRequiredMixin, View):
    template_name = 'bookkeeping/report_list.html'

    def get(self, request, year=None):
        try:
            year = int(request.GET.get('year', year)) if year or request.GET.get('year') else timezone.now().year
        except ValueError, TypeError:
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
        context.update(_bookkeeping_toolbar('reports'))

        return render(request, self.template_name, context)

    # Próg powyżej którego pivot kategorie × aktywa staje się nieczytelny (za szeroki).
    # Wtedy template przełącza się na fallback "sekcje per waluta" (Wzorzec 1).
    MAX_ASSETS_FOR_PIVOT = 5
