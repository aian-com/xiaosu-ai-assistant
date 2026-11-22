import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
import httpx
from pydantic import BaseModel, Field, model_validator
from app.config import get_settings
from app.knowledge.service import search


class Query(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class EmployeeArgs(BaseModel):
    employee_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")


class Dates(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self) -> "Dates":
        if not 0 <= (self.end_date - self.start_date).days <= 366:
            raise ValueError("日期范围须为正向且不超过 366 天")
        return self


class AttendanceArgs(Dates, EmployeeArgs):
    pass


class ClockArgs(BaseModel):
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class Calculation(BaseModel):
    operation: Literal["sum", "count"]
    values: list[Decimal] = Field(max_length=1000)


REGISTRY: dict[str, tuple[type[BaseModel], str]] = {
    "search_knowledge": (Query, "搜索当前有效公司制度。制度与追问必须重新检索；无证据则拒答。"),
    "get_employee": (EmployeeArgs, "通过员工编号查询员工部门；不知道编号时请询问。"),
    "get_attendance": (AttendanceArgs, "查询日期范围内员工打卡记录；天数按打卡日期去重。"),
    "get_orders": (Dates, "查询订单，返回数量和退款后净额，金额单位为分。相对日期先查当前时间。"),
    "current_time": (ClockArgs, "获取上海当前时间和上一个完整自然周日期范围。"),
    "calculate": (Calculation, "对数值安全求和或计数。"),
}


def schemas() -> list[dict]:
    return [{"type": "function", "function": {"name": name, "description": desc, "parameters": model.model_json_schema()}}
            for name, (model, desc) in REGISTRY.items()]


async def execute(name: str, arguments: dict) -> dict:
    if name not in REGISTRY:
        raise ValueError("未知工具")
    args = REGISTRY[name][0].model_validate(arguments)
    if isinstance(args, Query):
        return {"evidence": await search(args.query)}
    if isinstance(args, ClockArgs):
        current = datetime.now(ZoneInfo(args.timezone))
        monday = current.date() - timedelta(days=current.weekday() + 7)
        return {"now": current.isoformat(), "last_week_start": str(monday), "last_week_end": str(monday + timedelta(days=6))}
    if isinstance(args, Calculation):
        return {"result": str(sum(args.values, Decimal(0))) if args.operation == "sum" else len(args.values)}
    params = args.model_dump(mode="json")
    path = "/api/attendance" if name == "get_attendance" else "/api/orders"
    if name == "get_employee":
        path, params = f"/api/employee/{params['employee_id']}", {}
    async with httpx.AsyncClient(base_url=get_settings().mock_api_url, timeout=15) as client:
        for attempt in range(3):
            try:
                response = await client.get(path, params=params)
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                if attempt == 2 or (exc.response.status_code != 429 and exc.response.status_code < 500):
                    raise
            except httpx.TransportError:
                if attempt == 2:
                    raise
            logging.getLogger("xiaosu.tools").warning("tool_retry name=%s attempt=%s", name, attempt + 1)
            await asyncio.sleep(0.5 * (2 ** attempt))
    if name == "get_attendance":
        return {"records": data, "days_with_check_in": len({row["date"] for row in data}), "definition": "有打卡记录的日期去重，不等同正常出勤"}
    if name == "get_orders":
        return {"records": data, "order_count": len(data), "net_amount_fen": sum(row["amount_fen"] for row in data if row["status"] == "paid"), "definition": "订单数量包含退款单；净额排除退款及取消订单"}
    return {"employee": data}
