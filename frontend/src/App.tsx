import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Input, Layout, Menu, Popconfirm, Select, Space, Table, Tag, Typography, Upload } from 'antd';
import { api, type DocumentRow, type LogRow, type Settings } from './api';
import ChatPanel from './ChatPanel';

const { Title, Text, Paragraph } = Typography;

export default function App() {
  const [token, setToken] = useState('');
  const [draft, setDraft] = useState('');
  const [page, setPage] = useState('documents');
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [user, setUser] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [batchResult, setBatchResult] = useState('');
  const [batchFailed, setBatchFailed] = useState(false);
  const batchLock = useRef(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      if (page === 'documents') {
        const rows = await api<DocumentRow[]>('/documents', token);
        setDocuments(rows);
        setSelected(keys => keys.filter(key => rows.some(row => row.id === key)));
      }
      if (page === 'logs') setLogs(await api<LogRow[]>(`/conversations?user=${encodeURIComponent(user)}`, token));
      if (page === 'settings') setSettings(await api<Settings>('/settings', token));
      setError('');
    } catch (e) { setError(e instanceof Error ? e.message : '请求失败'); }
  }, [token, page, user]);
  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); return () => clearInterval(timer); }, [load]);
  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    try { await work(); await load(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  async function batch(items: { id: string; name: string; work: () => Promise<unknown> }[], verb: string) {
    if (batchLock.current || busy) return;
    batchLock.current = true;
    setBusy(true);
    setBatchFailed(false);
    const failed: string[] = [];
    const succeeded: string[] = [];
    try {
      for (const [index, item] of items.entries()) {
        setBatchResult(`正在${verb} ${index + 1}/${items.length}：${item.name}`);
        try { await item.work(); succeeded.push(item.id); }
        catch (e) { failed.push(`${item.name}：${e instanceof Error ? e.message : '请求失败'}`); }
      }
      if (verb === '删除') setSelected(keys => keys.filter(key => !succeeded.includes(key)));
      setBatchFailed(failed.length > 0);
      setBatchResult(`${verb}完成：成功 ${succeeded.length} 个，失败 ${failed.length} 个。${verb === '上传' ? '上传成功后仍需等待索引完成。' : ''}${failed.length ? '\n' + failed.join('\n') : ''}`);
      await load();
    } finally { setBusy(false); batchLock.current = false; }
  }
  if (!token) return <main className="login"><Tag color="green">XIAOSU / ADMIN</Tag><Title>小苏管理后台</Title><Paragraph>知识有出处，问答可追溯。</Paragraph><Card><Space direction="vertical" style={{ width: '100%' }}><Text>输入管理员访问口令</Text><Input.Password value={draft} onChange={e => setDraft(e.target.value)} onPressEnter={() => setToken(draft)} /><Button type="primary" disabled={!draft} onClick={() => { setToken(draft); setDraft(''); }}>进入后台</Button><Text type="secondary">口令仅保存在当前页面内存中，刷新后需重新输入。</Text></Space></Card></main>;
  return <Layout className="shell"><Layout.Sider theme="light" width={220}><div className="brand">小苏<span>企业知识与问答</span></div><Menu selectedKeys={[page]} onClick={e => setPage(e.key)} items={[{ key: 'documents', label: '知识库文档' }, { key: 'logs', label: '对话记录' }, { key: 'settings', label: '基础设置' }, { key: 'chat', label: '助手对话' }]} /><Button className="logout" onClick={() => setToken('')}>退出</Button></Layout.Sider><Layout.Content className="content"><header><div><Text type="secondary">WORKSPACE / 小苏</Text><Title level={2}>{({ documents: '知识库文档', logs: '对话记录', settings: '基础设置', chat: '助手对话' } as Record<string, string>)[page]}</Title></div><Tag>本地开发</Tag></header>{error && <Alert type="error" showIcon message={error} closable onClose={() => setError('')} />}
    {page === 'documents' && <><Paragraph type="secondary">上传制度与业务文档。索引完成后参与问答，同名文件自动更新。</Paragraph><Card><Space wrap style={{ marginBottom: 20 }}><Upload multiple disabled={busy} showUploadList={false} accept=".md,.txt,.pdf,.docx" beforeUpload={(file, files) => {
        if (file.uid === files[0].uid) void batch(files.map(item => ({ id: item.uid, name: item.name, work: () => { const data = new FormData(); data.append('file', item); return api('/documents', token, { method: 'POST', body: data }); } })), '上传');
        return false;
      }}><Button type="primary" disabled={busy}>批量上传文档</Button></Upload><Popconfirm title={`确定删除选中的 ${selected.length} 个文档？删除后不再参与问答。`} disabled={busy || !selected.length} onConfirm={() => batch(documents.filter(row => selected.includes(row.id)).map(row => ({ id: row.id, name: row.name, work: () => api(`/documents/${row.id}`, token, { method: 'DELETE' }) })), '删除')}><Button danger disabled={busy || !selected.length}>批量删除（{selected.length}）</Button></Popconfirm><Button disabled={busy} onClick={() => void load()}>刷新状态</Button><Text type="secondary">MD / TXT / PDF / DOCX</Text></Space>{batchResult && <Alert style={{ marginBottom: 16, whiteSpace: 'pre-wrap' }} type={batchFailed ? 'warning' : busy ? 'info' : 'success'} message={batchResult} showIcon />}<Table rowSelection={{ selectedRowKeys: selected, onChange: keys => setSelected(keys.map(String)), getCheckboxProps: () => ({ disabled: busy }) }} rowKey="id" dataSource={documents} columns={[
      { title: '文档', dataIndex: 'name' }, { title: '索引状态', render: (_, row: DocumentRow) => <Tag color={row.status === 'indexed' ? 'green' : row.status === 'failed' ? 'red' : 'gold'}>{row.status}</Tag> },
      { title: '说明', render: (_, row: DocumentRow) => <Text type="secondary">{row.error || (row.needs_reindex ? 'Embedding 已切换，请重建索引' : row.active_version ? '已有可用版本' : '等待首次索引')}</Text> },
      { title: '操作', render: (_, row: DocumentRow) => <Space>{(row.status === 'failed' || row.status === 'indexed') && <Button disabled={busy} size="small" onClick={() => void action(() => api(`/documents/${row.id}/retry`, token, { method: 'POST' }))}>{row.status === 'failed' ? '重试' : '重建索引'}</Button>}<Popconfirm disabled={busy} title="删除后该文档不再参与问答，确定删除？" onConfirm={() => action(() => api(`/documents/${row.id}`, token, { method: 'DELETE' }))}><Button disabled={busy} danger size="small">删除</Button></Popconfirm></Space> },
    ]} /></Card></>}
    {page === 'logs' && <Card><Input.Search placeholder="按用户 ID 筛选" allowClear onSearch={setUser} style={{ maxWidth: 320, marginBottom: 20 }} /><Table rowKey="id" dataSource={logs} columns={[{ title: '时间', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString() }, { title: '用户', dataIndex: 'user' }, { title: '问题', dataIndex: 'question', ellipsis: true }, { title: '状态', dataIndex: 'status' }, { title: 'Token', render: (_, row: LogRow) => row.usage?.total_tokens ?? '未知' }]} expandable={{ expandedRowRender: row => <><Paragraph style={{ whiteSpace: 'pre-wrap' }}>{row.answer || '尚未生成回答'}</Paragraph><Text>渠道：{row.platform} / 投递：{row.delivery} / 耗时：{row.latency_ms ?? '未知'} ms</Text>{row.error && <Alert type="error" message={row.error} />}<pre>{JSON.stringify(row.tool_calls, null, 2)}</pre>{row.citations.map(c => <Paragraph key={c.id}><a href={c.url} target="_blank" rel="noreferrer">{c.file} · {c.location}</a></Paragraph>)}</> }} /></Card>}
    {page === 'settings' && settings && <Card><Space direction="vertical" size="large" style={{ width: '100%' }}><Alert type="info" message={settings.verification} /><Text>模型配置：{settings.model_configured ? '已填写（未验证）' : '未配置'}</Text><Text>向量模型：{settings.embedding_configured ? `已配置：${settings.embedding_model}（待真实验证）` : '未配置，请填写 EMBEDDING_API_KEY / BASE_URL / MODEL'}</Text><Space><Text>对话模型</Text><Select style={{ minWidth: 240 }} value={settings.model || undefined} options={settings.allowed_models.map(name => ({ label: name, value: name }))} onChange={model => void action(() => api('/settings', token, { method: 'PATCH', body: JSON.stringify({ model }) }))} placeholder="在服务器配置允许模型" /></Space><Text type="secondary">支持 Web 与钉钉；钉钉需配置应用凭据，流式回复还需配置 AI 卡片模板。</Text></Space></Card>}
    {page === 'chat' && <ChatPanel token={token} />}
  </Layout.Content></Layout>;
}

