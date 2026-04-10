// Validation queue types

export type QueueEntryStatus = 'QUEUED' | 'ASSIGNED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface ValidationQueueEntry {
  id: string;
  buildRunId: string;
  stageConfigId: string | null;
  stage: number;
  priority: number;
  status: QueueEntryStatus;
  benchId: string | null;
  testRunId: string | null;
  reason: string | null;
  errorMessage: string | null;
  requestedAt: string;
  assignedAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
  // Populated relations
  buildRun?: {
    id: string;
    name: string | null;
    product: string;
    branch: string;
    status: string;
    stage: number | null;
  };
  bench?: {
    id: string;
    name: string;
    stationId: string;
    status: string;
  };
  stageConfig?: {
    id: string;
    name: string;
    stage: number;
  };
  testRun?: {
    id: string;
    type: 'VALIDATION' | 'MANUFACTURING';
    status: string;
  };
}

export interface QueueStats {
  total: number;
  byStatus: Record<QueueEntryStatus, number>;
  avgWaitSeconds: number | null;
}
