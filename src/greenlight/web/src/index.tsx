import './styles/global.css';
import { App } from './App';
import { createRoot } from 'react-dom/client';

import { ensureAuth, firebaseEnabled } from './lib/firebase';
import { installFetchAuth } from './lib/fetchAuth';

// Attach the Firebase ID token to every same-origin /api fetch (54 call
// sites route through window.fetch — patching it once beats wrapping each).
installFetchAuth();

async function boot(): Promise<void> {
  if (firebaseEnabled()) {
    // Wait for the anonymous sign-in to settle so the first data fetches
    // already carry a Bearer token (401ing then retrying every fetch is
    // racy and leaves the UI on the empty state).
    try {
      await ensureAuth();
    } catch {
      // keep the app usable without auth; requests will lack a token
    }
  }
  createRoot(document.getElementById('root')!).render(<App />);
}

void boot();