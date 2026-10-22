import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, ApiError, errorText, type Schema } from "./api";

type Pending = {
  message: string;
  mode: "qa" | "ruling";
  client_request_id: string;
};
type State = {
  hydrated: boolean;
  conversation: Schema["ConversationOut"] | null;
  detail: Schema["GameDetail"] | null;
  chatDetail: Schema["GameDetail"] | null;
  edition: string;
  expansions: string[];
  conversations: Record<string, string>;
  lastId: string | null;
  drafts: Record<string, string>;
  pending: Record<string, Pending>;
  request: Schema["RequestOut"] | null;
  source: Schema["SourceOut"] | null;
  mode: "qa" | "ruling";
  view: "games" | "chat";
  sourcesOpen: boolean;
  loading: boolean;
  sending: boolean;
  error: string;
  init: () => Promise<void>;
  selectGame: (id: string) => Promise<void>;
  start: () => Promise<void>;
  send: (retry?: boolean) => Promise<void>;
  refresh: (id: string) => Promise<void>;
};
export const scopeKey = (game: string, edition: string, expansions: string[]) =>
  JSON.stringify([game, edition, [...expansions].sort()]);
let selection = 0;
export const useStore = create<State>()(
  persist(
    (set, get) => ({
      hydrated: false,
      conversation: null,
      detail: null,
      chatDetail: null,
      edition: "",
      expansions: [],
      conversations: {},
      lastId: null,
      drafts: {},
      pending: {},
      request: null,
      source: null,
      mode: "qa",
      view: "games",
      sourcesOpen: false,
      loading: false,
      sending: false,
      error: "",
      init: async () => {
        await useStore.persist.rehydrate();
        const id = get().lastId ?? localStorage.getItem("rule-u-conversation");
        try {
          if (id) {
            const c = await api<Schema["ConversationOut"]>(
              `/conversations/${id}`,
            );
            const detail = await api<Schema["GameDetail"]>(
              `/games/${c.game_id}`,
            );
            set({
              conversation: c,
              detail,
              chatDetail: detail,
              edition: c.edition_id,
              expansions: c.expansion_ids,
              view: "games",
            });
            set((state) => ({
              lastId: id,
              conversations: {
                ...state.conversations,
                [scopeKey(c.game_id, c.edition_id, c.expansion_ids)]: id,
              },
            }));
            localStorage.removeItem("rule-u-conversation");
            await get().refresh(id);
          }
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            localStorage.removeItem("rule-u-conversation");
            set({
              lastId: null,
              conversations: {},
              pending: {},
              drafts: {},
              conversation: null,
              request: null,
            });
          }
          set({ error: errorText(error) });
        } finally {
          set({ hydrated: true });
        }
      },
      selectGame: async (id) => {
        const ticket = ++selection;
        set({ loading: true, error: "" });
        try {
          const detail = await api<Schema["GameDetail"]>(`/games/${id}`);
          if (ticket !== selection) return;
          set({
            detail,
            edition: detail.editions[0]?.id ?? "",
            expansions: [],
            loading: false,
          });
        } catch (error) {
          if (ticket === selection)
            set({ loading: false, error: errorText(error) });
        }
      },
      start: async () => {
        const { detail, edition, expansions } = get();
        if (!detail || !edition || get().loading) return;
        set({ loading: true, error: "" });
        const key = scopeKey(detail.id, edition, expansions);
        try {
          let id = get().conversations[key];
          let c: Schema["ConversationOut"] | undefined;
          if (id) {
            try {
              c = await api<Schema["ConversationOut"]>(`/conversations/${id}`);
            } catch (error) {
              if (!(error instanceof ApiError && error.status === 404))
                throw error;
            }
          }
          if (!c) {
            const created = await api<Schema["ConversationCreated"]>(
              "/conversations",
              {
                game_id: detail.id,
                edition_id: edition,
                expansion_ids: expansions,
              },
            );
            id = created.conversation_id;
            c = await api<Schema["ConversationOut"]>(`/conversations/${id}`);
          }
          set((s) => ({
            conversation: c!,
            chatDetail: detail,
            lastId: c!.id,
            conversations: { ...s.conversations, [key]: c!.id },
            request: null,
            source: null,
            sourcesOpen: false,
            view: "chat",
          }));
          await get().refresh(c.id);
        } catch (error) {
          set({ error: errorText(error) });
        } finally {
          set({ loading: false });
        }
      },
      refresh: async (id) => {
        const c = await api<Schema["ConversationOut"]>(`/conversations/${id}`);
        const rid = c.active_request_id ?? c.latest_request_id;
        const request = rid
          ? await api<Schema["RequestOut"]>(`/requests/${rid}`)
          : null;
        if (get().conversation?.id === id)
          set((s) => {
            const pending = { ...s.pending };
            if (
              request?.status === "completed" &&
              pending[id]?.client_request_id === c.latest_client_request_id
            )
              delete pending[id];
            return { conversation: c, request, pending };
          });
      },
      send: async (retry = false) => {
        const { conversation: c, mode, drafts, pending, request } = get();
        if (
          !c ||
          get().sending ||
          ["queued", "running"].includes(request?.status ?? "")
        )
          return;
        const last = [...c.messages].reverse().find((m) => m.role === "user");
        const old = pending[c.id];
        const message = retry ? (old?.message ?? last?.content) : drafts[c.id];
        if (!message?.trim()) return;
        const failedSubmission =
          request?.status === "failed" &&
          old?.client_request_id === c.latest_client_request_id;
        const body: Pending =
          old && !failedSubmission
            ? old
            : {
                message: message.trim(),
                mode: retry
                  ? (old?.mode ?? (last?.mode === "ruling" ? "ruling" : "qa"))
                  : mode,
                client_request_id: crypto.randomUUID(),
              };
        set((s) => ({
          sending: true,
          error: "",
          pending: { ...s.pending, [c.id]: body },
        }));
        try {
          await api<Schema["RequestAccepted"]>(
            `/conversations/${c.id}/messages`,
            body,
          );
          set((s) => ({ drafts: { ...s.drafts, [c.id]: "" } }));
          await get().refresh(c.id);
        } catch (error) {
          if (get().conversation?.id === c.id) set({ error: errorText(error) });
          if (error instanceof ApiError && error.status === 409)
            await get()
              .refresh(c.id)
              .catch(() => {});
        } finally {
          set({ sending: false });
        }
      },
    }),
    {
      name: "rule-u-workspace",
      skipHydration: true,
      partialize: (s) => ({
        conversations: s.conversations,
        lastId: s.lastId,
        drafts: s.drafts,
        pending: s.pending,
      }),
    },
  ),
);
