export interface TimeRange {
  start: number; // POSIX seconds
  end: number;
}

export interface StepInfo {
  name: string;
  module: string | null;
  startedAt: number;
  finishedAt: number;
  status?: string;
}

export interface ChannelInfo {
  type: 'timeseries' | 'text' | 'event';
  file: string;
  sampleCount: number;
  minT: number | null;
  maxT: number | null;
  unit?: string;
}

export interface TelemetryManifest {
  version: number;
  runId: string;
  startedAt: number | null;
  finishedAt: number | null;
  totalSamples: number;
  channels: Record<string, ChannelInfo>;
  steps: StepInfo[];
}
