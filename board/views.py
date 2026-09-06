from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, UpdateView

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryItemsAPI, CategoryReorderAPI
from chat.i18n import get_translations as get_chat_translations
from chat.models import Message

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


def board(request: HttpRequest) -> HttpResponse:
    sort = request.GET.get('sort', 'date')
    order = request.GET.get('order', 'desc')
    reverse_order = order == 'desc'

    raw_pks = request.GET.getlist('category')
    active_categories = []
    for pk in raw_pks:
        try:
            active_categories.append(int(pk))
        except (ValueError, TypeError):
            pass

    posts_query = Post.objects.select_related('category', 'author', 'chat_room').prefetch_related(Prefetch('chat_room__messages', queryset=Message.objects.only('id', 'room')), 'chat_room__seen_by')
    if request.user.is_authenticated:
        posts_all = posts_query.all()
    else:
        posts_all = posts_query.filter(is_public=True)

    categories = list(PostCategory.objects.all())
    posts_by_cat = {}
    uncategorized = []
    for post in posts_all:
        room = post.chat_room
        if room:
            post.chat_room_message_count = room.messages.count()
            is_unseen = request.user.is_authenticated and post.chat_room_message_count and request.user not in room.seen_by.all()
            post.chat_room_pulse_class = 'chat-room-pulse' if is_unseen else ''
        else:
            post.chat_room_message_count = 0
            post.chat_room_pulse_class = ''

        if post.category_id:
            posts_by_cat.setdefault(post.category_id, []).append(post)
        else:
            uncategorized.append(post)

    category_groups = []
    for cat in categories:
        cat_posts = posts_by_cat.get(cat.pk, [])
        if cat_posts:
            sorted_posts = sorted(cat_posts, key=lambda p: p.updated, reverse=reverse_order)
            category_groups.append({'category': cat, 'posts': sorted_posts})
    if uncategorized:
        sorted_uncategorized = sorted(uncategorized, key=lambda p: p.updated, reverse=reverse_order)
        category_groups.append({'category': None, 'posts': sorted_uncategorized})

    next_order = "asc" if order == "desc" else "desc"
    cat_query = "".join(f"&category={pk}" for pk in active_categories)
    sort_url = reverse("board:start") + f"?sort=date&order={next_order}{cat_query}"

    toolbar_sort_items = [{"url": sort_url, "label": gettext_lazy("Date"), "active": True, "icon": "up" if next_order == "desc" else "down"}]
    toolbar_views = [{"name": "list", "icon": "list", "title": gettext_lazy("List")}, {"name": "grid", "icon": "grip", "title": gettext_lazy("Grid")}]

    return render(
        request,
        'board/board.html',
        {
            'category_groups': category_groups,
            'categories': categories,
            'current_sort': sort,
            'current_order': order,
            'active_categories': active_categories,
            'toolbar_sort_items': toolbar_sort_items,
            'toolbar_views': toolbar_views,
        },
    )


class PostFormViewMixin(LoginRequiredMixin):
    """Wspólna logika create/update Post: autor + ręczny zapis załączników
    (pole `attachments` nie należy do modelu, więc nie obsługuje go form.save())."""

    model = Post
    form_class = PostForm
    template_name = 'board/post_form.html'

    def form_valid(self, form):
        post = form.save(commit=False)
        post.author = self.request.user
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


def _post_detail_context(request: HttpRequest, post: Post):
    """Build common context for document detail views (including embedded chat)."""
    return {'post': post, 'chat_room': post.chat_room, 'MESSAGE_MAX_LENGTH': settings.MESSAGE_MAX_LENGTH, 'ec_translations': get_chat_translations()}


def view_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post.objects.select_related('chat_room'), pk=pk)  # Only published documents can be viewed
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


def view_post_by_slug(request: HttpRequest, slug: str):
    post = get_object_or_404(Post.objects.select_related('chat_room'), slug=slug)
    return render(request, 'board/post_detail.html', _post_detail_context(request, post))


@login_required
def delete_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post, pk=pk)
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
