from urllib.parse import quote_plus, urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
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

from .forms import PostForm
from .models import Post, PostAttachment, PostCategory


class PostCategoryAPI(CategoryAPIBase):
    model = PostCategory
    related_count_field = "posts"
    order_field = "priority"


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

    return sort, order, active_categories, request.GET.get('q', '').strip()


def _board_listing(request, *, include_chat_counts=True):
    sort, order, active_categories, search_query = _board_list_state(request)
    posts_query = Post.objects.select_related('category', 'author', 'updated_by', 'chat_room')
    posts_all = posts_query.filter(Post.visibility_filter_for_user(request.user))
    if search_query:
        posts_all = posts_all.filter(Q(title__icontains=search_query) | Q(subtitle__icontains=search_query) | Q(text__icontains=search_query))
    posts_all = list(posts_all)

    if include_chat_counts:
        unread_counts = get_unread_message_counts_for_rooms(request.user, [post.chat_room_id for post in posts_all])
        for post in posts_all:
            post.chat_room_unread_count = unread_counts.get(post.chat_room_id, 0)
            post.chat_room_pulse_class = 'tw-chat-room-pulse' if post.chat_room_unread_count else ''

    categories = list(PostCategory.objects.all())
    posts_by_cat = {}
    uncategorized = []
    for post in posts_all:
        if post.category_id:
            posts_by_cat.setdefault(post.category_id, []).append(post)
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
    navigation_posts = [post for post in ordered_posts if not active_categories or post.category_id in active_categories]
    query_params = [('sort', sort)]
    if order is not None:
        query_params.append(('order', order))
    query_params.extend(('category', category) for category in active_categories)
    if search_query:
        query_params.append(('q', search_query))

    return {
        'category_groups': category_groups,
        'categories': categories,
        'sort': sort,
        'order': order,
        'active_categories': active_categories,
        'search_query': search_query,
        'ordered_posts': ordered_posts,
        'navigation_posts': navigation_posts,
        'detail_query': urlencode(query_params),
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
        query = f"sort={field}&order={state}" if state != 'none' else 'sort=none'
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
            'active': sort == 'title',
            'state': item_state('title'),
            'icon': 'up' if item_state('title') == 'asc' else 'down' if item_state('title') == 'desc' else None,
        },
        {
            'url': sort_url('date', next_state('date')),
            'label': gettext_lazy('Date'),
            'active': sort == 'date',
            'state': item_state('date'),
            'icon': 'up' if item_state('date') == 'asc' else 'down' if item_state('date') == 'desc' else None,
        },
    ]
    for post in listing['ordered_posts']:
        post.detail_url = reverse('board:view_post', kwargs={'pk': post.pk})
        if listing['detail_query']:
            post.detail_url = f"{post.detail_url}?{listing['detail_query']}"

    listing.update(
        {
            'current_sort': sort,
            'current_order': order,
            'toolbar_sort_items': toolbar_sort_items,
            'toolbar_views': [{'name': 'list', 'icon': 'list', 'title': gettext_lazy('List')}, {'name': 'grid', 'icon': 'grip', 'title': gettext_lazy('Grid')}],
        }
    )
    return render(request, 'board/board.html', listing)


class PostFormViewMixin(LoginRequiredMixin):
    """Wspólna logika create/update Post: autorzy zmian + ręczny zapis załączników
    (pole `attachments` nie należy do modelu, więc nie obsługuje go form.save())."""

    model = Post
    form_class = PostForm
    template_name = 'board/post_form.html'

    def form_valid(self, form):
        post = form.save(commit=False)
        if not post.pk:
            post.author = self.request.user
        post.updated_by = self.request.user
        post.save()

        for attachment in self.request.FILES.getlist('attachments'):
            PostAttachment.objects.create(post=post, file=attachment, filename=attachment.name)

        return redirect('board:view_post', post.pk)


class PostCreateView(PostFormViewMixin, CreateView):
    def get_initial(self):
        initial = super().get_initial()
        try:
            initial['category'] = PostCategory.objects.get(pk=int(self.request.GET.get('category', ''))).pk
        except (ValueError, TypeError, PostCategory.DoesNotExist):
            pass
        return initial


class PostUpdateView(PostFormViewMixin, UpdateView):
    pass


def _post_queryset_for_user(user):
    """Return posts visible to the given user."""
    return Post.objects.select_related('author', 'updated_by', 'category').filter(Post.visibility_filter_for_user(user))


def _post_detail_context(request: HttpRequest, post: Post):
    """Build common context for document detail views (including embedded chat)."""
    listing = _board_listing(request, include_chat_counts=False)
    context = {'post': post, 'chat_room': post.chat_room, 'MESSAGE_MAX_LENGTH': settings.MESSAGE_MAX_LENGTH, 'ec_translations': get_chat_translations(), 'list_url': reverse('board:start')}
    if listing['detail_query']:
        context['list_url'] = f"{context['list_url']}?{listing['detail_query']}"
    context.update(build_detail_navigation(request, listing['navigation_posts'], post.pk, 'board:view_post'))
    return context


def view_post(request: HttpRequest, pk: int):
    post = get_object_or_404(_post_queryset_for_user(request.user).select_related('chat_room'), pk=pk)
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


def view_post_by_slug(request: HttpRequest, slug: str):
    post = get_object_or_404(_post_queryset_for_user(request.user).select_related('chat_room'), slug=slug)
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


@login_required
def delete_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    if request.method == 'POST':
        try:
            post.delete()
            return redirect('board:start')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('board:view_post', pk=pk)
    return render(request, 'board/post_confirm_delete.html', {'post': post})


@login_required
def delete_attachment(request: HttpRequest, pk: int, attachment_id: int):
    post = get_object_or_404(Post, pk=pk)
    attachment = get_object_or_404(PostAttachment, pk=attachment_id, post=post)
    if request.method == 'POST':
        attachment.delete()
        return redirect('board:edit_post', pk=pk)
    return render(request, 'board/attachment_confirm_delete.html', {'attachment': attachment, 'post': post})
