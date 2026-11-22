"""End-to-end evaluation against a running Xiaosu server; never invent scores."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import time
import uuid
from datetime import datetime
import httpx
from app.config import get_settings


def cases():
    rows = []
    def add(key, question, patterns, tools, setup=None):
        rows.append(dict(id=key, question=question, patterns=patterns, tools=tools, setup=setup))
    people = [('001','张三','研发部'),('002','李四','财务部'),('003','王五','销售部'),('004','赵敏','人事部'),('005','陈晨','运营部'),('006','刘洋','研发部'),('007','周宁','客服部'),('008','吴桐','采购部'),('009','郑悦','市场部'),('010','孙浩','行政部')]
    for number, name, dept in people:
        add('employee-'+number, f'员工{number}叫什么，在哪个部门？', [name, dept], ['get_employee'])
    for number, days in [('001','5|五'),('002','4|四'),('003','3|三'),('005','5|五'),('006','4|四'),('007','2|两|二'),('008','5|五'),('009','1|一'),('010','5|五')]:
        add('attendance-'+number, f'员工{number}上周有几天打卡记录？请用阿拉伯数字回答天数。', [rf'(?:{days})\s*天'], ['current_time','get_attendance'])
    add('attendance-empty', '员工004上周有打卡记录吗？', ['没有|无.*记录|0\s*天|未.*记录'], ['current_time','get_attendance'])
    add('attendance-duplicate', '员工003上周有几条打卡记录、涉及几天？', ['(?:4|四)\s*条', '(?:3|三)\s*天'], ['current_time','get_attendance'])
    add('orders', '上周有多少订单？排除退款和取消后的净额是多少元？', ['(?:10|十)\s*(?:笔|个|条)', r'1,?064(?:\.0+)?\s*元'], ['current_time','get_orders'])
    add('missing-employee', '员工999在哪个部门？', ['不存在|未找到|没.*查到|查无|无法.*查'], ['get_employee'])
    add('sum', '请用计算工具求和：123.45、67.89、10。', [r'201\.34'], ['calculate'])
    add('count', '请用计数工具统计列表[8,8,3,2]的元素个数，重复元素也算。', ['4|四'], ['calculate'])
    add('followup', '他上周有几天打卡记录？请用阿拉伯数字回答。', [r'4\s*天'], ['current_time','get_attendance'], '员工002叫什么，在哪个部门？')
    return rows


def grade(case, result):
    answer = re.sub(r'[*`_]', '', result.get('answer', ''))
    missing = [p for p in case['patterns'] if not re.search(p, answer)]
    names = {c.get('name') for c in result.get('calls', [])}
    missing_tools = sorted(set(case['tools']) - names)
    answer_ok = result.get('done', False) and not result.get('error') and not missing
    tools_ok = not missing_tools
    return dict(passed=bool(answer_ok and tools_ok), answer_ok=bool(answer_ok), tools_ok=tools_ok,
                missing_patterns=missing, missing_tools=missing_tools)


async def ask(client, question, channel, user):
    result = dict(answer='', calls=[], done=False)
    event = ''
    async with client.stream('POST', '/api/chat/stream', json=dict(text=question, channel_id=channel, user_id=user)) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith('event:'):
                event = line[6:].strip()
            elif line.startswith('data:'):
                data = json.loads(line[5:])
                if event == 'tool':
                    result['calls'].append(data)
                elif event == 'done':
                    result.update(answer=data['answer'], done=True)
                elif event == 'error':
                    result['error'] = data
    if not result['done'] and not result.get('error'):
        result['error'] = '响应流未正常完成'
    return result


async def run(args):
    selected = cases()
    if args.limit:
        selected = selected[:args.limit]
    settings = get_settings()
    run_id = uuid.uuid4().hex
    results = []
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / ('evaluation-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + run_id[:6] + '.json')
    async with httpx.AsyncClient(base_url=args.url, headers={'Authorization': 'Bearer ' + settings.admin_secret.get_secret_value()}, timeout=180, trust_env=False) as client:
        check = await client.get('/api/settings')
        check.raise_for_status()
        model = check.json().get('model')
        for case in selected:
            start = time.monotonic()
            channel = run_id + '-' + case['id']
            try:
                if case['setup']:
                    setup = await ask(client, case['setup'], channel, 'eval-' + run_id)
                    if not setup['done'] or setup.get('error'):
                        raise ValueError('多轮前置问题失败')
                result = await ask(client, case['question'], channel, 'eval-' + run_id)
            except Exception as exc:
                # Do not persist request headers, URLs with credentials or exception bodies.
                result = dict(answer='', calls=[], done=False, error=type(exc).__name__)
            score = grade(case, result)
            results.append(dict(case=case, result=result, score=score, seconds=round(time.monotonic()-start, 2)))
            total = len(selected)
            passed = sum(r['score']['passed'] for r in results)
            report = dict(run_id=run_id, model=model, suite='mock-business-v1', total=total, completed=len(results),
                          passed=passed, accuracy=passed/total, answer_accuracy=sum(r['score']['answer_ok'] for r in results)/total,
                          tool_accuracy=sum(r['score']['tools_ok'] for r in results)/total,
                          errors=sum(bool(r['result'].get('error')) for r in results), results=results)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[{len(results)}/{total}] {case['id']}: {'PASS' if score['passed'] else 'FAIL'}", flush=True)
    print(f'综合通过率：{passed}/{total} = {passed/total:.2%}\n报告：{report_path.resolve()}')
    return 0 if passed == total else 1


def self_test():
    assert len(cases()) >= 20
    assert len({c['id'] for c in cases()}) == len(cases())
    case = cases()[0]
    good = dict(answer='张三，研发部', calls=[{'name':'get_employee'}], done=True)
    assert grade(case, good)['passed']
    assert not grade(case, {**good, 'answer':'李四，财务部'})['passed']
    assert not grade(case, {**good, 'calls':[]})['passed']
    assert not grade(case, {**good, 'done':False})['passed']
    assert not grade(case, {**good, 'error':'timeout'})['passed']
    print(f'评分器自检通过；共 {len(cases())} 条 case。此结果不是模型准确率。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='../logs/evaluations')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit 不能为负数')
    if args.self_test:
        self_test()
    else:
        try:
            raise SystemExit(asyncio.run(run(args)))
        except httpx.HTTPError as exc:
            print(f'评测未启动：无法访问或登录小苏服务（{type(exc).__name__}）。请先启动服务，并确认 .env 中的管理员口令与运行服务一致。未产生准确率。')
            raise SystemExit(2)
