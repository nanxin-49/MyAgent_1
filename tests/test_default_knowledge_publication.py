"""Approved seed and guarded upgrade tests; no production collection access."""
import json
import hashlib
from pathlib import Path
import pytest

from test_rag_contract import knowledge_base
from mcp.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'mcp/knowledge_assets/default_business_v1.json'


def test_default_seed_is_exact_approved_documents():
    approved = json.loads(ASSET.read_text(encoding='utf-8'))['documents']
    kb = knowledge_base()
    kb._load_default_docs()
    actual = {doc.document_id: doc.model_dump(mode='json')
              for doc, _ in kb._publications(kb._snapshot()).values()}
    from mcp.rag_contract import KnowledgeDocument
    expected = {r['document']['document_id']: KnowledgeDocument.model_validate(r['document']).model_dump(mode='json')
                for r in approved}
    assert actual == expected


@pytest.mark.parametrize('field,value', [('content','changed'), ('source','other'), ('effective_at',None)])
def test_asset_tampering_fails_closed(tmp_path, monkeypatch, field, value):
    import mcp.default_knowledge_asset as assets
    data = json.loads(ASSET.read_text(encoding='utf-8'))
    data['documents'][0]['document'][field] = value
    altered = tmp_path / 'asset.json'
    altered.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(assets, 'ASSET', altered)
    with pytest.raises(ValueError, match='asset mismatch'):
        assets.load_approved_defaults()


def test_actual_revision_chunk_and_no_context_split():
    from mcp.default_knowledge_asset import load_approved_defaults
    from mcp.rag_contract import KnowledgeDocument
    approved = json.loads(ASSET.read_text(encoding='utf-8'))['documents']
    kb = knowledge_base()
    for data, row in zip(load_approved_defaults(), approved):
        doc = KnowledgeDocument.model_validate(data)
        assert hashlib.sha256(doc.model_dump_json().encode()).hexdigest() == row['publication_revision']
        assert kb._chunk_text(doc.content) == [doc.content]


def test_legacy_upgrade_uses_explicit_ids_and_removes_old_rows():
    from mcp.default_knowledge_publication import assert_owned
    kb = knowledge_base()
    legacy = json.loads((ROOT / 'evaluation/reports/hardening/A05/b0-calibrated-20261013/default_snapshot_formal.json').read_text(encoding='utf-8'))
    kb._collection.rows.update({key: tuple(row) for key, row in legacy.items()})
    with pytest.raises(RuntimeError, match='legacy knowledge'):
        kb.search('新业务库升级前可检索性检查', 5)
    assert_owned(kb)
    kb._load_default_docs()
    assert not set(legacy) & set(kb._snapshot())
    assert len(kb._publications(kb._snapshot())) == 6
    assert kb.doc_count == 6
    assert len(kb.search('新业务库升级后检索检查', 5)) == 5


def test_unrelated_record_refused_before_any_mutation():
    from mcp.default_knowledge_publication import publish_approved
    kb = knowledge_base()
    kb._collection.rows['foreign'] = ('keep', {'document_id':'foreign','source':'business:other'})
    before = dict(kb._collection.rows)
    with pytest.raises(ValueError, match='unknown record'):
        publish_approved(kb)
    assert kb._collection.rows == before


def test_nonempty_publish_needs_backup():
    from mcp.default_knowledge_publication import publish_approved
    kb = knowledge_base()
    kb._load_default_docs()
    before = dict(kb._collection.rows)
    with pytest.raises(ValueError, match='requires a verified full backup'):
        publish_approved(kb)
    assert kb._collection.rows == before


def test_check_assets_has_no_chroma_connection(monkeypatch):
    from mcp import seed_demo_knowledge as seed
    import sys
    monkeypatch.setattr(sys, 'argv', ['seed', '--check-assets'])
    monkeypatch.setattr(seed, 'KnowledgeBase', lambda **kw: pytest.fail('must not connect'))
    assert seed.main() == 0


def backup_kb():
    from test_rag_contract import FakeCollection
    class VectorCollection(FakeCollection):
        def get(self, *, include):
            data = super().get(include=include)
            if 'embeddings' in include:
                data['embeddings'] = [[0.0]*1024 for _ in data['ids']]
            return data
    kb = knowledge_base()
    kb._collection = VectorCollection()
    kb._collection_name = 'cartcare_kbprep_unit'
    return kb


def test_backup_change_and_corruption_refused_without_mutation(tmp_path):
    from mcp.default_knowledge_publication import write_backup, publish_approved
    kb = backup_kb()
    kb._load_default_docs()
    path = tmp_path / 'full.json'
    write_backup(kb,path)
    with pytest.raises(FileExistsError):
        write_backup(kb,path)
    raw = path.read_bytes()
    path.write_bytes(raw+b' ')
    before = dict(kb._collection.rows)
    with pytest.raises(ValueError, match='hash mismatch'):
        publish_approved(kb,path)
    assert kb._collection.rows == before
    path.write_bytes(raw)
    key = next(i for i,(_,m) in kb._collection.rows.items() if m.get('record_type') == 'chunk')
    text, meta = kb._collection.rows[key]
    kb._collection.rows[key] = (text+'changed', meta)
    before = dict(kb._collection.rows)
    with pytest.raises(ValueError, match='changed since backup'):
        publish_approved(kb,path)
    assert kb._collection.rows == before


def test_wrong_target_restore_refused_before_delete(tmp_path):
    from mcp.default_knowledge_publication import write_backup, restore_backup
    kb = backup_kb()
    kb._load_default_docs()
    path = tmp_path / 'full.json'
    write_backup(kb,path)
    kb._collection_name = 'cartcare_kbprep_other'
    before = dict(kb._collection.rows)
    with pytest.raises(ValueError, match='target/configuration mismatch'):
        restore_backup(kb,path)
    assert kb._collection.rows == before


def test_ordinary_seed_reads_the_single_asset(monkeypatch):
    import sys
    from mcp import seed_demo_knowledge as seed
    kb = backup_kb()
    monkeypatch.setattr(seed,'KnowledgeBase',lambda **kw:kb)
    monkeypatch.setattr(sys,'argv',['seed'])
    assert seed.main() == 0
    assert len(kb._publications(kb._snapshot())) == 6


def test_reset_reads_same_asset_and_preserves_metadata(monkeypatch):
    import sys
    from mcp import seed_demo_knowledge as seed
    from test_rag_contract import FakeCollection
    kb = backup_kb()
    kb._collection_name = KnowledgeBase.COLLECTION_NAME
    kb._collection.metadata['description'] = 'preserve exact metadata'
    class Client:
        def delete_collection(self,name):
            assert name == kb._collection_name
        def get_or_create_collection(self, *, name, metadata):
            col = FakeCollection()
            col.metadata = metadata
            return col
    kb._client = Client()
    before = dict(kb._collection.metadata)
    assert kb.rebuild_demo_collection() == 6
    assert kb._collection.metadata == before
    actual = {doc.document_id:doc.content for doc,_ in kb._publications(kb._snapshot()).values()}
    assert actual == {r['document']['document_id']:r['document']['content'] for r in json.loads(ASSET.read_text(encoding='utf-8'))['documents']}


def test_readonly_release_verifier_requires_all_six_and_preserves_rows():
    from mcp.default_knowledge_publication import verify_current
    kb = backup_kb()
    with pytest.raises(ValueError, match='six ready'):
        verify_current(kb)
    kb._load_default_docs()
    before = dict(kb._collection.rows)
    report = verify_current(kb)
    assert report['mechanical_passed'] and report['effective_chunks'] == 6
    assert len(report['business_cases']) == 6
    assert kb._collection.rows == before


def test_readonly_cli_missing_collection_never_creates():
    from mcp.seed_demo_knowledge import ExistingKnowledgeBase
    kb = ExistingKnowledgeBase.__new__(ExistingKnowledgeBase)
    kb._collection_name = 'cartcare_kbprep_missing_unit'
    class Client:
        def get_collection(self, **kw):
            raise ValueError('not found')
        def get_or_create_collection(self, **kw):
            pytest.fail('read-only operation attempted creation')
    kb._client = Client()
    with pytest.raises(ValueError, match='not found'):
        kb._open_collection()
