import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, onAuthStateChanged, signInAnonymously, type Auth } from 'firebase/auth';

// Public web config — safe to ship; only set in prod builds (.env.production),
// empty in dev (auth off, matching the backend FIREBASE_PROJECT_ID flag).
const apiKey = import.meta.env.VITE_FIREBASE_API_KEY as string | undefined;
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined;

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (apiKey && projectId) {
  app = initializeApp({
    apiKey,
    authDomain: (import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string) ?? `${projectId}.firebaseapp.com`,
    projectId,
    appId: (import.meta.env.VITE_FIREBASE_APP_ID as string) ?? '',
  });
  auth = getAuth(app);
}

export function firebaseEnabled(): boolean {
  return auth !== null;
}

let readyPromise: Promise<void> | null = null;

/** Sign in (once per page load); resolves immediately when auth is off. */
export function ensureAuth(): Promise<void> {
  if (!auth) return Promise.resolve();
  if (!readyPromise) {
    readyPromise = new Promise<void>((resolve, reject) => {
      onAuthStateChanged(auth!, (user) => {
        if (user) resolve();
      });
      signInAnonymously(auth!).catch((e) => {
        console.warn('anonymous sign-in failed', e);
        reject(e);
      });
    }).catch(() => {
      /* keep the app usable without auth; requests will just lack a token */
    });
  }
  return readyPromise;
}

/** Current Firebase ID token, or null when auth is off/unavailable. */
export async function getAuthToken(): Promise<string | null> {
  if (!auth) return null;
  const user = auth.currentUser;
  if (!user) return null;
  try {
    return await user.getIdToken();
  } catch {
    return null;
  }
}
