import json
import os

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore as gcloud

_db = None


class _EmulatorCredential(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def ensure_initialized():
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    project_id = (
        getattr(settings, 'FIREBASE_PROJECT_ID', '')
        or os.getenv('GOOGLE_CLOUD_PROJECT')
        or 'demo-fitlife'
    )

    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        firebase_admin.initialize_app(_EmulatorCredential(), {'projectId': project_id})
        return

    raw = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_JSON', '')
    path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_FILE', '')
    if raw:
        cred = credentials.Certificate(json.loads(raw))
    elif path:
        cred = credentials.Certificate(path)
    else:
        cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {'projectId': project_id})


def get_db():
    global _db
    if _db is None:
        ensure_initialized()
        _db = firestore.client()
    return _db


def doc_data(snapshot):
    return snapshot.to_dict() or {}


def delete_document_tree(doc_ref):
    for collection in doc_ref.collections():
        for child in collection.stream():
            delete_document_tree(child.reference)
    doc_ref.delete()


def delete_query(query):
    while True:
        docs = list(query.limit(400).stream())
        if not docs:
            return
        batch = get_db().batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()


def count_query(query):
    try:
        result = query.count().get()
        return int(result[0][0].value)
    except Exception:
        return sum(1 for _ in query.stream())


def increment(value=1):
    return gcloud.Increment(value)


SERVER_TIMESTAMP = firestore.SERVER_TIMESTAMP
