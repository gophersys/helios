import { Fragment, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { K8sEvent } from '../../types/models';

const POLL_INTERVAL = 10000;

export function EventsList() {
  const [namespace, setNamespace] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const url = namespace
    ? `/v2/system/events?limit=200&namespace=${namespace}`
    : '/v2/system/events?limit=200';
  const { data: events, loading, error } = useFetchData<K8sEvent[]>(url, { pollInterval: POLL_INTERVAL });

  const items = events ?? [];

  const toggleRow = (idx: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {items.length} event{items.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading events..." />
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-sm text-text-tertiary">
          No events found
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="w-8 px-2 py-2" />
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Type</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Reason</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Object</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Count</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Last Seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {items.map((e, idx) => {
                const isExpanded = expandedRows.has(idx);
                return (
                  <Fragment key={`${e.object}-${e.reason}-${e.type}-${e.lastSeen}-${e.message}`}>
                    <tr
                      className="cursor-pointer bg-surface-1 transition-colors hover:bg-surface-2"
                      onClick={() => toggleRow(idx)}
                    >
                      <td className="px-2 py-2 text-text-tertiary">
                        {isExpanded
                          ? <ChevronDown size={14} />
                          : <ChevronRight size={14} />
                        }
                      </td>
                      <td className="px-3 py-2"><StatusIndicator status={e.type} /></td>
                      <td className="px-3 py-2 font-medium text-text-primary">{e.reason}</td>
                      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{e.object}</td>
                      <td className="px-3 py-2 text-text-secondary">{e.count}</td>
                      <td className="px-3 py-2"><ResourceAge timestamp={e.lastSeen} /></td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-surface-2">
                        <td colSpan={6} className="px-4 py-3">
                          <div className="flex flex-wrap gap-6 text-xs">
                            <div className="min-w-0 flex-1">
                              <span className="text-text-tertiary">Message: </span>
                              <span className="text-text-primary">{e.message}</span>
                            </div>
                            <div className="shrink-0">
                              <span className="text-text-tertiary">Source: </span>
                              <span className="text-text-secondary">{e.source}</span>
                            </div>
                            {e.firstSeen && (
                              <div className="shrink-0">
                                <span className="text-text-tertiary">First seen: </span>
                                <span className="text-text-secondary"><ResourceAge timestamp={e.firstSeen} /></span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
