"use client";

import { FormEvent, useEffect, useState } from "react";
import type { components } from "@/lib/api.generated";

type Game = components["schemas"]["GameOut"];
type Conversation = components["schemas"]["ConversationOut"];
type RequestResult = components["schemas"]["RequestOut"];

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: body ? "POST" : "GET", cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  return response.json();
}

export default function Home() {
  const [games, setGames] = useState<Game[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [health, list] = await Promise.all([
          api<components["schemas"]["HealthOut"]>("/health"),
          api<components["schemas"]["GameList"]>("/games"),
        ]);
        if (!active) return;
        setReady(health.status === "ok"); setGames(list.items);
        const saved = localStorage.getItem("rule-u-conversation");
        if (saved) {
          try {
            const previous = await api<Conversation>(`/conversations/${saved}`);
            if (active) setConversation(previous);
          } catch { localStorage.removeItem("rule-u-conversation"); }
        }
      } catch { if (active) setError("서비스에 연결할 수 없습니다. API 실행 상태를 확인해 주세요."); }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, []);

  async function selectGame(game: Game) {
    setBusy(true); setError("");
    try {
      const detail = await api<components["schemas"]["GameDetail"]>(`/games/${game.id}`);
      if (!detail.editions.length) throw new Error("아직 선택할 수 있는 판본이 없습니다.");
      const created = await api<components["schemas"]["ConversationCreated"]>("/conversations", {
        game_id: game.id, edition_id: detail.editions[0].id, expansion_ids: [],
      });
      const next = await api<Conversation>(`/conversations/${created.conversation_id}`);
      localStorage.setItem("rule-u-conversation", next.id);
      setConversation(next);
    } catch (e) { setError(e instanceof Error ? e.message : "대화를 시작할 수 없습니다."); }
    finally { setBusy(false); }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!conversation || !input.trim() || busy) return;
    setBusy(true); setError("");
    try {
      const request = await api<components["schemas"]["RequestAccepted"]>(`/conversations/${conversation.id}/messages`, {
        message: input.trim(), mode: "qa", client_request_id: crypto.randomUUID(),
      });
      setInput("");
      for (let attempt = 0; attempt < 60; attempt++) {
        const result = await api<RequestResult>(`/requests/${request.request_id}`);
        if (result.status === "failed") throw new Error("응답 생성에 실패했습니다. 다시 질문해 주세요.");
        if (result.status === "completed") {
          setConversation(await api<Conversation>(`/conversations/${conversation.id}`));
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      throw new Error("응답이 지연되고 있습니다. 잠시 후 새로고침해 주세요.");
    } catch (e) { setError(e instanceof Error ? e.message : "질문을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }

  return <main>
    <header><a className="brand" href="/">Rule<span>_U</span><span className="brand-dot">✳</span></a><span className="tag">LOCAL PREVIEW</span></header>
    <section className="intro"><p className="eyebrow">LESS DOUBT, MORE PLAY</p><h1>규칙은 명확하게.<br />플레이는 즐겁게.</h1><p>보드게임의 궁금한 순간, 규칙과 근거를 함께 확인하세요.</p></section>
    <div className="notice"><span className="status-dot" />기반 기능을 확인하는 미리보기입니다. 현재는 테스트 응답만 제공하며 실제 규칙 판정은 준비 중입니다.</div>
    <div className="workspace">
      <aside className="games"><div className="section-title"><h2>게임 선택</h2><span>01</span></div><p className="muted">대화를 시작할 게임을 골라주세요.</p>
        {loading && <p role="status">게임을 불러오는 중…</p>}
        {!loading && games.length === 0 && <p className="empty">아직 등록된 게임이 없습니다.</p>}
        {games.map(game => <button className={`game-card ${conversation?.game_id === game.id ? "selected" : ""}`} key={game.id} disabled={busy} onClick={() => selectGame(game)}><span className="game-icon">⚄</span><strong>{game.name_ko}</strong><small>테스트 판본 · 규칙 준비 중</small><span className="arrow">↗</span></button>)}
        <div className="connection"><span className={`status-dot ${ready ? "online" : ""}`} />{ready ? "서비스 연결됨" : "서비스 연결 대기"}</div>
      </aside>
      <section className="chat"><div className="section-title"><h2>규칙 이야기</h2><span>02</span></div><div className="messages" aria-live="polite">
        {!conversation?.messages.length && <div className="welcome"><span className="welcome-icon">?</span><h3>어떤 규칙이 궁금한가요?</h3><p>{conversation ? "질문을 입력해 대화 저장을 확인해 보세요." : "왼쪽에서 게임을 선택하면 대화를 시작할 수 있어요."}</p></div>}
        {conversation?.messages.map(message => <article key={message.id} className={`message ${message.role}`}><small>{message.role === "user" ? "나" : "Rule_U"}</small><p>{message.content}</p></article>)}
        {busy && <p className="muted" role="status">처리하고 있습니다…</p>}
      </div><form onSubmit={send}><label className="sr-only" htmlFor="question">규칙 질문</label><input id="question" value={input} onChange={e => setInput(e.target.value)} maxLength={8000} placeholder="궁금한 규칙이나 상황을 입력하세요" disabled={!conversation || busy} /><button type="submit" disabled={!conversation || busy || !input.trim()} aria-label="질문 보내기">↑</button></form><p className="input-note">선택한 게임과 대화는 이 브라우저에 연결해 저장됩니다.</p></section>
      <aside className="sources"><div className="section-title"><h2>답변의 근거</h2><span>03</span></div><div className="source-placeholder"><span>▤</span><p>인용된 근거가 없습니다.</p><small>공식 규칙이 연결되면<br />문서와 페이지를 이곳에서 확인할 수 있어요.</small></div></aside>
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    <footer><span>Rule_U</span><p>함께 즐기는 테이블을 위한 규칙 도우미</p><span>PROJECT FOUNDATION · 01</span></footer>
  </main>;
}
