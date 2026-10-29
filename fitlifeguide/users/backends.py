from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password

from .repositories import get_user, get_user_by_username


class FirestoreBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        user = get_user_by_username(username)
        if not user or not user.is_active:
            return None
        if check_password(password, user.password_hash):
            user.backend = f'{self.__module__}.{self.__class__.__name__}'
            return user
        return None

    def get_user(self, user_id):
        return get_user(user_id)
