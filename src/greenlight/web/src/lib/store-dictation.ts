import { create } from 'zustand';
import { getAuthToken } from './firebase';
import type { DictationSession, UndoEntry } from './types';

interface DictationStore {
  session: DictationSession | null;
  interimText: string;
  insertHistory: UndoEntry[];
  targetCharacter: string | null;
  ws: WebSocket | null;
  audioCtx: AudioContext | null;
  micStream: MediaStream | null;
  workletNode: AudioWorkletNode | null;
  vuMeter: number;
  sessionTimerRef: ReturnType<typeof setInterval> | null;
  remainingSeconds: number;

  startDictation: (scriptId: string, sceneNumber: number, sceneText?: string) => Promise<void>;
  stopDictation: () => void;
  pushUndoEntry: (entry: UndoEntry) => void;
  popUndoEntry: () => UndoEntry | undefined;
  setTargetCharacter: (name: string | null) => void;
}

const MAX_UNDO_HISTORY = 50;

async function openMicPipeline() {
  let stream: MediaStream | null = null;
  let audioCtx: AudioContext | null = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
    });

    audioCtx = new AudioContext({ sampleRate: 16000 });
    await audioCtx.resume();

    // Load AudioWorklet (served from public/ so dev + prod builds resolve it)
    await audioCtx.audioWorklet.addModule('/audio-processor.js');
    const source = audioCtx.createMediaStreamSource(stream);
    const workletNode = new AudioWorkletNode(audioCtx, 'audio-processor');
    // Worklet must be connected downstream (silent gain) or process() never runs
    const silentGain = audioCtx.createGain();
    silentGain.gain.value = 0;
    workletNode.connect(silentGain);
    silentGain.connect(audioCtx.destination);
    source.connect(workletNode);

    return { stream, audioCtx, workletNode };
  } catch (err) {
    stream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close().catch(() => undefined);
    throw err;
  }
}

function micErrorMessage(err: unknown): Error {
  if (err instanceof DOMException && err.name === 'NotAllowedError') {
    return new Error('Microphone permission denied — enable mic access in your browser');
  }
  return err instanceof Error ? err : new Error('Dictation setup failed');
}

export const useDictationStore = create<DictationStore>((set, get) => ({
  session: null,
  interimText: '',
  insertHistory: [],
  targetCharacter: null,
  ws: null,
  audioCtx: null,
  micStream: null,
  workletNode: null,
  vuMeter: 0,
  sessionTimerRef: null,
  remainingSeconds: 0,

  startDictation: async (scriptId: string, sceneNumber: number, sceneText?: string) => {
    const state = get();
    if (state.session?.active) return;

    // Open WebSocket
    // Firebase Hosting rewrites do not proxy WebSockets — prod builds bake
    // VITE_WS_BASE (direct Cloud Run origin). Dev falls back to :8000 direct.
    const wsBase = import.meta.env.VITE_WS_BASE as string | undefined;
    const token = await getAuthToken();
    const auth = token ? `?token=${encodeURIComponent(token)}` : '';
    let wsUrl: string;
    if (wsBase) {
      wsUrl = `${wsBase}/api/ws/dictation${auth}`;
    } else {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = window.location.hostname;
      // In dev mode, WS goes to :8000 (FastAPI), not :5173 (Vite); empty port
      // (default 443/80) must not emit a trailing colon.
      const wsPort = window.location.port === '5173' ? '8000' : window.location.port;
      wsUrl = `${wsProtocol}//${wsHost}${wsPort ? `:${wsPort}` : ''}/api/ws/dictation${auth}`;
    }
    const ws = new WebSocket(wsUrl);

    ws.binaryType = 'arraybuffer';

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            type: 'start',
            script_id: scriptId,
            scene_number: sceneNumber,
            scene_text: sceneText ?? '',
          }),
        );
        resolve();
      };
      ws.onerror = () => reject(new Error('WebSocket connection failed'));
    });

    // Wait for 'started' message
    const started = await new Promise<Record<string, unknown>>((resolve, reject) => {
      const timeout = setTimeout(() => {
        ws.close();
        reject(new Error('Timeout waiting for started'));
      }, 5000);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'started') {
            clearTimeout(timeout);
            resolve(data);
          } else if (data.type === 'error') {
            clearTimeout(timeout);
            ws.close();
            reject(new Error(data.message));
          }
        } catch {
          // ignore non-JSON
        }
      };
    });

    let pipeline: Awaited<ReturnType<typeof openMicPipeline>>;
    try {
      pipeline = await openMicPipeline();
    } catch (err) {
      ws.close();
      throw micErrorMessage(err);
    }
    const { stream, audioCtx, workletNode } = pipeline;

    // Client-side VAD: track RMS silence → send audio_stream_end for
    // zero-latency finalization (hybrid VAD, plan decision #3)
    let silentFrames = 0;
    let vadArmed = true;
    const VAD_SILENCE_FRAMES = 8; // 8 × 100ms = 800ms
    const VAD_RMS_THRESHOLD = 0.012;

    workletNode.port.onmessage = (e: MessageEvent) => {
      if (e.data.type === 'frame') {
        const rms = e.data.rms;
        if (rms < VAD_RMS_THRESHOLD) {
          silentFrames += 1;
          if (vadArmed && silentFrames >= VAD_SILENCE_FRAMES) {
            vadArmed = false;
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'audio_stream_end' }));
            }
          }
        } else {
          silentFrames = 0;
          vadArmed = true;
        }
        // Send binary audio to server
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(e.data.pcm);
        }
        // Update VU meter
        set({ vuMeter: rms });
      }
    };

    // Tell worklet to start
    workletNode.port.postMessage({ type: 'start' });

    // Message handler
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'transcript':
            if (data.is_final) {
              set({ interimText: '' });
            } else {
              set({ interimText: data.text });
            }
            // Forward both to the overlay/page via custom event
            window.dispatchEvent(new CustomEvent('dictation-message', { detail: data }));
            break;

          case 'command':
            window.dispatchEvent(new CustomEvent('dictation-message', { detail: data }));
            break;

          case 'session_warn':
            set({ remainingSeconds: data.remaining_seconds });
            break;

          case 'session_expired':
            get().stopDictation();
            break;
        }
      } catch {
        // ignore
      }
    };

    // Session timer (countdown)
    const maxSeconds = 600; // 10 min
    const timerRef = setInterval(() => {
      const s = get();
      if (s.session?.active) {
        const elapsed = Math.floor((Date.now() - s.session.startedAt) / 1000);
        set({ remainingSeconds: Math.max(0, maxSeconds - elapsed) });
      }
    }, 1000);

    set({
      session: {
        active: true,
        scriptId,
        sceneNumber,
        vocabularyCount: started.vocabulary_count as number,
        characters: started.characters as string[],
        stoplistCollisions: (started.stoplist_collisions as string[]) ?? [],
        startedAt: Date.now(),
      },
      ws,
      audioCtx,
      micStream: stream,
      workletNode,
      sessionTimerRef: timerRef,
      remainingSeconds: maxSeconds,
    });
  },

  stopDictation: () => {
    const state = get();

    // Send stop to server
    if (state.ws?.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'stop' }));
    }

    // Stop worklet
    state.workletNode?.port.postMessage({ type: 'stop' });

    // Stop mic
    state.micStream?.getTracks().forEach((t) => t.stop());

    // Close audio context
    state.audioCtx?.close();

    // Close WS
    state.ws?.close();

    // Clear timer
    if (state.sessionTimerRef) clearInterval(state.sessionTimerRef);

    set({
      session: null,
      interimText: '',
      targetCharacter: null,
      ws: null,
      audioCtx: null,
      micStream: null,
      workletNode: null,
      vuMeter: 0,
      sessionTimerRef: null,
      remainingSeconds: 0,
    });
  },

  pushUndoEntry: (entry: UndoEntry) => {
    set((s) => ({
      insertHistory: [...s.insertHistory.slice(-MAX_UNDO_HISTORY + 1), entry],
    }));
  },

  popUndoEntry: () => {
    const state = get();
    const last = state.insertHistory[state.insertHistory.length - 1];
    if (last) {
      set({ insertHistory: state.insertHistory.slice(0, -1) });
    }
    return last;
  },

  setTargetCharacter: (name: string | null) => {
    set({ targetCharacter: name });
  },
}));
