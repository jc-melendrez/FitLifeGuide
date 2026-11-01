import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from google.cloud.firestore_v1.transaction import transactional

from fitlifeguide.domain import (
    Author,
    Profile,
    User,
    parse_date,
    parse_datetime,
    to_iso_date,
)
from fitlifeguide.firestore import count_query, get_db


def _profile_from_doc(uid, data):
    return Profile(
        user_id=uid,
        location=data.get('location', ''),
        bio=data.get('bio', ''),
        birth_date=parse_date(data.get('birth_date')),
        avatar_url=data.get('avatar_url', ''),
        cover_url=data.get('cover_url', ''),
        status=data.get('status', 'rest'),
        status_updated_at=parse_datetime(data.get('status_updated_at')),
        goal=data.get('goal', ''),
        days_per_week=data.get('days_per_week'),
    )


def get_user(uid):
    if not uid:
        return None
    db = get_db()
    user_snap = db.collection('users').document(str(uid)).get()
    if not user_snap.exists:
        return None
    data = user_snap.to_dict() or {}
    profile_snap = db.collection('profiles').document(str(uid)).get()
    profile = _profile_from_doc(str(uid), profile_snap.to_dict() or {})
    return User(
        id=str(uid),
        username=data.get('username', ''),
        email=data.get('email', ''),
        date_joined=parse_datetime(data.get('date_joined')) or timezone.now(),
        profile=profile,
        password_hash=data.get('password_hash', ''),
        is_active=data.get('is_active', True),
        firebase_uid=data.get('firebase_uid', ''),
        auth_provider=data.get('auth_provider', ''),
        email_verified=data.get('email_verified', False),
    )


def get_user_by_username(username):
    if not username:
        return None
    db = get_db()
    snap = db.collection('usernames').document(username.strip().lower()).get()
    if snap.exists:
        return get_user((snap.to_dict() or {}).get('uid'))
    matches = db.collection('users').where('username_lower', '==', username.strip().lower()).limit(1).stream()
    for match in matches:
        return get_user(match.id)
    return None


def get_user_by_email(email):
    if not email:
        return None
    db = get_db()
    snap = db.collection('emails').document(email.strip().lower()).get()
    if snap.exists:
        return get_user((snap.to_dict() or {}).get('uid'))
    return None


def get_user_by_firebase_uid(firebase_uid):
    if not firebase_uid:
        return None
    db = get_db()
    snap = db.collection('firebase_uids').document(str(firebase_uid)).get()
    if snap.exists:
        return get_user((snap.to_dict() or {}).get('uid'))
    matches = (
        db.collection('users')
        .where('firebase_uid', '==', str(firebase_uid))
        .limit(1)
        .stream()
    )
    for match in matches:
        return get_user(match.id)
    return None


def create_user(
    username,
    email,
    password=None,
    goal='',
    days_per_week=None,
    firebase_uid='',
    profile_data=None,
):
    username = username.strip()
    email = email.strip()
    username_lower = username.lower()
    email_lower = email.lower()
    firebase_uid = str(firebase_uid or '').strip()
    if not username or not email:
        raise ValueError('Username and email are required.')
    if get_user_by_username(username):
        raise ValueError('This username is already taken.')
    if get_user_by_email(email):
        raise ValueError('An account with this email already exists.')
    if firebase_uid and get_user_by_firebase_uid(firebase_uid):
        raise ValueError('This sign-in is already linked to another account.')

    profile_data = profile_data or {}
    db = get_db()
    user_ref = db.collection('users').document()
    uid = user_ref.id
    username_ref = db.collection('usernames').document(username_lower)
    email_ref = db.collection('emails').document(email_lower)
    firebase_ref = (
        db.collection('firebase_uids').document(firebase_uid)
        if firebase_uid
        else None
    )
    now = timezone.now()

    @transactional
    def create(transaction):
        if username_ref.get(transaction=transaction).exists:
            raise ValueError('This username is already taken.')
        if email_ref.get(transaction=transaction).exists:
            raise ValueError('An account with this email already exists.')
        if firebase_ref and firebase_ref.get(transaction=transaction).exists:
            raise ValueError('This sign-in is already linked to another account.')

        user_payload = {
            'username': username,
            'username_lower': username_lower,
            'email': email,
            'email_lower': email_lower,
            'password_hash': make_password(password) if password else '',
            'date_joined': now,
            'is_active': True,
            'auth_provider': 'firebase' if firebase_uid else 'password',
            'email_verified': bool(firebase_uid),
        }
        if firebase_uid:
            user_payload['firebase_uid'] = firebase_uid
        transaction.set(user_ref, user_payload)
        transaction.set(db.collection('profiles').document(uid), {
            'location': profile_data.get('location', ''),
            'bio': profile_data.get('bio', ''),
            'birth_date': to_iso_date(profile_data.get('birth_date')),
            'avatar_url': '',
            'cover_url': '',
            'status': 'rest',
            'status_updated_at': now,
            'goal': goal,
            'days_per_week': days_per_week,
        })
        transaction.set(username_ref, {'uid': uid})
        transaction.set(email_ref, {'uid': uid})
        if firebase_ref:
            transaction.set(firebase_ref, {'uid': uid})

    create(db.transaction())
    return get_user(uid)


def link_firebase_uid(user_id, firebase_uid):
    firebase_uid = str(firebase_uid or '').strip()
    if not firebase_uid:
        raise ValueError('A Firebase sign-in is required.')

    db = get_db()
    user_ref = db.collection('users').document(str(user_id))
    firebase_ref = db.collection('firebase_uids').document(firebase_uid)

    @transactional
    def link(transaction):
        user_snap = user_ref.get(transaction=transaction)
        if not user_snap.exists:
            raise ValueError('Account not found.')
        firebase_snap = firebase_ref.get(transaction=transaction)
        if firebase_snap.exists and (firebase_snap.to_dict() or {}).get('uid') != str(user_id):
            raise ValueError('This sign-in is already linked to another account.')
        current_uid = (user_snap.to_dict() or {}).get('firebase_uid', '')
        if current_uid and current_uid != firebase_uid:
            raise ValueError('This account is already linked to another sign-in.')
        transaction.update(user_ref, {
            'firebase_uid': firebase_uid,
            'auth_provider': 'firebase',
            'email_verified': True,
        })
        transaction.set(firebase_ref, {'uid': str(user_id)})

    link(db.transaction())
    return get_user(str(user_id))


def update_user(user, username, email):
    username = username.strip()
    email = email.strip()
    username_lower = username.lower()
    email_lower = email.lower()
    if not username or not email:
        raise ValueError('Username and email are required.')

    db = get_db()
    user_ref = db.collection('users').document(user.id)
    username_ref = db.collection('usernames').document(username_lower)
    email_ref = db.collection('emails').document(email_lower)

    @transactional
    def update(transaction):
        username_snap = username_ref.get(transaction=transaction)
        if username_snap.exists and (username_snap.to_dict() or {}).get('uid') != user.id:
            raise ValueError('This username is already taken.')
        email_snap = email_ref.get(transaction=transaction)
        if email_snap.exists and (email_snap.to_dict() or {}).get('uid') != user.id:
            raise ValueError('An account with this email already exists.')

        transaction.update(user_ref, {
            'username': username,
            'username_lower': username_lower,
            'email': email,
            'email_lower': email_lower,
        })
        if username_lower != user.username.lower():
            transaction.delete(db.collection('usernames').document(user.username.lower()))
            transaction.set(username_ref, {'uid': user.id})
        if email_lower != user.email.lower():
            transaction.delete(db.collection('emails').document(user.email.lower()))
            transaction.set(email_ref, {'uid': user.id})

    update(db.transaction())
    return get_user(user.id)


def update_profile(uid, data, avatar_url=None, cover_url=None):
    db = get_db()
    payload = {
        'location': data.get('location', ''),
        'bio': data.get('bio', ''),
        'birth_date': to_iso_date(data.get('birth_date')),
        'status': data.get('status', 'rest'),
        'status_updated_at': timezone.now(),
    }
    if avatar_url is not None:
        payload['avatar_url'] = avatar_url
    if cover_url is not None:
        payload['cover_url'] = cover_url
    db.collection('profiles').document(uid).set(payload, merge=True)
    return get_user(uid)


def set_status(uid, status):
    db = get_db()
    db.collection('profiles').document(uid).set({
        'status': status,
        'status_updated_at': timezone.now(),
    }, merge=True)


def create_otp(uid):
    code = f'{secrets.randbelow(900000) + 100000:06d}'
    now = timezone.now()
    get_db().collection('otps').document(uid).set({
        'code': code,
        'created_at': now,
        'expires_at': now + timedelta(minutes=5),
    })
    return code


def get_otp(uid):
    snap = get_db().collection('otps').document(uid).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    expires_at = parse_datetime(data.get('expires_at'))
    if expires_at and expires_at <= timezone.now():
        return None
    return data


def delete_otp(uid):
    get_db().collection('otps').document(uid).delete()


def count_users():
    return count_query(get_db().collection('users'))


def author_for(user):
    return Author(user.id, user.username, user.profile.avatar_url)
