import { create } from 'zustand';
import type { Script, SessionState } from './types';

interface ProjectStore {
  scripts: Script[];
  scriptsLoading: boolean;
  session: SessionState | null;
  sessionLoading: boolean;
  lastEditedScene: number | null;

  refreshSession: () => Promise<SessionState | null>;
  loadScripts: () => Promise<void>;
  loadScript: (scriptId: string, rawText?: string) => Promise<boolean>;
  unloadScript: () => Promise<void>;
  setActiveVersion: (branchId: string, versionId: string) => Promise<void>;
  markEditedScene: (sceneNumber: number) => void;
}

const EMPTY_SESSION: SessionState = {
  loaded: false,
  scriptId: '',
  branchId: '',
  versionId: '',
  title: '',
  branches: [],
};

async function fetchSession(): Promise<SessionState> {
  const res = await fetch('/api/session/active');
  if (!res.ok) return EMPTY_SESSION;
  const data = await res.json();
  if (!data.loaded) return EMPTY_SESSION;
  return {
    loaded: true,
    scriptId: data.script_id,
    branchId: data.branch_id,
    versionId: data.version_id,
    title: data.title ?? '',
    branches: data.branches ?? [],
  };
}

export const useProjectStore = create<ProjectStore>((set) => ({
  scripts: [],
  scriptsLoading: false,
  session: null,
  sessionLoading: false,
  lastEditedScene: null,

  refreshSession: async () => {
    set({ sessionLoading: true });
    try {
      const session = await fetchSession();
      set({ session });
      return session;
    } finally {
      set({ sessionLoading: false });
    }
  },

  loadScripts: async () => {
    set({ scriptsLoading: true });
    try {
      const res = await fetch('/api/scripts');
      const data = await res.json();
      set({ scripts: Array.isArray(data) ? data : [] });
    } catch (err) {
      console.error('Failed to load scripts:', err);
    } finally {
      set({ scriptsLoading: false });
    }
  },

  loadScript: async (scriptId, rawText) => {
    try {
      const body: Record<string, unknown> = {};
      if (rawText) body.raw_text = rawText;
      const res = await fetch(`/api/scripts/${scriptId}/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const session = await fetchSession();
      set({ session });
      return true;
    } catch (err) {
      console.error('Failed to load script:', err);
      return false;
    }
  },

  markEditedScene: (sceneNumber) => {
    set({ lastEditedScene: sceneNumber });
  },

  unloadScript: async () => {
    const s = useProjectStore.getState().session;
    if (!s?.scriptId) return;
    try {
      await fetch(`/api/scripts/${s.scriptId}/unload`, { method: 'POST' });
      set({ session: EMPTY_SESSION, lastEditedScene: null });
    } catch (err) {
      console.error('Failed to unload:', err);
    }
  },

  setActiveVersion: async (branchId, versionId) => {
    const s = useProjectStore.getState().session;
    if (!s?.scriptId) return;
    try {
      await fetch(`/api/scripts/${s.scriptId}/active`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch_id: branchId, version_id: versionId }),
      });
      set({
        session: {
          ...s,
          branchId,
          versionId,
          branches: s.branches.map((b) =>
            b.branch_id === branchId ? { ...b, head_version_id: versionId } : b,
          ),
        },
      });
    } catch (err) {
      console.error('Failed to set active version:', err);
    }
  },
}));
