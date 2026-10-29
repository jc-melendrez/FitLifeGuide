from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from .models import BlogPost, Forum, Thread, ForumPost, BlogComment, ForumComment
from .forms import BlogPostForm, ThreadForm, BlogCommentForm, ForumCommentForm


def posts_view(request):
    posts = (
        BlogPost.objects.filter(published=True)
        .select_related('author', 'author__profile', 'workout')
        .prefetch_related('likes', 'comments')
    )
    hot_thread = (
        Thread.objects.select_related('forum', 'author')
        .annotate(reply_count=Count('posts'))
        .order_by('-reply_count', '-created_at')
        .first()
    )
    return render(request, 'community/posts.html', {
        'posts': posts,
        'hot_thread': hot_thread,
        'forums': Forum.objects.annotate(thread_count=Count('threads')),
    })


def post_detail_view(request, slug):
    post = get_object_or_404(
        BlogPost.objects.select_related('author', 'author__profile', 'workout'),
        slug=slug,
        published=True,
    )
    comments = post.comments.select_related('author').all()
    
    if request.method == 'POST' and request.user.is_authenticated:
        form = BlogCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('post_detail', slug=slug)
    else:
        form = BlogCommentForm()
    
    return render(request, 'community/post_detail.html', {
        'post': post,
        'comments': comments,
        'form': form,
        'user_has_liked': post.likes.filter(id=request.user.id).exists() if request.user.is_authenticated else False
    })


@login_required
def create_post_view(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Post created successfully!')
            return redirect('posts')
    else:
        form = BlogPostForm(user=request.user)
    return render(request, 'community/create_post.html', {'form': form})


@login_required
def delete_post(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    if request.user != post.author:
        return HttpResponseForbidden("You don't have permission to delete this post.")
    
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Post deleted successfully!')
        return redirect('posts')
    
    return render(request, 'community/delete_confirm.html', {
        'object': post,
        'cancel_url': reverse('posts'),
    })


@login_required
def like_post(request, slug):
    if request.method == 'POST':
        post = get_object_or_404(BlogPost, slug=slug)
        if post.likes.filter(id=request.user.id).exists():
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'total_likes': post.total_likes()
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)


def forum_list(request):
    forums = Forum.objects.all()
    return render(request, 'community/forum_list.html', {'forums': forums})


def forum_threads(request, slug):
    forum = get_object_or_404(Forum, slug=slug)
    threads = forum.threads.select_related('author', 'author__profile').prefetch_related('likes').order_by('-created_at')
    return render(request, 'community/forum_threads.html', {'forum': forum, 'threads': threads})


@login_required
def thread_create(request, slug):
    forum = get_object_or_404(Forum, slug=slug)
    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.forum = forum
            thread.author = request.user
            thread.save()
            
            # Create the initial post with the thread content
            ForumPost.objects.create(
                thread=thread,
                author=request.user,
                content=form.cleaned_data['content']
            )
            
            messages.success(request, 'Thread created successfully!')
            return redirect('thread_detail', slug=thread.slug)
    else:
        form = ThreadForm()
    return render(request, 'community/thread_create.html', {'form': form, 'forum': forum})


def thread_detail(request, slug):
    thread = get_object_or_404(
        Thread.objects.select_related('author', 'author__profile', 'forum'),
        slug=slug,
    )
    posts = thread.posts.select_related('author', 'author__profile').prefetch_related(
        'comments', 
        'comments__author', 
        'comments__author__profile',
        'likes'
    ).all()
    
    if request.method == 'POST' and request.user.is_authenticated:
        content = request.POST.get('content')
        if content:
            post = ForumPost.objects.create(
                thread=thread,
                author=request.user,
                content=content
            )
            messages.success(request, 'Reply added successfully!')
            return redirect('thread_detail', slug=slug)
    
    return render(request, 'community/thread_detail.html', {
        'thread': thread,
        'posts': posts,
        'form': ForumCommentForm(),
        'user_has_liked': thread.likes.filter(id=request.user.id).exists() if request.user.is_authenticated else False
    })


@login_required
def delete_thread(request, slug):
    thread = get_object_or_404(Thread, slug=slug)
    if request.user != thread.author:
        return HttpResponseForbidden("You don't have permission to delete this thread.")
    
    if request.method == 'POST':
        forum_slug = thread.forum.slug
        thread.delete()
        messages.success(request, 'Thread deleted successfully!')
        return redirect('forum_threads', slug=forum_slug)
    
    return render(request, 'community/delete_confirm.html', {
        'object': thread,
        'cancel_url': reverse('forum_threads', args=[thread.forum.slug]),
    })


@login_required
def like_thread(request, slug):
    if request.method == 'POST':
        thread = get_object_or_404(Thread, slug=slug)
        if thread.likes.filter(id=request.user.id).exists():
            thread.likes.remove(request.user)
            liked = False
        else:
            thread.likes.add(request.user)
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'total_likes': thread.total_likes()
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def delete_forum_post(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)
    if request.user != post.author:
        return HttpResponseForbidden("You don't have permission to delete this post.")
    
    if request.method == 'POST':
        thread_slug = post.thread.slug
        post.delete()
        messages.success(request, 'Post deleted successfully!')
        return redirect('thread_detail', slug=thread_slug)
    
    return render(request, 'community/delete_confirm.html', {
        'object': post,
        'cancel_url': reverse('thread_detail', args=[post.thread.slug]),
    })


@login_required
def like_forum_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(ForumPost, id=post_id)
        if post.likes.filter(id=request.user.id).exists():
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'total_likes': post.total_likes()
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)
    
    if request.method == 'POST':
        form = ForumCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.parent = form.cleaned_data.get('parent')
            comment.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'comment_id': comment.id,
                    'author': comment.author.username,
                    'content': comment.content,
                    'created_at': comment.created_at.strftime("%b %d, %Y, %I:%M %p"),
                    'likes_count': 0,
                    'can_delete': True
                })
            
            return redirect('thread_detail', slug=post.thread.slug)
    
    return redirect('thread_detail', slug=post.thread.slug)


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(ForumComment, id=comment_id)
    if request.user != comment.author:
        return HttpResponseForbidden("You don't have permission to delete this comment.")
    
    if request.method == 'POST':
        thread_slug = comment.post.thread.slug
        comment.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('thread_detail', slug=thread_slug)
    
    return render(request, 'community/delete_confirm.html', {
        'object': comment,
        'cancel_url': reverse('thread_detail', args=[comment.post.thread.slug]),
    })


@login_required
def like_comment(request, comment_id):
    if request.method == 'POST':
        comment = get_object_or_404(ForumComment, id=comment_id)
        if comment.likes.filter(id=request.user.id).exists():
            comment.likes.remove(request.user)
            liked = False
        else:
            comment.likes.add(request.user)
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'total_likes': comment.total_likes()
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)
