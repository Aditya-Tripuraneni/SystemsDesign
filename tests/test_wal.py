import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from LLD.WAL import Operation, WriteAheadLog


def test_wal_append_persists_jsonl_record(tmp_path):
    wal_file = tmp_path / "wal.jsonl"
    meta_file = tmp_path / "wal.meta"
    wal = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))

    record = wal.append(Operation.INSERT, "user:1", 42)

    assert record.lsn == 1
    assert wal.currentLSN == 2
    assert wal.records == [record]
    assert wal_file.read_text(encoding="utf-8").strip() == (
        '{"lsn": 1, "operation": "insert", "key": "user:1", "val": 42}'
    )


def test_wal_commit_persists_committed_lsn(tmp_path):
    wal_file = tmp_path / "wal.jsonl"
    meta_file = tmp_path / "wal.meta"
    wal = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))

    wal.append(Operation.INSERT, "user:1", 42)
    wal.commit(1)

    assert wal.committedLSN == 1
    assert meta_file.read_text(encoding="utf-8").strip() == "1"


def test_wal_replay_applies_only_committed_records(tmp_path):
    wal_file = tmp_path / "wal.jsonl"
    meta_file = tmp_path / "wal.meta"
    wal = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))

    wal.append(Operation.INSERT, "user:1", 10)
    wal.append(Operation.UPDATE, "user:1", 20)
    wal.append(Operation.DELETE, "user:1")
    wal.commit(2)
    wal.replay()

    assert wal.inMemoryDb.getRecord("user:1") == 20


def test_wal_recover_rebuilds_db_from_disk(tmp_path):
    wal_file = tmp_path / "wal.jsonl"
    meta_file = tmp_path / "wal.meta"

    wal = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))
    wal.append(Operation.INSERT, "user:1", 10)
    wal.append(Operation.UPDATE, "user:1", 20)
    wal.append(Operation.DELETE, "user:1")
    wal.commit(2)

    recovered = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))
    recovered.recover()

    assert recovered.committedLSN == 2
    assert recovered.currentLSN == 1
    assert recovered.inMemoryDb.getRecord("user:1") == 20


def test_wal_append_validates_operation_and_payload(tmp_path):
    wal_file = tmp_path / "wal.jsonl"
    meta_file = tmp_path / "wal.meta"
    wal = WriteAheadLog(wal_file=str(wal_file), meta_file=str(meta_file))

    try:
        wal.append("insert", "user:1", 42)
        assert False, "expected TypeError"
    except TypeError:
        pass

    try:
        wal.append(Operation.DELETE, "user:1", 42)
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        wal.append(Operation.INSERT, "user:1")
        assert False, "expected ValueError"
    except ValueError:
        pass
