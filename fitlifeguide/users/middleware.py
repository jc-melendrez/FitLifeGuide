from django.contrib.auth import BACKEND_SESSION_KEY, SESSION_KEY, load_backend
from django.contrib.auth.models import AnonymousUser


class FirestoreAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.session.get(SESSION_KEY)
        backend_path = request.session.get(BACKEND_SESSION_KEY)
        if user_id and backend_path:
            try:
                backend = load_backend(backend_path)
                request.user = backend.get_user(user_id) or AnonymousUser()
            except Exception:
                request.user = AnonymousUser()
        else:
            request.user = AnonymousUser()
        return self.get_response(request)
