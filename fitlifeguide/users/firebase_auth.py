import logging

from firebase_admin import auth

from fitlifeguide.firestore import ensure_initialized

logger = logging.getLogger(__name__)


class FirebaseAuthError(Exception):
    status_code = 401


class MissingFirebaseToken(FirebaseAuthError):
    status_code = 400


class InvalidFirebaseToken(FirebaseAuthError):
    status_code = 401


class UnverifiedFirebaseEmail(FirebaseAuthError):
    status_code = 403


class UnsupportedFirebaseProvider(FirebaseAuthError):
    status_code = 403


def verify_firebase_id_token(token):
    if not token:
        raise MissingFirebaseToken('A Firebase sign-in token is required.')

    ensure_initialized()
    try:
        decoded = auth.verify_id_token(token, check_revoked=False)
    except Exception as exc:
        logger.warning('Firebase token verification failed: %s', exc)
        raise InvalidFirebaseToken('This sign-in link is invalid or has expired.') from exc

    if not decoded.get('email_verified'):
        raise UnverifiedFirebaseEmail('Please verify your email address first.')

    provider = (decoded.get('firebase') or {}).get('sign_in_provider')
    if provider != 'emailLink':
        raise UnsupportedFirebaseProvider('Use the email sign-in link to continue.')

    email = (decoded.get('email') or '').strip().lower()
    uid = (decoded.get('uid') or '').strip()
    if not uid or not email:
        raise InvalidFirebaseToken('This sign-in token is missing an email address.')

    return {
        'uid': uid,
        'email': email,
        'name': (decoded.get('name') or '').strip(),
    }
