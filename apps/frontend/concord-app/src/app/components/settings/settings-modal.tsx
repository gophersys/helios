import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useAuth } from '../../auth-provider';
import { settingsSections } from './settings-sections';

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();

  const visibleSections = useMemo(
    () =>
      settingsSections.filter((s) => {
        if (!s.requiredRole) return true;
        if (!user) return false;
        if (s.requiredRole === 'ADMIN') return user.role === 'ADMIN';
        if (s.requiredRole === 'OPERATOR')
          return user.role === 'ADMIN' || user.role === 'OPERATOR';
        return false;
      }),
    [user],
  );

  const [activeId, setActiveId] = useState(visibleSections[0]?.id ?? '');

  const activeSection = visibleSections.find((s) => s.id === activeId);
  const ActiveComponent = activeSection?.component;

  // Lock body scroll while open
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return createPortal(
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-50 bg-overlay animate-overlay-in"
        onClick={onClose}
      />

      {/* Centered container */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="pointer-events-auto flex w-full max-w-[900px] h-full max-h-[680px] rounded-xl border border-border bg-surface-0 shadow-xl animate-modal-in"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Left nav */}
          <div className="flex w-56 shrink-0 flex-col rounded-l-xl border-r border-border bg-surface-1">
            <div className="px-5 pt-5 pb-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Settings
              </h2>
            </div>
            <nav className="flex-1 space-y-0.5 px-3 pb-3">
              {visibleSections.map((section) => {
                const Icon = section.icon;
                const isActive = section.id === activeId;
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveId(section.id)}
                    className={[
                      'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors',
                      isActive
                        ? 'bg-accent-muted text-accent'
                        : 'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary',
                    ].join(' ')}
                  >
                    <Icon size={16} strokeWidth={1.75} className="shrink-0" />
                    <span className="truncate">{section.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Right panel */}
          <div className="flex flex-1 flex-col min-w-0">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <h3 className="text-sm font-semibold text-text-primary">
                {activeSection?.label}
              </h3>
              <button
                onClick={onClose}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
              >
                <X size={16} strokeWidth={1.75} />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {ActiveComponent && <ActiveComponent />}
            </div>
          </div>
        </div>
      </div>
    </>,
    document.body,
  );
}
