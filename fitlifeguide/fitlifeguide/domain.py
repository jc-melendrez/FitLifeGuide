from dataclasses import dataclass, field
from datetime import date, datetime, timezone as dt_timezone
from hashlib import sha256

from django.utils import timezone

DEFAULT_AVATAR = '/static/mainpage/default-avatar.png'
DEFAULT_COVER = '/static/mainpage/default-cover.jpg'

PROFILE_STATUS = (
    ('run', 'Run'),
    ('lift', 'Lift'),
    ('rest', 'Rest'),
    ('cook', 'Cook'),
)
MEAL_TYPES = (
    ('breakfast', 'Breakfast'),
    ('lunch', 'Lunch'),
    ('dinner', 'Dinner'),
    ('snack', 'Snack'),
)
MEAL_STATUS = (
    ('planned', 'Planned'),
    ('eaten', 'Eaten'),
    ('skipped', 'Skipped'),
)
WORKOUT_STATUS = (
    ('planned', 'Planned'),
    ('completed', 'Completed'),
    ('missed', 'Missed'),
)
WEEKDAYS = (
    ('Mon', 'Monday'),
    ('Tue', 'Tuesday'),
    ('Wed', 'Wednesday'),
    ('Thu', 'Thursday'),
    ('Fri', 'Friday'),
    ('Sat', 'Saturday'),
    ('Sun', 'Sunday'),
)


def label_for(choices, value):
    return dict(choices).get(value, value or '')


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value))
    if timezone.is_naive(result):
        result = timezone.make_aware(result, dt_timezone.utc)
    return result


def to_iso_date(value):
    return value.isoformat() if value else None


@dataclass
class Image:
    url: str


class CommentList(list):
    @property
    def count(self):
        return len(self)

    @property
    def exists(self):
        return bool(self)


@dataclass
class Profile:
    user_id: str
    location: str = ''
    bio: str = ''
    birth_date: date | None = None
    avatar_url: str = DEFAULT_AVATAR
    cover_url: str = DEFAULT_COVER
    status: str = 'rest'
    status_updated_at: datetime | None = None
    goal: str = ''
    days_per_week: int | None = None

    @property
    def avatar(self):
        return Image(self.avatar_url or DEFAULT_AVATAR)

    @property
    def cover_image(self):
        return Image(self.cover_url or DEFAULT_COVER)

    @property
    def get_status_display(self):
        return label_for(PROFILE_STATUS, self.status)


class _Pk:
    def value_to_string(self, obj):
        return str(obj.pk)

    def to_python(self, value):
        return value


class _Meta:
    pk = _Pk()


@dataclass
class User:
    _meta = _Meta()

    id: str
    username: str
    email: str
    date_joined: datetime
    profile: Profile
    password_hash: str = field(default='', repr=False)
    is_active: bool = True
    backend: str = ''

    @property
    def pk(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_username(self):
        return self.username

    def save(self, *args, **kwargs):
        return None

    def get_session_auth_hash(self):
        return sha256(self.password_hash.encode('utf-8')).hexdigest()

    def __eq__(self, other):
        return getattr(other, 'id', None) == self.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class Author:
    id: str
    username: str
    avatar_url: str = DEFAULT_AVATAR

    @property
    def profile(self):
        return Profile(self.id, avatar_url=self.avatar_url)

    def __eq__(self, other):
        return getattr(other, 'id', None) == self.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class Workout:
    STATUS_CHOICES = WORKOUT_STATUS

    id: str
    date: date
    week_start: date
    day_of_week: str
    title: str
    exercises: str = ''
    duration_minutes: int | None = None
    goal: str = ''
    status: str = 'planned'
    notes: str = ''
    user: Author | None = None

    @property
    def get_status_display(self):
        return label_for(WORKOUT_STATUS, self.status)


@dataclass
class Meal:
    id: str
    date: date
    week_start: date
    day_of_week: str
    meal_type: str
    food_items: str
    calories: int | None = None
    status: str = 'planned'
    notes: str = ''
    user: Author | None = None

    @property
    def get_meal_type_display(self):
        return label_for(MEAL_TYPES, self.meal_type)

    @property
    def get_status_display(self):
        return label_for(MEAL_STATUS, self.status)


@dataclass
class BlogPost:
    id: str
    title: str
    slug: str
    author: Author
    content: str
    created_at: datetime
    updated_at: datetime | None = None
    image: Image | None = None
    workout: Workout | None = None
    published: bool = False
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    comments: CommentList = field(default_factory=CommentList)

    @property
    def total_likes(self):
        return self.like_count


@dataclass
class Comment:
    id: str
    post_id: str
    author: Author
    content: str
    created_at: datetime
    updated_at: datetime | None = None
    parent_id: str | None = None
    depth: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    children: CommentList = field(default_factory=CommentList)

    @property
    def total_likes(self):
        return self.like_count

    @property
    def get_descendant_count(self):
        return sum(1 + child.get_descendant_count for child in self.children)

    @property
    def is_leaf_node(self):
        return not self.children


@dataclass
class Forum:
    id: str
    name: str
    slug: str
    description: str = ''
    thread_count: int = 0


@dataclass
class Thread:
    id: str
    forum: Forum
    title: str
    slug: str
    author: Author
    content: str
    created_at: datetime
    like_count: int = 0
    reply_count: int = 0
    liked_by_me: bool = False

    @property
    def total_likes(self):
        return self.like_count


@dataclass
class ForumPost:
    id: str
    thread_id: str
    author: Author
    content: str
    created_at: datetime
    updated_at: datetime | None = None
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    comments: CommentList = field(default_factory=CommentList)

    @property
    def total_likes(self):
        return self.like_count


@dataclass
class VideoHistory:
    id: str
    user_id: str
    video_id: str
    title: str
    thumbnail_url: str
    channel_title: str
    duration: str
    viewed_at: datetime


def author_from_doc(data, fallback_id=''):
    return Author(
        id=data.get('author_id') or fallback_id,
        username=data.get('author_username', ''),
        avatar_url=data.get('author_avatar_url') or DEFAULT_AVATAR,
    )


def workout_from_doc(doc_id, data):
    return Workout(
        id=doc_id,
        date=parse_date(data.get('date')),
        week_start=parse_date(data.get('week_start')),
        day_of_week=data.get('day_of_week', ''),
        title=data.get('title', ''),
        exercises=data.get('exercises', ''),
        duration_minutes=data.get('duration_minutes'),
        goal=data.get('goal', ''),
        status=data.get('status', 'planned'),
        notes=data.get('notes', ''),
        user=Author(
            id=data.get('user_id', ''),
            username=data.get('username', ''),
            avatar_url=data.get('avatar_url') or DEFAULT_AVATAR,
        ) if data.get('username') else None,
    )


def meal_from_doc(doc_id, data):
    return Meal(
        id=doc_id,
        date=parse_date(data.get('date')),
        week_start=parse_date(data.get('week_start')),
        day_of_week=data.get('day_of_week', ''),
        meal_type=data.get('meal_type', ''),
        food_items=data.get('food_items', ''),
        calories=data.get('calories'),
        status=data.get('status', 'planned'),
        notes=data.get('notes', ''),
        user=Author(
            id=data.get('user_id', ''),
            username=data.get('username', ''),
            avatar_url=data.get('avatar_url') or DEFAULT_AVATAR,
        ) if data.get('username') else None,
    )


def now():
    return timezone.now()
