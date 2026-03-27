export interface RuntimeConversationMessage {
  role: string;
  content: unknown;
  [key: string]: unknown;
}

export interface RuntimeConversation {
  id: string;
  name: string;
  session_id: string;
  user_id: string;
  channel: string;
  meta: Record<string, unknown>;
  messages: RuntimeConversationMessage[];
}
