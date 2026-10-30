from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from fitlifeguide.storage import upload_image
from tools.repositories import get_workout

from .forms import BlogCommentForm, BlogPostForm, ForumCommentForm, ThreadForm
from .repositories import (
    add_blog_comment,
    add_comment,
    count_posts_by_author,
    create_forum_post,
    create_post,
    create_thread,
    delete_comment,
    delete_forum_post,
    delete_post,
    delete_thread,
    get_comment,
    get_forum,
    get_forum_post,
    get_hot_thread,
    get_post,
    get_thread,
    list_forums,
    list_posts,
    list_threads,
    toggle_like,
)


def posts_view(request):
    uid = request.user.id if request.user.is_authenticated else None
    return render(request, 'community/posts.html', {
        'posts': list_posts(uid),
        'hot_thread': get_hot_thread(uid),
        'forums': list_forums(),
    })


def post_detail_view(request, slug):
    uid = request.user.id if request.user.is_authenticated else None
    post = get_post(slug, uid)
    if not post:
        raise Http404('Post not found')

    if request.method == 'POST' and request.user.is_authenticated:
        form = BlogCommentForm(request.POST)
        if form.is_valid():
            add_blog_comment(post.id, request.user, form.cleaned_data['content'])
            messages.success(request, 'Comment added successfully!')
            return redirect('post_detail', slug=slug)
    else:
        form = BlogCommentForm()

    return render(request, 'community/post_detail.html', {
        'post': post,
        'comments': post.comments,
        'form': form,
        'user_has_liked': post.liked_by_me,
    })


@login_required
def create_post_view(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            workout_id = form.cleaned_data.get('workout')
            workout = get_workout(workout_id, request.user.id) if workout_id else None
            if workout_id and not workout:
                form.add_error('workout', 'Select one of your own workouts.')
            else:
                try:
                    image_url = upload_image(form.cleaned_data.get('image'), 'posts')
                except ValueError as exc:
                    form.add_error('image', str(exc))
                else:
                    create_post(
                        request.user,
                        form.cleaned_data['title'],
                        form.cleaned_data['content'],
                        published=form.cleaned_data.get('published', False),
                        image_url=image_url,
                        workout=workout,
                    )
                    messages.success(request, 'Post created successfully!')
                    return redirect('posts')
    else:
        form = BlogPostForm(user=request.user, initial={'workout': request.GET.get('workout', '')})
    return render(request, 'community/create_post.html', {'form': form})


@login_required
def delete_post_view(request, slug):
    post = get_post(slug)
    if not post:
        raise Http404('Post not found')
    if request.user.id != post.author.id:
        return HttpResponseForbidden("You don't have permission to delete this post.")

    if request.method == 'POST':
        delete_post(slug)
        messages.success(request, 'Post deleted successfully!')
        return redirect('posts')

    return render(request, 'community/delete_confirm.html', {
        'object': post,
        'cancel_url': reverse('posts'),
    })


@login_required
def like_post_view(request, slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    post = get_post(slug)
    if not post:
        raise Http404('Post not found')
    liked, total = toggle_like('posts', post.id, request.user.id)
    return JsonResponse({'liked': liked, 'total_likes': total})


def forum_list_view(request):
    return render(request, 'community/forum_list.html', {'forums': list_forums()})


def forum_threads_view(request, slug):
    forum = get_forum(slug)
    if not forum:
        raise Http404('Forum not found')
    uid = request.user.id if request.user.is_authenticated else None
    return render(request, 'community/forum_threads.html', {
        'forum': forum,
        'threads': list_threads(slug, uid),
    })


@login_required
def thread_create_view(request, slug):
    forum = get_forum(slug)
    if not forum:
        raise Http404('Forum not found')
    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = create_thread(
                request.user,
                forum,
                form.cleaned_data['title'],
                form.cleaned_data['content'],
            )
            messages.success(request, 'Thread created successfully!')
            return redirect('thread_detail', slug=thread.slug)
    else:
        form = ThreadForm()
    return render(request, 'community/thread_create.html', {'form': form, 'forum': forum})


def thread_detail_view(request, slug):
    uid = request.user.id if request.user.is_authenticated else None
    thread, posts = get_thread(slug, uid)
    if not thread:
        raise Http404('Thread not found')

    if request.method == 'POST' and request.user.is_authenticated:
        content = request.POST.get('content', '').strip()
        if content:
            create_forum_post(thread, request.user, content)
            messages.success(request, 'Reply added successfully!')
            return redirect('thread_detail', slug=slug)

    return render(request, 'community/thread_detail.html', {
        'thread': thread,
        'posts': posts,
        'form': ForumCommentForm(),
        'user_has_liked': thread.liked_by_me,
    })


@login_required
def delete_thread_view(request, slug):
    thread, _ = get_thread(slug)
    if not thread:
        raise Http404('Thread not found')
    if request.user.id != thread.author.id:
        return HttpResponseForbidden("You don't have permission to delete this thread.")

    if request.method == 'POST':
        forum_slug = thread.forum.slug
        delete_thread(slug)
        messages.success(request, 'Thread deleted successfully!')
        return redirect('forum_threads', slug=forum_slug)

    return render(request, 'community/delete_confirm.html', {
        'object': thread,
        'cancel_url': reverse('forum_threads', args=[thread.forum.slug]),
    })


@login_required
def like_thread_view(request, slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    thread, _ = get_thread(slug)
    if not thread:
        raise Http404('Thread not found')
    liked, total = toggle_like('threads', thread.id, request.user.id)
    return JsonResponse({'liked': liked, 'total_likes': total})


@login_required
def delete_forum_post_view(request, post_id):
    post, data = get_forum_post(post_id)
    if not post:
        raise Http404('Post not found')
    if request.user.id != post.author.id:
        return HttpResponseForbidden("You don't have permission to delete this post.")

    if request.method == 'POST':
        delete_forum_post(post_id)
        messages.success(request, 'Post deleted successfully!')
        return redirect('thread_detail', slug=data.get('thread_slug'))

    return render(request, 'community/delete_confirm.html', {
        'object': post,
        'cancel_url': reverse('thread_detail', args=[data.get('thread_slug')]),
    })


@login_required
def like_forum_post_view(request, post_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    post, _ = get_forum_post(post_id)
    if not post:
        raise Http404('Post not found')
    liked, total = toggle_like('forum_posts', post.id, request.user.id)
    return JsonResponse({'liked': liked, 'total_likes': total})


@login_required
def add_comment_view(request, post_id):
    post, data = get_forum_post(post_id)
    if not post:
        raise Http404('Post not found')

    if request.method == 'POST':
        form = ForumCommentForm(request.POST)
        if form.is_valid():
            comment = add_comment(
                post.id,
                request.user,
                form.cleaned_data['content'],
                form.cleaned_data.get('parent') or None,
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                comment_data = comment.to_dict() or {}
                return JsonResponse({
                    'status': 'success',
                    'comment_id': comment.id,
                    'author': comment_data.get('author_username', ''),
                    'content': comment_data.get('content', ''),
                    'created_at': comment_data.get('created_at').strftime('%b %d, %Y, %I:%M %p'),
                    'likes_count': 0,
                    'can_delete': True,
                })
            return redirect('thread_detail', slug=data.get('thread_slug'))

    return redirect('thread_detail', slug=data.get('thread_slug'))


@login_required
def delete_comment_view(request, comment_id):
    comment, data = get_comment(comment_id)
    if not comment:
        raise Http404('Comment not found')
    if request.user.id != comment.author.id:
        return HttpResponseForbidden("You don't have permission to delete this comment.")

    if request.method == 'POST':
        delete_comment(comment_id)
        messages.success(request, 'Comment deleted successfully!')
        return redirect('thread_detail', slug=data.get('thread_slug'))

    return render(request, 'community/delete_confirm.html', {
        'object': comment,
        'cancel_url': reverse('thread_detail', args=[data.get('thread_slug')]),
    })


@login_required
def like_comment_view(request, comment_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    comment, _ = get_comment(comment_id)
    if not comment:
        raise Http404('Comment not found')
    liked, total = toggle_like('forum_comments', comment.id, request.user.id)
    return JsonResponse({'liked': liked, 'total_likes': total})
