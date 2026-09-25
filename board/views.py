from urllib.parse import quote_plus, urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, UpdateView

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryItemsAPI, CategoryReorderAPI
from chat.i18n import get_translations as get_chat_translations
from chat.services import get_unread_message_counts_for_rooms
from core.utils import build_detail_navigation
from home.navigation import default_toolbar_views

from .forms import PostForm
from .models import Post, PostAttachment, PostCategory


class PostCategoryAPI(CategoryAPIBase):
    model = PostCategory
    related_count_field = "posts"
    order_field = "priority"

    def _get_queryset(self):
        queryset = super()._get_queryset()
        system_category = PostCategory.get_system_category()
        if system_category:
            queryset = queryset.filter(~Q(name=PostCategory.SYSTEM_NAME) | Q(pk=system_category.pk))
        return queryset

    def serialize(self, cat):
        data = super().serialize(cat)
        if cat.name == PostCategory.SYSTEM_NAME:
            data['item_count'] = Post.objects.filter(system_key__isnull=False).count()
        return data


class PostCategoryEditAPI(CategoryEditAPI):
    model = PostCategory


class PostCategoryDeleteAPI(CategoryDeleteAPI):
    model = PostCategory
    related_count_field = "posts"
    # Deleting a category that documents use is allowed: FK Post.category is SET_NULL,
    # so those documents simply become uncategorized. The UI confirms first (lists titles).
    block_if_in_use = False


class PostCategoryItemsAPI(CategoryItemsAPI):
    model = PostCategory
    related_field = "posts"
    item_label_field = "title"
    limit = 10  # keep the native confirm() dialog short; "…and N more" covers the rest


class PostCategoryReorderAPI(CategoryReorderAPI):
    model = PostCategory
    order_field = "priority"


def _board_list_state(request):
    default_tab = 'public'
    tab = request.GET.get('tab', default_tab)
    if tab == 'internal':
        tab = 'group'
    elif tab == 'trash':
        tab = 'archive'
    if tab not in ('group', 'public', 'important', 'archive') or (not request.user.is_authenticated and tab in ('group', 'archive')):
        tab = default_tab
    sort = request.GET.get('sort', 'title')
    if sort not in ('title', 'date', 'none'):
        sort = 'title'
    order = request.GET.get('order', 'asc') if sort != 'none' else None
    if order not in ('asc', 'desc', None):
        order = 'asc'

    active_categories = []
    for raw_pk in request.GET.getlist('category'):
        try:
            active_categories.append(int(raw_pk))
        except (ValueError, TypeError):
            pass

    return tab, sort, order, active_categories, request.GET.get('q', '').strip()


def _board_return_query(request, listing):
    """Keep only the list state explicitly present when opening a document."""
    query_params = []
    if 'tab' in request.GET:
        query_params.append(('tab', listing['current_tab']))
    if 'sort' in request.GET:
        query_params.append(('sort', listing['sort']))
        if listing['order'] is not None and 'order' in request.GET:
            query_params.append(('order', listing['order']))
    query_params.extend(('category', category) for category in listing['active_categories'])
    if 'q' in request.GET and listing['search_query']:
        query_params.append(('q', listing['search_query']))
    return urlencode(query_params)


def _board_tab_filter(user, tab):
    if tab == 'group':
        return Q(visibility=Post.Visibility.GROUP)
    if tab == 'public':
        return Q(visibility=Post.Visibility.PUBLIC)
    if tab == 'important':
        return Q(is_important=True, visibility__in=(Post.Visibility.GROUP, Post.Visibility.PUBLIC))
    return Q(visibility=Post.Visibility.ARCHIVE)


def _board_visibility_filter_for_user(user, *, include_archive=False):
    visibility_filter = Post.visibility_filter_for_user(user, include_archive=include_archive)
    if not user.is_authenticated:
        visibility_filter &= Q(system_key__isnull=True)
    return visibility_filter


def _board_listing(request, *, include_chat_counts=True):
    tab, sort, order, active_categories, search_query = _board_list_state(request)
    posts_query = Post.objects.select_related('category', 'author', 'updated_by', 'chat_room')
    if tab == 'archive':
        posts_all = posts_query.filter(_board_tab_filter(request.user, tab), _board_visibility_filter_for_user(request.user, include_archive=True))
    else:
        tab_filter = Q(visibility=Post.Visibility.PUBLIC) if tab == 'public' and 'tab' not in request.GET else _board_tab_filter(request.user, tab)
        posts_all = posts_query.filter(_board_visibility_filter_for_user(request.user), tab_filter)
    if search_query:
        posts_all = posts_all.filter(Q(title__icontains=search_query) | Q(subtitle__icontains=search_query) | Q(text__icontains=search_query))
    posts_all = list(posts_all)

    if include_chat_counts:
        unread_counts = get_unread_message_counts_for_rooms(request.user, [post.chat_room_id for post in posts_all])
        for post in posts_all:
            post.chat_room_unread_count = unread_counts.get(post.chat_room_id, 0)
            post.chat_room_pulse_class = 'tw-chat-room-pulse' if post.chat_room_unread_count else ''

    system_category = PostCategory.get_system_category()
    categories_query = PostCategory.objects.all()
    if system_category:
        categories_query = categories_query.filter(~Q(name=PostCategory.SYSTEM_NAME) | Q(pk=system_category.pk))
    categories = list(categories_query)
    posts_by_cat = {}
    uncategorized = []
    for post in posts_all:
        category_id = system_category.pk if system_category and post.system_key else post.category_id
        if category_id:
            posts_by_cat.setdefault(category_id, []).append(post)
        else:
            uncategorized.append(post)

    def sort_posts(posts):
        if sort == 'none':
            return posts
        key = (lambda post: post.updated) if sort == 'date' else (lambda post: (post.title or '').lower())
        return sorted(posts, key=key, reverse=order == 'desc')

    category_groups = []
    for category in categories:
        category_posts = posts_by_cat.get(category.pk, [])
        if category_posts:
            category_groups.append({'category': category, 'posts': sort_posts(category_posts)})
    if uncategorized:
        category_groups.append({'category': None, 'posts': sort_posts(uncategorized)})

    ordered_posts = [post for group in category_groups for post in group['posts']]
    navigation_posts = [post for post in ordered_posts if not active_categories or (system_category.pk if system_category and post.system_key else post.category_id) in active_categories]
    query_params = []
    if tab != 'public' or request.GET.get('tab'):
        query_params.append(('tab', tab))
    query_params.append(('sort', sort))
    if order is not None:
        query_params.append(('order', order))
    query_params.extend(('category', category) for category in active_categories)
    if search_query:
        query_params.append(('q', search_query))

    tab_counts = {}
    for tab_name in ('group', 'public', 'important', 'archive'):
        if tab_name == 'archive' and not request.user.is_authenticated:
            tab_query = Post.objects.none()
        else:
            tab_query = Post.objects.filter(_board_tab_filter(request.user, tab_name))
            tab_query = tab_query.filter(_board_visibility_filter_for_user(request.user, include_archive=tab_name == 'archive'))
        tab_counts[tab_name] = tab_query.count()

    return {
        'category_groups': category_groups,
        'categories': categories,
        'current_tab': tab,
        'board_tab_counts': tab_counts,
        'sort': sort,
        'order': order,
        'active_categories': active_categories,
        'search_query': search_query,
        'ordered_posts': ordered_posts,
        'navigation_posts': navigation_posts,
        'detail_query': urlencode(query_params),
    }


def _board_stepper(request: HttpRequest, listing):
    def tab_url(tab_name):
        return f"{reverse('board:start')}?{urlencode({'tab': tab_name})}"

    return {
        'steps': [
            {'url': tab_url('group'), 'tab': 'group', 'icon': 'users', 'label': gettext_lazy('Group'), 'count': listing['board_tab_counts']['group'], 'active': listing['current_tab'] == 'group'},
            {'url': tab_url('public'), 'tab': 'public', 'icon': 'globe', 'label': gettext_lazy('Public'), 'count': listing['board_tab_counts']['public'], 'active': listing['current_tab'] == 'public'},
            {
                'url': tab_url('important'),
                'tab': 'important',
                'icon': 'star',
                'label': gettext_lazy('Important'),
                'count': listing['board_tab_counts']['important'],
                'active': listing['current_tab'] == 'important',
            },
            {'url': tab_url('archive'), 'tab': 'archive', 'icon': 'archive', 'label': gettext_lazy('Archive'), 'count': listing['board_tab_counts']['archive'], 'active': listing['current_tab'] == 'archive'},
        ],
        'css_class': 'tw-board-stepper',
    }


def board(request: HttpRequest) -> HttpResponse:
    listing = _board_listing(request)
    sort = listing['sort']
    order = listing['order']
    active_categories = listing['active_categories']
    search_query = listing['search_query']
    cat_query = ''.join(f"&category={pk}" for pk in active_categories)
    search_query_param = f"&q={quote_plus(search_query)}" if search_query else ''

    def sort_url(field, state):
        tab_query = f"tab={listing['current_tab']}&"
        query = f"{tab_query}sort={field}&order={state}" if state != 'none' else f"{tab_query}sort=none"
        return reverse('board:start') + f"?{query}{cat_query}{search_query_param}"

    def item_state(field):
        return order if sort == field else 'none'

    def next_state(field):
        state = item_state(field)
        return 'asc' if state == 'none' else 'desc' if state == 'asc' else 'none'

    toolbar_sort_items = [
        {
            'url': sort_url('title', next_state('title')),
            'label': gettext_lazy('A-Z'),
            'pre_icon': 'list',
            'active': sort == 'title',
            'state': item_state('title'),
            'icon': 'up' if item_state('title') == 'asc' else 'down' if item_state('title') == 'desc' else None,
        },
        {
            'url': sort_url('date', next_state('date')),
            'label': gettext_lazy('Date'),
            'pre_icon': 'clock',
            'active': sort == 'date',
            'state': item_state('date'),
            'icon': 'up' if item_state('date') == 'asc' else 'down' if item_state('date') == 'desc' else None,
        },
    ]
    for post in listing['ordered_posts']:
        post.detail_url = reverse('board:view_post', kwargs={'pk': post.pk})
        if listing['detail_query']:
            post.detail_url = f"{post.detail_url}?{listing['detail_query']}"

    listing.update({'current_sort': sort, 'current_order': order, 'toolbar_sort_items': toolbar_sort_items, 'toolbar_views': default_toolbar_views(), 'stepper': _board_stepper(request, listing)})
    return render(request, 'board/board.html', listing)


class PostFormViewMixin(LoginRequiredMixin):
    """Wspólna logika create/update Post: autorzy zmian + ręczny zapis załączników
    (pole `attachments` nie należy do modelu, więc nie obsługuje go form.save())."""

    model = Post
    form_class = PostForm
    template_name = 'board/post_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = _board_listing(self.request, include_chat_counts=False)
        context['stepper'] = _board_stepper(self.request, listing)
        context['detail_query'] = _board_return_query(self.request, listing)
        return context

    def form_valid(self, form):
        post = form.save(commit=False)
        if not post.pk:
            post.author = self.request.user
        post.updated_by = self.request.user
        post.save()

        for attachment in self.request.FILES.getlist('attachments'):
            PostAttachment.objects.create(post=post, file=attachment, filename=attachment.name)

        detail_url = reverse('board:view_post', kwargs={'pk': post.pk})
        listing = _board_listing(self.request, include_chat_counts=False)
        detail_query = _board_return_query(self.request, listing)
        if post.visibility == Post.Visibility.ARCHIVE:
            detail_query = 'tab=archive'
        if detail_query:
            detail_url = f'{detail_url}?{detail_query}'
        return redirect(detail_url)


class PostCreateView(PostFormViewMixin, CreateView):
    def get_initial(self):
        initial = super().get_initial()
        tab = self.request.GET.get('tab')
        visibility_by_tab = {'group': Post.Visibility.GROUP, 'public': Post.Visibility.PUBLIC, 'important': Post.Visibility.GROUP, 'archive': Post.Visibility.ARCHIVE}
        if tab in visibility_by_tab:
            initial['visibility'] = visibility_by_tab[tab]
        if tab in ('public', 'important'):
            initial['is_important'] = True
        try:
            initial['category'] = PostCategory.objects.get(pk=int(self.request.GET.get('category', ''))).pk
        except (ValueError, TypeError, PostCategory.DoesNotExist):
            pass
        return initial


class PostUpdateView(PostFormViewMixin, UpdateView):
    def get_queryset(self):
        return super().get_queryset().filter(Post.editable_filter_for_user(self.request.user))


def _public_post_queryset():
    """Return only regular public posts intended for the external blog."""
    return Post.objects.filter(visibility=Post.Visibility.PUBLIC, system_key__isnull=True).select_related('category', 'author').order_by('-updated', '-pk')


def public_board(request: HttpRequest) -> HttpResponse:
    posts = list(_public_post_queryset())
    for post in posts:
        post.public_detail_url = reverse('board:public_view_post', kwargs={'pk': post.pk})
        if post.slug:
            post.public_detail_url = reverse('board:public_view_post_by_slug', kwargs={'slug': post.slug})
    return render(request, 'board/public_board.html', {'posts': posts})


def public_view_post(request: HttpRequest, pk: int):
    post = get_object_or_404(_public_post_queryset(), pk=pk)
    return render(request, 'board/public_post_detail.html', {'post': post})


def public_view_post_by_slug(request: HttpRequest, slug: str):
    post = get_object_or_404(_public_post_queryset(), slug=slug)
    return render(request, 'board/public_post_detail.html', {'post': post})


def _post_queryset_for_user(user, *, include_archive=False):
    """Return posts visible to the given user."""
    queryset = Post.objects.select_related('author', 'updated_by', 'category')
    return queryset.filter(_board_visibility_filter_for_user(user, include_archive=include_archive))


def _post_detail_context(request: HttpRequest, post: Post):
    """Build common context for document detail views (including embedded chat)."""
    listing = _board_listing(request, include_chat_counts=False)
    context = {
        'post': post,
        'chat_room': post.chat_room,
        'MESSAGE_MAX_LENGTH': settings.MESSAGE_MAX_LENGTH,
        'ec_translations': get_chat_translations(),
        'stepper': _board_stepper(request, listing),
        'detail_query': _board_return_query(request, listing),
    }
    context.update(build_detail_navigation(request, listing['navigation_posts'], post.pk, 'board:view_post'))
    return context


def view_post(request: HttpRequest, pk: int):
    include_archive = request.user.is_authenticated and request.GET.get('tab') == 'archive'
    post = get_object_or_404(_post_queryset_for_user(request.user, include_archive=include_archive).select_related('chat_room'), pk=pk)
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


def view_post_by_slug(request: HttpRequest, slug: str):
    include_archive = request.user.is_authenticated and request.GET.get('tab') == 'archive'
    post = get_object_or_404(_post_queryset_for_user(request.user, include_archive=include_archive).select_related('chat_room'), slug=slug)
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


@login_required
def delete_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post.objects.filter(Post.editable_filter_for_user(request.user)), pk=pk, system_key__isnull=True)
    if request.method == 'POST':
        post.visibility = Post.Visibility.ARCHIVE
        post.updated_by = request.user
        post.save(update_fields=('visibility', 'updated_by', 'updated'))
        return redirect(f"{reverse('board:start')}?tab=archive")
    return redirect('board:view_post', pk=pk)


@login_required
def restore_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post, pk=pk, visibility=Post.Visibility.ARCHIVE, system_key__isnull=True)
    if request.method == 'POST':
        post.visibility = Post.Visibility.GROUP
        post.updated_by = request.user
        post.save(update_fields=('visibility', 'updated_by', 'updated'))
        return redirect(f"{reverse('board:start')}?tab=group")
    return redirect('board:view_post', pk=pk)


@login_required
def delete_featured_image(request: HttpRequest, pk: int):
    post = get_object_or_404(Post.objects.filter(Post.editable_filter_for_user(request.user)), pk=pk)
    if request.method == 'POST' and post.featured_image:
        post.featured_image.delete(save=False)
        post.featured_image = None
        post.save(update_fields=('featured_image', 'updated'))
    return redirect('board:edit_post', pk=pk)


@login_required
def delete_attachment(request: HttpRequest, pk: int, attachment_id: int):
    post = get_object_or_404(Post.objects.filter(Post.editable_filter_for_user(request.user)), pk=pk)
    attachment = get_object_or_404(PostAttachment, pk=attachment_id, post=post)
    if request.method == 'POST':
        attachment.delete()
        return redirect('board:edit_post', pk=pk)
    return redirect('board:edit_post', pk=pk)
