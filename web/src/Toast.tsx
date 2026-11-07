import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

/** A short confirmation at the bottom of the screen, e.g. "Moved to Contacted · Undo". */
interface Toast {
  id: number;
  message: string;
  action?: { label: string; run: () => void };
}

type Show = (message: string, action?: Toast["action"]) => void;

const ToastContext = createContext<Show>(() => {});

/** Show a confirmation. Works anywhere under <ToastProvider>. */
export const useToast = () => useContext(ToastContext);

// Long enough to read and reach Undo, short enough not to pile up.
const SHOW_MS = 5000;
const SHOW_WITH_ACTION_MS = 8000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const nextId = useRef(1);

  // One at a time: a new confirmation replaces the last, so they never stack up.
  const show = useCallback<Show>((message, action) => {
    setToast({ id: nextId.current++, message, action });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.action ? SHOW_WITH_ACTION_MS : SHOW_MS);
    return () => clearTimeout(timer);
  }, [toast]);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {/* Always in the page so screen readers announce what gets put in it. */}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-30 flex justify-center px-4 sm:bottom-6 sm:justify-start sm:px-6"
      >
        {toast && (
          <div
            key={toast.id}
            className="toast-in pointer-events-auto flex max-w-md items-center gap-4 rounded-lg bg-stone-900 px-4 py-3 text-sm text-white shadow-lg shadow-stone-950/20 dark:bg-stone-100 dark:text-stone-900"
          >
            <span>{toast.message}</span>
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action!.run();
                  setToast(null);
                }}
                className="shrink-0 rounded font-semibold text-orange-300 underline-offset-2 hover:underline active:scale-[0.98] dark:text-accent"
              >
                {toast.action.label}
              </button>
            )}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}
