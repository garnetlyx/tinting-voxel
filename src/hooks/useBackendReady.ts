/**
 * Polls /api/health until the backend responds successfully.
 * Returns { ready: boolean } — false while warming up, true once healthy.
 */
import { useEffect, useState } from 'react';

const POLL_INTERVAL_MS = 2_000;
const HEALTH_URL = '/api/health';

export function useBackendReady(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (ready) return;

    let cancelled = false;

    async function check() {
      try {
        const res = await fetch(HEALTH_URL, { method: 'GET' });
        if (res.ok && !cancelled) {
          setReady(true);
          return;
        }
      } catch {
        // backend not up yet — keep polling
      }
      if (!cancelled) {
        setTimeout(check, POLL_INTERVAL_MS);
      }
    }

    check();
    return () => { cancelled = true; };
  }, [ready]);

  return ready;
}
