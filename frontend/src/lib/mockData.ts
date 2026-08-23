import { addHours, format } from "date-fns";

export interface EEGDataPoint {
  timestamp: number;
  timeStr: string;
  delta: number;
  theta: number;
  alpha: number;
  beta: number;
  seizureProb: number;
  artifact: number;
  aeegUpper: number;
  aeegLower: number;
  asymmetry: number; // -1 to 1
  spectrogram: number[]; // 40 bins
}

export const generateMockEEGData = (hours: number = 24): EEGDataPoint[] => {
  const data: EEGDataPoint[] = [];
  const startTime = new Date(2026, 3, 11, 8, 0, 0);
  const pointsPerHour = 60; // 1 point per minute for demo

  for (let i = 0; i < hours * pointsPerHour; i++) {
    const time = addHours(startTime, i / pointsPerHour);
    const t = i / (hours * pointsPerHour);
    
    // Simulate some physiological trends
    const baseDelta = 40 + Math.sin(t * 10) * 10 + Math.random() * 5;
    const baseAlpha = 10 + Math.cos(t * 8) * 5 + Math.random() * 2;
    
    // Generate a mock spectrogram (40 bins)
    const spectrogram = Array.from({ length: 40 }, (_, binIdx) => {
      const freq = binIdx * 0.5;
      // Higher power at lower frequencies (1/f noise)
      let power = (100 / (freq + 1)) * (1 + Math.random() * 0.5);
      // Add a peak for alpha (8-13 Hz)
      if (freq >= 8 && freq <= 13) {
        power += baseAlpha * Math.exp(-Math.pow(freq - 10, 2) / 2);
      }
      // Add a peak for delta (1-4 Hz)
      if (freq >= 1 && freq <= 4) {
        power += baseDelta * 0.5 * Math.exp(-Math.pow(freq - 2, 2) / 4);
      }
      return power;
    });

    data.push({
      timestamp: time.getTime(),
      timeStr: format(time, "HH:mm"),
      delta: Math.max(0, baseDelta),
      theta: Math.max(0, 20 + Math.sin(t * 15) * 8 + Math.random() * 4),
      alpha: Math.max(0, baseAlpha),
      beta: Math.max(0, 5 + Math.random() * 3),
      seizureProb: Math.random() > 0.95 ? Math.random() * 0.8 : Math.random() * 0.1,
      artifact: Math.random() > 0.9 ? Math.random() * 20 : Math.random() * 2,
      aeegUpper: 15 + Math.sin(t * 12) * 5 + Math.random() * 2,
      aeegLower: 5 + Math.sin(t * 12) * 3 + Math.random() * 1,
      asymmetry: Math.sin(t * 5) * 0.3 + (Math.random() - 0.5) * 0.1,
      spectrogram,
    });
  }
  return data;
};

export const mockPatient = {
  id: "PED-2046-1",
  age: "4.5 years",
  sex: "Male",
  diagnosis: "Post-Cardiac Arrest",
  roscTime: "2026-04-11 07:42",
  eegStart: "2026-04-11 08:15",
  location: "PICU Bed 12",
};
