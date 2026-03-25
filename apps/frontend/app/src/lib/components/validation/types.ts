export interface PowerSample {
  t: number;   // POSIX seconds
  mA: number;
  mV: number;
}

export interface AccelSample {
  t: number;   // POSIX seconds
  x: number;
  y: number;
  z: number;
}
