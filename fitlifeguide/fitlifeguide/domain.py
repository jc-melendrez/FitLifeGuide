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
    firebase_uid: str = ''
    auth_provider: str = ''
    email_verified: bool = False

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


EXERCISE_TYPES = (
    ('strength', 'Strength'),
    ('timed', 'Timed'),
    ('cardio', 'Cardio'),
)
EXERCISE_TYPE_VALUES = tuple(key for key, _ in EXERCISE_TYPES)
MAX_EXERCISES = 30
MAX_CUSTOM_EXERCISES = 50
EXERCISE_NUMERIC_FIELDS = (
    'sets',
    'reps',
    'weight_kg',
    'seconds',
    'minutes',
    'distance_km',
)


def _number(value, minimum, converter):
    if value in (None, ''):
        return None
    try:
        number = converter(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= minimum else None


def _int_or_none(value, minimum=1):
    return _number(value, minimum, int)


def _float_or_none(value, minimum=0):
    return _number(value, minimum, float)


def _number_label(value):
    if value is None:
        return ''
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f'{number:.2f}'.rstrip('0').rstrip('.')


def _invalid_number(value, minimum):
    if value in (None, ''):
        return False
    return _number(value, minimum, float) is None


def _legacy_exercise_line(item):
    if not isinstance(item, dict):
        return str(item).strip()
    name = str(item.get('name') or '').strip()
    if not name:
        return ''
    parts = []
    sets = item.get('sets')
    reps = item.get('reps')
    if sets not in (None, '') and reps not in (None, ''):
        parts.append(f'{sets}x{reps}')
    elif reps not in (None, ''):
        parts.append(str(reps))
    elif sets not in (None, ''):
        parts.append(f'{sets} sets')
    weight = item.get('weight_kg')
    if weight not in (None, ''):
        parts.append(f'@ {weight} kg')
    seconds = item.get('seconds')
    if seconds not in (None, ''):
        parts.append(f'{seconds} s')
    minutes = item.get('minutes')
    if minutes not in (None, ''):
        parts.append(f'{minutes} min')
    distance = item.get('distance_km')
    if distance not in (None, ''):
        parts.append(f'{distance} km')
    detail = ', '.join(part for part in parts if part)
    return f'{name} - {detail}' if detail else name


def _exercise_display(name, exercise_type, sets, reps, weight_kg, seconds, minutes, distance_km):
    if exercise_type == 'timed':
        if sets and seconds:
            detail = f'{sets}×{seconds} s'
        elif seconds:
            detail = f'{seconds} s'
        elif sets:
            detail = f'{sets} sets'
        else:
            detail = ''
    elif exercise_type == 'cardio':
        parts = []
        if minutes:
            parts.append(f'{minutes} min')
        if distance_km is not None:
            parts.append(f'{_number_label(distance_km)} km')
        detail = ' · '.join(parts)
    else:
        if sets and reps:
            detail = f'{sets}×{reps}'
        elif reps:
            detail = f'{reps} reps'
        elif sets:
            detail = f'{sets} sets'
        else:
            detail = ''
        if weight_kg is not None:
            weight = f'{_number_label(weight_kg)} kg'
            detail = f'{detail} @ {weight}' if detail else f'@ {weight}'
    return f'{name} — {detail}' if detail else name


def _normalize_exercise(item, index):
    if not isinstance(item, dict):
        line = str(item).strip()
        return None, line
    name = str(item.get('name') or '').strip()
    if not name:
        return None, ''
    exercise_type = item.get('type')
    if exercise_type not in EXERCISE_TYPE_VALUES:
        exercise_type = 'strength'

    raw_values = {field: item.get(field) for field in EXERCISE_NUMERIC_FIELDS}
    invalid = False
    if exercise_type == 'strength':
        invalid = (
            _invalid_number(raw_values['sets'], 1)
            or _invalid_number(raw_values['reps'], 1)
            or _invalid_number(raw_values['weight_kg'], 0)
        )
    elif exercise_type == 'timed':
        invalid = (
            _invalid_number(raw_values['sets'], 1)
            or _invalid_number(raw_values['seconds'], 1)
        )
    elif exercise_type == 'cardio':
        invalid = (
            _invalid_number(raw_values['minutes'], 1)
            or _invalid_number(raw_values['distance_km'], 0)
        )
    if invalid:
        return None, _legacy_exercise_line(item)

    sets = _int_or_none(raw_values['sets'], 1)
    reps = _int_or_none(raw_values['reps'], 1)
    weight_kg = _float_or_none(raw_values['weight_kg'], 0)
    seconds = _int_or_none(raw_values['seconds'], 1)
    minutes = _int_or_none(raw_values['minutes'], 1)
    distance_km = _float_or_none(raw_values['distance_km'], 0)
    order = _int_or_none(item.get('order'), 0)
    return {
        'name': name,
        'type': exercise_type,
        'type_label': label_for(EXERCISE_TYPES, exercise_type),
        'order': index if order is None else order,
        'sets': sets,
        'reps': reps,
        'weight_kg': weight_kg,
        'seconds': seconds,
        'minutes': minutes,
        'distance_km': distance_km,
        'display': _exercise_display(
            name,
            exercise_type,
            sets,
            reps,
            weight_kg,
            seconds,
            minutes,
            distance_km,
        ),
    }, ''


def split_exercises(value):
    if isinstance(value, str):
        return [], value.strip()
    structured = []
    legacy = []
    for index, item in enumerate(value or []):
        exercise, legacy_line = _normalize_exercise(item, index)
        if exercise:
            structured.append(exercise)
        if legacy_line:
            legacy.append(legacy_line)
    structured.sort(key=lambda item: item['order'])
    for index, exercise in enumerate(structured):
        exercise['order'] = index
    return structured, '\n'.join(legacy)


def normalize_exercises(value):
    return split_exercises(value)[0]


def exercises_with_legacy(value, legacy_text=''):
    structured, derived_legacy = split_exercises(value)
    parts = [
        str(part).strip()
        for part in (legacy_text, derived_legacy)
        if part and str(part).strip()
    ]
    return structured, '\n'.join(parts)


def serialize_exercises(value):
    structured, _ = split_exercises(value)
    items = []
    for exercise in structured[:MAX_EXERCISES]:
        data = {
            'name': exercise['name'],
            'type': exercise['type'],
            'order': len(items),
        }
        if exercise['type'] == 'strength':
            if exercise['sets'] is not None:
                data['sets'] = exercise['sets']
            if exercise['reps'] is not None:
                data['reps'] = exercise['reps']
            if exercise['weight_kg'] is not None:
                data['weight_kg'] = float(exercise['weight_kg'])
        elif exercise['type'] == 'timed':
            if exercise['sets'] is not None:
                data['sets'] = exercise['sets']
            if exercise['seconds'] is not None:
                data['seconds'] = exercise['seconds']
        elif exercise['type'] == 'cardio':
            if exercise['minutes'] is not None:
                data['minutes'] = exercise['minutes']
            if exercise['distance_km'] is not None:
                data['distance_km'] = float(exercise['distance_km'])
        items.append(data)
    return items


def exercise_text(value):
    return ' '.join(item['name'] for item in normalize_exercises(value))


@dataclass
class Workout:
    STATUS_CHOICES = WORKOUT_STATUS

    id: str
    date: date
    week_start: date
    day_of_week: str
    title: str
    exercises: list = field(default_factory=list)
    legacy_exercises_text: str = ''
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
    exercises, legacy_exercises = exercises_with_legacy(
        data.get('exercises'),
        data.get('legacy_exercises_text'),
    )
    return Workout(
        id=doc_id,
        date=parse_date(data.get('date')),
        week_start=parse_date(data.get('week_start')),
        day_of_week=data.get('day_of_week', ''),
        title=data.get('title', ''),
        exercises=exercises,
        legacy_exercises_text=legacy_exercises,
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
