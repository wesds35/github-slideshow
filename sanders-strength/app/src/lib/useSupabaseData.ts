import { useEffect, useRef, useState } from "react";

/**
 * A near drop-in replacement for dexie-react-hooks' useLiveQuery, sized for Supabase: it re-runs
 * `queryFn` whenever `deps` changes and returns `undefined` until the first result lands. Unlike
 * Dexie's version this does not subscribe to live table changes — after a mutation, call the
 * `refresh` function returned by useRefreshKey (bump a key in `deps`) to force a refetch.
 */
export function useSupabaseData<T>(queryFn: () => Promise<T>, deps: unknown[]): T | undefined {
  const [data, setData] = useState<T | undefined>(undefined);
  const queryFnRef = useRef(queryFn);
  queryFnRef.current = queryFn;

  useEffect(() => {
    let cancelled = false;
    queryFnRef.current().then((result) => {
      if (!cancelled) setData(result);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return data;
}

/** A small counter to include in a useSupabaseData deps array; call `bump()` after a mutation
 *  to force every query depending on it to refetch. */
export function useRefreshKey(): [number, () => void] {
  const [key, setKey] = useState(0);
  return [key, () => setKey((k) => k + 1)];
}
