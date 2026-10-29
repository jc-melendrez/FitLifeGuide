from django.utils import timezone
from django.utils.text import slugify
from google.cloud.firestore_v1 import Increment
from google.cloud.firestore_v1.transaction import transactional

from fitlifeguide.domain import (
    Author,
    BlogPost,
    Comment,
    CommentList,
    Forum,
    ForumPost,
    Image,
    Thread,
    Workout,
    author_from_doc,
    parse_date,
    parse_datetime,
)
from fitlifeguide.firestore import count_query, delete_document_tree, delete_query, get_db


def _now():
    return timezone.now()


def _liked_ids(collection_name, doc_ids, uid):
    if not uid or not doc_ids:
        return set()
    db = get_db()
    refs = [
        db.collection(collection_name).document(doc_id).collection('likes').document(uid)
        for doc_id in doc_ids
    ]
    return {
        snap.reference.parent.parent.id
        for snap in db.get_all(refs)
        if snap.exists
    }


def _liked(collection_name, doc_id, uid):
    if not uid:
        return False
    return (
        get_db()
        .collection(collection_name)
        .document(doc_id)
        .collection('likes')
        .document(uid)
        .get()
        .exists
    )


def _unique_slug(collection_name, title):
    base = slugify(title)[:80] or 'item'
    slug = base
    index = 2
    db = get_db()
    while list(db.collection(collection_name).where('slug', '==', slug).limit(1).stream()):
        slug = f'{base}-{index}'
        index += 1
    return slug


def _workout_summary(data):
    if not data.get('workout_title'):
        return None
    return Workout(
        id=data.get('workout_id', ''),
        date=parse_date(data.get('workout_date')),
        week_start=parse_date(data.get('workout_week_start')),
        day_of_week=data.get('workout_day_of_week', ''),
        title=data.get('workout_title', ''),
        duration_minutes=data.get('workout_duration_minutes'),
        goal=data.get('workout_goal', ''),
        status=data.get('workout_status', 'planned'),
    )


def _post_from_doc(doc, liked_ids=None):
    data = doc.to_dict() or {}
    image_url = data.get('image_url')
    return BlogPost(
        id=doc.id,
        title=data.get('title', ''),
        slug=data.get('slug', doc.id),
        author=author_from_doc(data, doc.id),
        content=data.get('content', ''),
        created_at=parse_datetime(data.get('created_at')) or _now(),
        updated_at=parse_datetime(data.get('updated_at')),
        image=Image(image_url) if image_url else None,
        workout=_workout_summary(data),
        published=data.get('published', False),
        like_count=int(data.get('like_count', 0)),
        comment_count=int(data.get('comment_count', 0)),
        liked_by_me=doc.id in (liked_ids or set()),
    )


def list_posts(uid=None, limit=None):
    db = get_db()
    docs = [doc for doc in db.collection('posts').stream() if (doc.to_dict() or {}).get('published')]
    docs.sort(key=lambda doc: (doc.to_dict() or {}).get('created_at') or timezone.now(), reverse=True)
    if limit:
        docs = docs[:limit]
    liked_ids = _liked_ids('posts', [doc.id for doc in docs], uid)
    return [_post_from_doc(doc, liked_ids) for doc in docs]


def list_posts_by_author(uid, limit=None):
    docs = list(get_db().collection('posts').where('author_id', '==', uid).stream())
    docs.sort(key=lambda doc: (doc.to_dict() or {}).get('created_at') or timezone.now(), reverse=True)
    if limit:
        docs = docs[:limit]
    liked_ids = _liked_ids('posts', [doc.id for doc in docs], uid)
    return [_post_from_doc(doc, liked_ids) for doc in docs]


def count_posts_by_author(uid):
    return count_query(get_db().collection('posts').where('author_id', '==', uid))


def _post_doc_by_slug(slug):
    for doc in get_db().collection('posts').where('slug', '==', slug).limit(1).stream():
        return doc
    return None


def _comments_for(post_id, collection_name, uid, comment_cls=Comment):
    db = get_db()
    docs = list(db.collection(collection_name).where('post_id', '==', post_id).stream())
    docs.sort(key=lambda doc: (doc.to_dict() or {}).get('created_at') or timezone.now())
    liked_ids = _liked_ids(collection_name, [doc.id for doc in docs], uid)
    comments = {}
    top_level = CommentList()
    for doc in docs:
        data = doc.to_dict() or {}
        comment = comment_cls(
            id=doc.id,
            post_id=post_id,
            author=author_from_doc(data, doc.id),
            content=data.get('content', ''),
            created_at=parse_datetime(data.get('created_at')) or _now(),
            updated_at=parse_datetime(data.get('updated_at')),
            parent_id=data.get('parent_id'),
            like_count=int(data.get('like_count', 0)),
            liked_by_me=doc.id in liked_ids,
        )
        comments[doc.id] = comment
    for comment in comments.values():
        parent = comments.get(comment.parent_id)
        if parent:
            parent.children.append(comment)
        else:
            top_level.append(comment)
    _set_depth(top_level, 0)
    return top_level


def _set_depth(comments, depth):
    for comment in comments:
        comment.depth = depth
        _set_depth(comment.children, depth + 1)


def get_post(slug, uid=None):
    doc = _post_doc_by_slug(slug)
    if not doc:
        return None
    post = _post_from_doc(doc, _liked_ids('posts', [doc.id], uid))
    post.comments = _comments_for(doc.id, 'blog_comments', uid)
    post.comment_count = len(post.comments)
    return post


def create_post(user, title, content, published=False, image_url='', workout=None):
    db = get_db()
    doc_ref = db.collection('posts').document()
    now = _now()
    data = {
        'title': title,
        'slug': _unique_slug('posts', title),
        'content': content,
        'published': published,
        'image_url': image_url,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': now,
        'updated_at': now,
        'like_count': 0,
        'comment_count': 0,
    }
    if workout:
        data.update({
            'workout_id': workout.id,
            'workout_title': workout.title,
            'workout_date': workout.date.isoformat() if workout.date else None,
            'workout_week_start': workout.week_start.isoformat() if workout.week_start else None,
            'workout_day_of_week': workout.day_of_week,
            'workout_duration_minutes': workout.duration_minutes,
            'workout_goal': workout.goal,
            'workout_status': workout.status,
        })
    doc_ref.set(data)
    return _post_from_doc(doc_ref.get())


def delete_post(slug):
    doc = _post_doc_by_slug(slug)
    if not doc:
        return None
    data = doc.to_dict() or {}
    delete_query(get_db().collection('blog_comments').where('post_id', '==', doc.id))
    delete_document_tree(doc.reference)
    return data


def add_blog_comment(post_id, user, content):
    db = get_db()
    doc_ref = db.collection('blog_comments').document()
    doc_ref.set({
        'post_id': post_id,
        'content': content,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': _now(),
        'like_count': 0,
        'parent_id': None,
    })
    db.collection('posts').document(post_id).update({'comment_count': Increment(1)})
    return doc_ref.get()


def list_forums():
    db = get_db()
    forums = []
    for doc in db.collection('forums').stream():
        data = doc.to_dict() or {}
        forums.append(Forum(
            id=doc.id,
            name=data.get('name', doc.id),
            slug=data.get('slug', doc.id),
            description=data.get('description', ''),
            thread_count=int(data.get('thread_count', 0)),
        ))
    forums.sort(key=lambda forum: forum.name.lower())
    return forums


def get_forum(slug):
    db = get_db()
    for doc in db.collection('forums').where('slug', '==', slug).limit(1).stream():
        data = doc.to_dict() or {}
        return Forum(
            id=doc.id,
            name=data.get('name', slug),
            slug=data.get('slug', slug),
            description=data.get('description', ''),
            thread_count=int(data.get('thread_count', 0)),
        )
    return None


def _thread_from_doc(doc, liked_ids=None):
    data = doc.to_dict() or {}
    forum = Forum(
        id=data.get('forum_id', ''),
        name=data.get('forum_name', ''),
        slug=data.get('forum_slug', ''),
    )
    return Thread(
        id=doc.id,
        forum=forum,
        title=data.get('title', ''),
        slug=data.get('slug', doc.id),
        author=author_from_doc(data, doc.id),
        content=data.get('content', ''),
        created_at=parse_datetime(data.get('created_at')) or _now(),
        like_count=int(data.get('like_count', 0)),
        reply_count=int(data.get('reply_count', 0)),
        liked_by_me=doc.id in (liked_ids or set()),
    )


def list_threads(forum_slug, uid=None):
    docs = list(get_db().collection('threads').where('forum_slug', '==', forum_slug).stream())
    docs.sort(key=lambda doc: (doc.to_dict() or {}).get('created_at') or timezone.now(), reverse=True)
    liked_ids = _liked_ids('threads', [doc.id for doc in docs], uid)
    return [_thread_from_doc(doc, liked_ids) for doc in docs]


def get_hot_thread(uid=None):
    docs = list(get_db().collection('threads').stream())
    docs.sort(
        key=lambda doc: (
            (doc.to_dict() or {}).get('reply_count', 0),
            (doc.to_dict() or {}).get('created_at') or timezone.now(),
        ),
        reverse=True,
    )
    if not docs:
        return None
    doc = docs[0]
    return _thread_from_doc(doc, _liked_ids('threads', [doc.id], uid))


def _thread_doc_by_slug(slug):
    for doc in get_db().collection('threads').where('slug', '==', slug).limit(1).stream():
        return doc
    return None


def get_thread(slug, uid=None):
    doc = _thread_doc_by_slug(slug)
    if not doc:
        return None, []
    thread = _thread_from_doc(doc, _liked_ids('threads', [doc.id], uid))
    post_docs = list(get_db().collection('forum_posts').where('thread_id', '==', thread.id).stream())
    post_docs.sort(key=lambda post: (post.to_dict() or {}).get('created_at') or timezone.now())
    liked_ids = _liked_ids('forum_posts', [post.id for post in post_docs], uid)
    posts = []
    for post_doc in post_docs:
        data = post_doc.to_dict() or {}
        post = ForumPost(
            id=post_doc.id,
            thread_id=thread.id,
            author=author_from_doc(data, post_doc.id),
            content=data.get('content', ''),
            created_at=parse_datetime(data.get('created_at')) or _now(),
            updated_at=parse_datetime(data.get('updated_at')),
            like_count=int(data.get('like_count', 0)),
            comment_count=int(data.get('comment_count', 0)),
            liked_by_me=post_doc.id in liked_ids,
        )
        post.comments = _comments_for(post.id, 'forum_comments', uid)
        post.comment_count = len(post.comments)
        posts.append(post)
    thread.reply_count = len(posts)
    return thread, posts


def create_thread(user, forum, title, content):
    db = get_db()
    thread_ref = db.collection('threads').document()
    post_ref = db.collection('forum_posts').document()
    slug = _unique_slug('threads', title)
    now = _now()
    batch = db.batch()
    batch.set(thread_ref, {
        'title': title,
        'slug': slug,
        'content': content,
        'forum_id': forum.id,
        'forum_slug': forum.slug,
        'forum_name': forum.name,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': now,
        'like_count': 0,
        'reply_count': 1,
    })
    batch.set(post_ref, {
        'thread_id': thread_ref.id,
        'thread_slug': slug,
        'content': content,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': now,
        'like_count': 0,
        'comment_count': 0,
    })
    batch.update(db.collection('forums').document(forum.id), {'thread_count': Increment(1)})
    batch.commit()
    return _thread_from_doc(thread_ref.get())


def create_forum_post(thread, user, content):
    db = get_db()
    doc_ref = db.collection('forum_posts').document()
    doc_ref.set({
        'thread_id': thread.id,
        'thread_slug': thread.slug,
        'content': content,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': _now(),
        'like_count': 0,
        'comment_count': 0,
    })
    db.collection('threads').document(thread.id).update({'reply_count': Increment(1)})
    return doc_ref.get()


def delete_thread(slug):
    doc = _thread_doc_by_slug(slug)
    if not doc:
        return None
    data = doc.to_dict() or {}
    db = get_db()
    delete_query(db.collection('forum_comments').where('thread_id', '==', doc.id))
    delete_query(db.collection('forum_posts').where('thread_id', '==', doc.id))
    delete_document_tree(doc.reference)
    if data.get('forum_id'):
        db.collection('forums').document(data['forum_id']).update({'thread_count': Increment(-1)})
    return data


def get_forum_post(post_id):
    snap = get_db().collection('forum_posts').document(post_id).get()
    if not snap.exists:
        return None, {}
    data = snap.to_dict() or {}
    post = ForumPost(
        id=snap.id,
        thread_id=data.get('thread_id', ''),
        author=author_from_doc(data, snap.id),
        content=data.get('content', ''),
        created_at=parse_datetime(data.get('created_at')) or _now(),
        updated_at=parse_datetime(data.get('updated_at')),
        like_count=int(data.get('like_count', 0)),
        comment_count=int(data.get('comment_count', 0)),
    )
    return post, data


def get_comment(comment_id):
    snap = get_db().collection('forum_comments').document(comment_id).get()
    if not snap.exists:
        return None, {}
    data = snap.to_dict() or {}
    comment = Comment(
        id=snap.id,
        post_id=data.get('post_id', ''),
        author=author_from_doc(data, snap.id),
        content=data.get('content', ''),
        created_at=parse_datetime(data.get('created_at')) or _now(),
        updated_at=parse_datetime(data.get('updated_at')),
        parent_id=data.get('parent_id'),
        like_count=int(data.get('like_count', 0)),
    )
    return comment, data


def delete_forum_post(post_id):
    db = get_db()
    doc_ref = db.collection('forum_posts').document(post_id)
    snap = doc_ref.get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    delete_query(db.collection('forum_comments').where('post_id', '==', post_id))
    delete_document_tree(doc_ref)
    if data.get('thread_id'):
        db.collection('threads').document(data['thread_id']).update({'reply_count': Increment(-1)})
    return data


def add_comment(post_id, user, content, parent_id=None):
    db = get_db()
    post_ref = db.collection('forum_posts').document(post_id)
    post_snap = post_ref.get()
    if not post_snap.exists:
        return None
    post_data = post_snap.to_dict() or {}
    if parent_id:
        parent = db.collection('forum_comments').document(parent_id).get()
        if not parent.exists or (parent.to_dict() or {}).get('post_id') != post_id:
            parent_id = None
    doc_ref = db.collection('forum_comments').document()
    doc_ref.set({
        'post_id': post_id,
        'thread_id': post_data.get('thread_id'),
        'thread_slug': post_data.get('thread_slug'),
        'parent_id': parent_id,
        'content': content,
        'author_id': user.id,
        'author_username': user.username,
        'author_avatar_url': user.profile.avatar_url,
        'created_at': _now(),
        'like_count': 0,
    })
    post_ref.update({'comment_count': Increment(1)})
    return doc_ref.get()


def _delete_comment_tree(comment_id):
    db = get_db()
    children = list(db.collection('forum_comments').where('parent_id', '==', comment_id).stream())
    for child in children:
        _delete_comment_tree(child.id)
    delete_document_tree(db.collection('forum_comments').document(comment_id))


def delete_comment(comment_id):
    db = get_db()
    snap = db.collection('forum_comments').document(comment_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    post_id = data.get('post_id')
    _delete_comment_tree(comment_id)
    if post_id:
        remaining = count_query(db.collection('forum_comments').where('post_id', '==', post_id))
        db.collection('forum_posts').document(post_id).update({'comment_count': remaining})
    return data


def toggle_like(collection_name, doc_id, uid):
    db = get_db()
    doc_ref = db.collection(collection_name).document(doc_id)
    like_ref = doc_ref.collection('likes').document(uid)
    result = {'liked': False}

    @transactional
    def toggle(transaction):
        like_snap = like_ref.get(transaction=transaction)
        if like_snap.exists:
            transaction.delete(like_ref)
            transaction.update(doc_ref, {'like_count': Increment(-1)})
            result['liked'] = False
        else:
            transaction.set(like_ref, {'created_at': _now()})
            transaction.update(doc_ref, {'like_count': Increment(1)})
            result['liked'] = True

    toggle(db.transaction())
    data = doc_ref.get().to_dict() or {}
    return result['liked'], max(0, int(data.get('like_count', 0)))


def refresh_author(uid, username, avatar_url):
    db = get_db()
    for collection_name in ('posts', 'threads', 'forum_posts', 'blog_comments', 'forum_comments'):
        docs = list(db.collection(collection_name).where('author_id', '==', uid).stream())
        for index in range(0, len(docs), 400):
            batch = db.batch()
            for doc in docs[index:index + 400]:
                batch.update(doc.reference, {
                    'author_username': username,
                    'author_avatar_url': avatar_url,
                })
            batch.commit()
