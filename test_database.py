import asyncio
import tempfile
import unittest
from pathlib import Path

from database import Database

class DatabaseTests(unittest.TestCase):
    def test_settings_round_trip(self):
        async def run():
            with tempfile.TemporaryDirectory() as tmp:
                db = Database(str(Path(tmp) / "test.sqlite3"))
                await db.initialize()
                await db.set_setting(123, "threshold", 7)
                self.assertEqual(await db.get_setting(123, "threshold"), 7)
                await db.close()
        asyncio.run(run())

    def test_moderation_case_round_trip(self):
        async def run():
            with tempfile.TemporaryDirectory() as tmp:
                db = Database(str(Path(tmp) / "test.sqlite3"))
                await db.initialize()
                case_id = await db.record_case(1, 2, 3, "warn", "test", "2026-01-01T00:00:00+00:00")
                rows = await db.get_cases(1, 2)
                self.assertGreater(case_id, 0)
                self.assertEqual(rows[0]["action"], "warn")
                await db.close()
        asyncio.run(run())

if __name__ == "__main__":
    unittest.main()
