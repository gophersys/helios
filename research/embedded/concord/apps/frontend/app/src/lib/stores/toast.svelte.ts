/**
 * Minimal toast/snackbar store.
 *
 * Entries auto-dismiss after `DEFAULT_DURATION_MS`. Mounted once at the
 * root layout via `<ToastContainer />`. Shows bottom-right, stacking
 * upwards as new toasts arrive.
 */

export type ToastKind = 'info' | 'success' | 'error';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const DEFAULT_DURATION_MS = 5000;

class ToastState {
  toasts = $state<Toast[]>([]);
  private nextId = 1;

  show(message: string, kind: ToastKind = 'info', durationMs = DEFAULT_DURATION_MS) {
    const id = this.nextId++;
    this.toasts.push({ id, kind, message });
    window.setTimeout(() => this.dismiss(id), durationMs);
  }

  success(message: string, durationMs?: number) {
    this.show(message, 'success', durationMs);
  }

  error(message: string, durationMs?: number) {
    this.show(message, 'error', durationMs);
  }

  dismiss(id: number) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
  }
}

export const toasts = new ToastState();
