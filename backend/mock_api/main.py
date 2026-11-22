from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="小苏内部系统 Mock")


class Employee(BaseModel):
    id: str
    name: str
    dept: str


class Attendance(BaseModel):
    employee_id: str
    date: date
    check_in: str


class Order(BaseModel):
    id: str
    date: date
    amount_fen: int
    status: str


# Editable demo fixtures. Day offsets are relative to last week's Monday.
EMPLOYEES = {
    item.id: item for item in [
        Employee(id="001", name="张三", dept="研发部"),
        Employee(id="002", name="李四", dept="财务部"),
        Employee(id="003", name="王五", dept="销售部"),
        Employee(id="004", name="赵敏", dept="人事部"),
        Employee(id="005", name="陈晨", dept="运营部"),
        Employee(id="006", name="刘洋", dept="研发部"),
        Employee(id="007", name="周宁", dept="客服部"),
        Employee(id="008", name="吴桐", dept="采购部"),
        Employee(id="009", name="郑悦", dept="市场部"),
        Employee(id="010", name="孙浩", dept="行政部"),
    ]
}
# (day offset, check-in time); repeated dates test date deduplication.
ATTENDANCE_DATA = {
    "001": [(0, "08:55"), (1, "08:58"), (2, "09:00"), (3, "08:50"), (4, "08:59")],
    "002": [(0, "09:05"), (1, "08:56"), (3, "08:57"), (4, "09:00")],
    "003": [(0, "08:45"), (0, "08:46"), (2, "09:10"), (4, "08:55")],
    "004": [],
    "005": [(0, "08:50"), (1, "08:50"), (2, "08:50"), (3, "08:50"), (4, "08:50")],
    "006": [(0, "09:02"), (1, "08:59"), (2, "08:58"), (4, "08:56")],
    "007": [(1, "08:55"), (3, "08:55")],
    "008": [(0, "08:52"), (1, "08:53"), (2, "08:54"), (3, "08:55"), (4, "08:56")],
    "009": [(2, "09:00")],
    "010": [(0, "08:40"), (1, "08:40"), (2, "08:40"), (3, "08:40"), (4, "08:40")],
}
# (order ID, day offset, amount in cents, status).
ORDER_DATA = [
    ("O001", 0, 10000, "paid"), ("O002", 0, 25000, "paid"),
    ("O003", 1, 8800, "paid"), ("O004", 1, 12000, "refunded"),
    ("O005", 2, 5000, "paid"), ("O006", 3, 36000, "paid"),
    ("O007", 3, 9900, "cancelled"), ("O008", 4, 15000, "paid"),
    ("O009", 5, 20000, "refunded"), ("O010", 6, 6600, "paid"),
]


def last_monday(today: date) -> date:
    return today - timedelta(days=today.weekday() + 7)


def validate_range(start: date, end: date) -> None:
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "日期范围须为正向且不超过 366 天")


@app.get("/api/employee/{employee_id}")
def employee(employee_id: str) -> Employee:
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, "员工不存在")
    return EMPLOYEES[employee_id]


@app.get("/api/attendance")
def attendance(employee_id: str, start_date: date, end_date: date) -> list[Attendance]:
    employee(employee_id)
    validate_range(start_date, end_date)
    monday = last_monday(datetime.now(ZoneInfo("Asia/Shanghai")).date())
    return [Attendance(employee_id=employee_id, date=day, check_in=check_in)
            for offset, check_in in ATTENDANCE_DATA.get(employee_id, [])
            if start_date <= (day := monday + timedelta(days=offset)) <= end_date]


@app.get("/api/orders")
def orders(start_date: date, end_date: date, limit: int = Query(100, ge=1, le=100)) -> list[Order]:
    validate_range(start_date, end_date)
    monday = last_monday(datetime.now(ZoneInfo("Asia/Shanghai")).date())
    return [Order(id=order_id, date=day, amount_fen=amount, status=status)
            for order_id, offset, amount, status in ORDER_DATA
            if start_date <= (day := monday + timedelta(days=offset)) <= end_date][:limit]
