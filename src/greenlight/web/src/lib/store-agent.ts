import { create } from 'zustand';

export type AgentStatusValue = 'idle' | 'running' | 'completed' | 'error';

interface AgentStatus {
  name: string;
  status: AgentStatusValue;
  lastEvent?: string;
}

interface AgentState {
  agents: Record<string, AgentStatus>;
  updateAgent: (name: string, status: Partial<AgentStatus>) => void;
  resetAgents: () => void;
}

const INITIAL_AGENTS = {
  showrunner: { name: 'showrunner', status: 'idle' as const },
  bible: { name: 'bible', status: 'idle' as const },
  analytics: { name: 'analytics', status: 'idle' as const },
  rewrite: { name: 'rewrite', status: 'idle' as const },
};

export const useAgentStore = create<AgentState>((set) => ({
  agents: INITIAL_AGENTS,
  updateAgent: (name, status) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [name]: { ...state.agents[name], ...status },
      },
    })),
  resetAgents: () => set({ agents: INITIAL_AGENTS }),
}));
