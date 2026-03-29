export interface RuntimeChatAgentProfile {
  agent_id: string;
  name: string;
  role_name?: string | null;
  current_focus_kind?: string | null;
  current_focus_id?: string | null;
  current_focus?: string | null;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
}
