export interface PowerSample {
  t: number;   // POSIX seconds
  mA: number;
  mV: number;
}

export interface JoulescopeSample {
  t: number;   // POSIX seconds
  uA: number;  // microamps (Joulescope nanoamp resolution, displayed as µA)
  mV: number;
  nA?: number; // raw nanoamp value
}

export interface AccelSample {
  t: number;   // POSIX seconds
  x: number;
  y: number;
  z: number;
}
