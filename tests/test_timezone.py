import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfoNotFoundError

from crawler.timezone import shanghai_timezone


class ShanghaiTimezoneTests(unittest.TestCase):
    def test_uses_fixed_china_offset_when_tzdata_is_unavailable(self):
        def missing_zoneinfo(_key):
            raise ZoneInfoNotFoundError("tzdata unavailable")

        tz = shanghai_timezone(missing_zoneinfo)

        self.assertEqual(tz.utcoffset(datetime(2026, 8, 2)), timedelta(hours=8))
        self.assertEqual(tz.tzname(datetime(2026, 8, 2)), "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
