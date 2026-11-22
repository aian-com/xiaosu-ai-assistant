"""Run with python -m unittest mock_api.test_demo (no external services)."""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
import httpx
from app.agent.tools import execute
from mock_api.main import app, last_monday


class DemoTests(unittest.TestCase):
    def test_tools_and_api(self):
        async def check():
            monday = last_monday(datetime.now(ZoneInfo("Asia/Shanghai")).date())
            dates = {"start_date": str(monday), "end_date": str(monday + timedelta(days=6))}
            original = httpx.AsyncClient
            def client(**kwargs):
                return original(transport=httpx.ASGITransport(app=app), **kwargs)
            with patch("app.agent.tools.httpx.AsyncClient", client):
                employee = await execute("get_employee", {"employee_id": "002"})
                self.assertEqual(employee["employee"]["name"], "李四")
                self.assertEqual(employee["employee"]["dept"], "财务部")
                for number, count, days in [("001", 5, 5), ("002", 4, 4), ("003", 4, 3), ("004", 0, 0)]:
                    result = await execute("get_attendance", {**dates, "employee_id": number})
                    self.assertEqual(len(result["records"]), count)
                    self.assertEqual(result["days_with_check_in"], days)
                result = await execute("get_orders", dates)
                self.assertEqual(result["order_count"], 10)
                self.assertEqual(result["net_amount_fen"], 106400)
                with self.assertRaises(httpx.HTTPStatusError):
                    await execute("get_employee", {"employee_id": "999"})
                async with client(base_url="http://test") as api:
                    self.assertEqual((await api.get("/api/orders", params={**dates, "limit": 2})).status_code, 200)
                    self.assertEqual(len((await api.get("/api/orders", params={**dates, "limit": 2})).json()), 2)
                    self.assertEqual((await api.get("/api/attendance", params={**dates, "employee_id": "999"})).status_code, 404)
                    self.assertEqual((await api.get("/api/orders", params={"start_date": dates["end_date"], "end_date": dates["start_date"]})).status_code, 422)
        asyncio.run(check())
