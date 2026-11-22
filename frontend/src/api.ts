export interface Citation { id: string; file: string; location: string; text: string; url: string }
export interface DocumentRow { id: string; name: string; status: string; error: string | null; active_version: string | null; needs_reindex: boolean }
export interface LogRow {
  id: string; user: string; platform: string; question: string; answer: string;
  tool_calls: unknown[]; citations: Citation[]; usage: { total_tokens?: number } | null;
  status: string; delivery: string; error: string | null; latency_ms: number | null; created_at: string;
}
export interface Settings {
  model: string; allowed_models: string[]; model_configured: boolean; embedding_configured: boolean; embedding_model: string;
  im_configured: boolean; im: { status: string; last_received?: string }; im_streaming: boolean; verification: string;
}
export async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${token}`);
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : `请求失败 (${response.status})`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
export async function chat(token: string, text: string, channel: string, onEvent: (event: string, data: unknown) => void): Promise<void> {
  const response = await fetch('/api/chat/stream', { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ text, channel_id: channel }) });
  if (!response.ok || !response.body) throw new Error(`无法连接对话服务 (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = block.split('\n').find(line => line.startsWith('event:'))?.slice(6).trim() ?? 'message';
      const data = block.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}
