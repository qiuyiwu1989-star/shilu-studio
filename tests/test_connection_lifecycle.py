import sqlite3,tempfile,unittest
from pathlib import Path
from shilu.core import Store
class ConnectionLifecycleTests(unittest.TestCase):
 def test_commit_and_close(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db')
   with s.connect() as db:db.execute("INSERT INTO projects VALUES('test','{}')")
   with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
   with s.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM projects').fetchone()[0],1)
 def test_rollback_and_close(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db')
   with s.connect() as db:db.execute("INSERT INTO projects VALUES('before','{}')")
   with self.assertRaisesRegex(ValueError,'abort'):
    with s.connect() as db:
     db.execute("INSERT INTO projects VALUES('discard','{}')")
     raise ValueError('abort')
   with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
   with s.connect() as db:self.assertEqual(db.execute('SELECT id FROM projects').fetchall(),[('before',)])
