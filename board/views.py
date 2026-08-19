from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryItemsAPI, CategoryReorderAPI

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

    if request.user.is_authenticated:
        posts_all = Post.objects.all().select_related('category', 'author')
    else:
        posts_all = Post.objects.filter(is_public=True).select_related('category', 'author')

    categories = list(PostCategory.objects.all())
    posts_by_cat = {}
    uncategorized = []
    for post in posts_all:
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


@login_required
def create_post(request: HttpRequest):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()

            attachments = request.FILES.getlist('attachments')
            for attachment in attachments:
                PostAttachment.objects.create(post=post, file=attachment, filename=attachment.name)

            return redirect('board:view_post', post.pk)
    else:
        form = PostForm()
    return render(request, 'board/create_post.html', {'form': form})


@login_required
def edit_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post, pk=pk)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()

            attachments = request.FILES.getlist('attachments')
            for attachment in attachments:
                PostAttachment.objects.create(post=post, file=attachment, filename=attachment.name)

            return redirect('board:view_post', pk)
    else:
        form = PostForm(instance=post)
    return render(request, 'board/edit_post.html', {'form': form, 'post': post})


def view_post(request: HttpRequest, pk: int):
    post = get_object_or_404(Post, pk=pk)  # Only published documents can be viewed
    return render(request, 'board/post_detail.html', {'post': post})


def view_post_by_slug(request: HttpRequest, slug: str):
    post = get_object_or_404(Post, slug=slug)
    return render(request, 'board/post_detail.html', {'post': post})


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
