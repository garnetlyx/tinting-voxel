/**
 * Live heavy-job queue state, shared between the API wrappers and the queue
 * banner. Framework-free on purpose: the wrappers are plain functions.
 */
export interface HeavyQueueEntry {
  /** Server job id (queued/running) — also the store key. */
  id: string;
  /** i18n key naming this job for the banner. */
  labelKey: string;
  /** 1-based queue position while queued; undefined once running. */
  position?: number;
  running: boolean;
  /** Ask the wrapper to abort (cancels the queued server job too). */
  cancel: () => void;
}

type Listener = () => void;

const listeners = new Set<Listener>();
let entries: HeavyQueueEntry[] = [];
let nextCallId = 0;

function emit(): void {
  for (const listener of listeners) listener();
}

export const heavyQueue = {
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  getSnapshot(): readonly HeavyQueueEntry[] {
    return entries;
  },

  add(entry: Omit<HeavyQueueEntry, 'id'> & { id?: string }): string {
    const id = entry.id ?? `call-${++nextCallId}`;
    entries = [...entries, { ...entry, id }];
    emit();
    return id;
  },

  update(id: string, patch: Partial<Pick<HeavyQueueEntry, 'position' | 'running'>>): void {
    if (!entries.some(entry => entry.id === id)) return;
    entries = entries.map(entry => (entry.id === id ? { ...entry, ...patch } : entry));
    emit();
  },

  remove(id: string): void {
    if (!entries.some(entry => entry.id === id)) return;
    entries = entries.filter(entry => entry.id !== id);
    emit();
  },
};
