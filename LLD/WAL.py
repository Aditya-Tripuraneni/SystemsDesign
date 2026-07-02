from dataclasses import dataclass
from enum import Enum
import json
import os 


class Operation(Enum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"



@dataclass(frozen = True)
class Record:
    """Represents one append-only WAL entry."""

    lsn: int
    operation: Operation
    key: str
    val: int | None

    def to_dict(self):
        """Convert the record into a JSON-serializable dictionary."""
        return {
              "lsn": self.lsn,
              "operation": self.operation.value,
              "key": self.key,
              "val": self.val,
          }
    
    @staticmethod
    def from_dict(data):
        """Rebuild a Record from a dictionary loaded from JSON."""
        return Record(
              lsn=data["lsn"],
              operation=Operation(data["operation"]),
              key=data["key"],
              val=data["val"],
          )


class InMemoryDB:
    """Simple in-memory key-value store used as the replay target."""

    def __init__(self):
        self.db = {}
    
    def insertRecord(self, key, val) -> bool:
        """Insert a new key-value pair if the key does not already exist."""
        if key in self.db:
            return False
        
        self.db[key] = val
        return True

    def updateRecord(self, key, val) -> bool:
        """Update an existing key-value pair."""
        if key in self.db:
            self.db[key] = val
            return True

        return False

    def deleteRecord(self, key) -> bool:
        """Delete a key-value pair if the key exists."""
        if key in self.db:
            del self.db[key]
            return True

        return False
    
    def getRecord(self, key):
        """Return the stored value for a key, or None if it is missing."""
        return self.db.get(key, None)

class WriteAheadLog:
    """Append-only write-ahead log with JSONL persistence and recovery."""

    def __init__(self, wal_file= 'wal.jsonl', meta_file="wal.meta"):
        """Initialize the WAL state and persistence file paths."""
        self.records: list[Record] = []
        self.inMemoryDb = InMemoryDB()
        self.currentLSN = 1 # the next log sequence number to assign
        self.version = 1
        self.committedLSN = 0
        self.wal_file = wal_file
        self.meta_file = meta_file

    
    def _write_record_to_file(self, record: Record):
        """Persist a single record as one JSON line in the WAL file."""
        with open(self.wal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    
    def _write_commit_meta(self):
        """Persist the highest committed LSN to the metadata file."""
        with open(self.meta_file, "w", encoding="utf-8") as f:
            f.write(str(self.committedLSN))
            f.flush()
            os.fsync(f.fileno())

    
    def append(self, operation: Operation, key: str, val=None):
        """
        Create a new log record, assign the next LSN, and append it to disk.

        The WAL must record the change before any recovery-visible action is
        taken, which is why the record is persisted here.
        """
        if not isinstance(operation, Operation):
            raise TypeError("operation must be an Operation enum value")

        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be a non-empty string")

        if operation == Operation.DELETE and val is not None:
            raise ValueError("delete operations must not include a value")

        if operation in (Operation.INSERT, Operation.UPDATE) and val is None:
            raise ValueError("insert and update operations require a value")

        record = Record(lsn = self.currentLSN,
                        operation=operation,
                        key=key,
                        val=val)

        self.records.append(record)
        self._write_record_to_file(record)
        self.currentLSN += 1
        return record

    def commit(self, lsn: int):
        """
        Advance the durable commit boundary up to the given LSN.

        Only LSNs that have already been recorded can be committed.
        """
        if lsn <= self.currentLSN -1 and lsn > self.committedLSN:
            self.committedLSN = lsn
            self._write_commit_meta()
            return

        raise ValueError("Cannot commit an LSN that has not been recorded yet")
        
    def replay(self):
        """
        Apply committed log records to the in-memory database.

        This is useful after a write has been durably logged but applying the
        change to the database failed, or when you want to re-drive committed
        log entries without performing full crash recovery.
        """
        for record in self.records:
            if record.lsn <= self.committedLSN:
                # apply to the db
                key = record.key
                val = record.val
                op = record.operation

                if op == Operation.INSERT:
                    self.inMemoryDb.insertRecord(key, val)
                elif op == Operation.UPDATE:
                    self.inMemoryDb.updateRecord(key, val)
                elif op == Operation.DELETE:
                    self.inMemoryDb.deleteRecord(key)
                else: 
                    raise Exception("Invalid operation")
    
    def _load_records(self):
        """Load all WAL records from the JSONL file into memory."""
        self.records = []

        if not os.path.exists(self.wal_file):
            return
    
        with open(self.wal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)
                self.records.append(Record.from_dict(data))
    
    def _load_commit_meta(self):
        """Load the committed LSN from the metadata file."""
        if not os.path.exists(self.meta_file):
            self.committedLSN = 0
            return

        with open(self.meta_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
            self.committedLSN = int(text) if text else 0
    
    def recover(self):
        """
        Restore the in-memory database from persisted WAL state.

        This loads the records and commit metadata, then replays only the
        committed operations into a fresh in-memory database.
        """
        self._load_records()
        self._load_commit_meta()
        self.inMemoryDb = InMemoryDB()
        self.replay()
