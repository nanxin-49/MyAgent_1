"""Single approved seed asset. Mismatch fails closed, without rewriting data."""
import hashlib
import json
from pathlib import Path

from .rag_contract import KnowledgeDocument

ASSET = Path(__file__).with_name('knowledge_assets') / 'default_business_v1.json'
APPROVAL = ASSET.with_name('default_business_v1.approval.json')
APPROVED_SHA256 = '17e3c606365c203589919321b166e942e6aab569d539ce631f447a5439cd018d'


def load_approved_defaults() -> list[dict]:
    raw = ASSET.read_bytes()
    approval = json.loads(APPROVAL.read_text(encoding='utf-8'))
    if (hashlib.sha256(raw).hexdigest() != APPROVED_SHA256
            or approval['asset_sha256'] != APPROVED_SHA256
            or approval['approval'] != 'user_approved_content_and_metadata_only'):
        raise ValueError('approved default knowledge asset mismatch; stop for human review')
    rows = json.loads(raw)['documents']
    if len(rows) != 6 or len({r['document']['document_id'] for r in rows}) != 6:
        raise ValueError('approved document count/identity mismatch')
    reviewed = {r['document_id']: r for r in approval['documents']}
    for row in rows:
        doc = KnowledgeDocument.model_validate(row['document'])
        revision = hashlib.sha256(doc.model_dump_json().encode()).hexdigest()
        content_hash = hashlib.sha256(doc.content.encode()).hexdigest()
        key = 'publication_' + hashlib.sha256(f'{doc.document_id}\0{doc.policy_version or ""}'.encode()).hexdigest()
        chunk_id = hashlib.sha256(f'{key}\0{revision}\0{0}'.encode()).hexdigest()
        if (revision != row['publication_revision'] or content_hash != row['content_sha256']
                or chunk_id != row['chunk_id'] or len(doc.content) > 500
                or reviewed[doc.document_id]['publication_revision'] != revision
                or reviewed[doc.document_id]['content_sha256'] != content_hash):
            raise ValueError('approved metadata/revision/chunk mismatch; stop for human review')
    return [r['document'] for r in rows]
