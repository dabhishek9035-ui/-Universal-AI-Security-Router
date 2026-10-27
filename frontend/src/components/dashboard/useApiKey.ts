'use client';
import { useEffect, useState } from 'react';

const KEY_STORAGE = 'ai_router.api_key';
export const DEFAULT_API_KEY = 'dev-default-key';

/** Tenant API key, persisted. The dev keys ship in app/policy/tenants.yaml. */
export function useApiKey(): [string, (k: string) => void] {
  const [key, setKey] = useState(DEFAULT_API_KEY);
  useEffect(() => {
    try {
      const stored = localStorage.getItem(KEY_STORAGE);
      if (stored) setKey(stored);
    } catch { /* private mode */ }
  }, []);
  const update = (k: string) => {
    setKey(k);
    try { localStorage.setItem(KEY_STORAGE, k); } catch { /* private mode */ }
  };
  return [key, update];
}
