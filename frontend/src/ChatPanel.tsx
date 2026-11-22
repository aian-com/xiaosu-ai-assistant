import { useState } from 'react';
import { flushSync } from 'react-dom';
import { Alert, Button, Card, Input, Space, Typography } from 'antd';
import { chat, type Citation } from './api';

interface Turn { question: string; answer: string; citations: Citation[] }
function displayAnswer(turn: Turn) {
  return turn.answer.replace(/[ \t]*\[cite:([^\]]+)\]/g, '').replace(/\[cite:[^\]]*$/, '');
}
export default function ChatPanel({ token }: { token: string }) {
  const [channel, setChannel] = useState(() => crypto.randomUUID());
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  async function send() {
    if (!question.trim() || busy) return;
    const text = question.trim();
    setQuestion(''); setBusy(true);
    setTurns(rows => [...rows, { question: text, answer: '', citations: [] }]);
    try {
      await chat(token, text, channel, (event, data) => {
        if (event === 'status') setStatus(String(data));
        if (event === 'delta') flushSync(() => setTurns(rows => rows.map((row, i) => i === rows.length - 1 ? { ...row, answer: row.answer + String(data) } : row)));
        if (event === 'done' && typeof data === 'object' && data !== null && 'answer' in data && 'citations' in data) {
          const result = data as { answer: string; citations: Citation[] };
          setTurns(rows => rows.map((row, i) => i === rows.length - 1 ? { ...row, ...result } : row));
        }
        if (event === 'error') throw new Error(String(data));
      });
      setStatus('完成');
    } catch (e) { const message = e instanceof Error ? e.message : '连接失败'; setStatus(message); setTurns(rows => rows.map((row, i) => i === rows.length - 1 ? { ...row, answer: message, citations: [] } : row)); }
    finally { setBusy(false); }
  }
  return <Space direction="vertical" size="middle" style={{ width: '100%' }}><Alert type="info" message="本地助手入口。生成过程中为草稿，完成后以引用校验结果为准。" /><Button disabled={busy} onClick={() => { setChannel(crypto.randomUUID()); setTurns([]); }}>新建会话</Button>{turns.map((turn, i) => <Card key={i}><Typography.Text strong>{turn.question}</Typography.Text><Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginTop: 18 }}>{displayAnswer(turn) || '正在处理…'}</Typography.Paragraph>{turn.citations.map(c => <Typography.Paragraph key={c.id}>来源：<a href={c.url} target="_blank" rel="noreferrer">{c.file}</a></Typography.Paragraph>)}</Card>)}<Input.TextArea rows={3} value={question} onChange={e => setQuestion(e.target.value)} placeholder="例如：员工 001 是哪个部门的？" /><Space><Button type="primary" loading={busy} onClick={() => void send()}>发送</Button><Typography.Text type="secondary">{status}</Typography.Text></Space></Space>;
}

