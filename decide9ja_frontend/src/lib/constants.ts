import type { CSSProperties } from 'react';

export const COLORS = {
  red: '#D6453A',
  blue: '#164678',
  green: '#487A3A',
  yellow: '#EBC346',
  beige: '#D9D9CD',
  brown: '#9E7D45',
  black: '#050505',
  border: '#111111',
} as const;

export const CSS_VARS: CSSProperties = {
  '--c-red': COLORS.red,
  '--c-blue': COLORS.blue,
  '--c-green': COLORS.green,
  '--c-yellow': COLORS.yellow,
  '--c-beige': COLORS.beige,
  '--c-brown': COLORS.brown,
  '--c-black': COLORS.black,
  '--c-border': COLORS.border,
} as CSSProperties;

export const SEVERITY_CONFIG = {
  CRITICAL: { bg: COLORS.red, text: '#000', colorKey: 'red' as const },
  HIGH: { bg: COLORS.blue, text: '#fff', colorKey: 'blue' as const },
  MEDIUM: { bg: COLORS.yellow, text: '#000', colorKey: 'yellow' as const },
  LOW: { bg: COLORS.beige, text: '#000', colorKey: 'beige' as const },
} as const;

export type BlockColor = 'red' | 'blue' | 'green' | 'yellow' | 'beige' | 'brown';

export function severityToColor(severity: string): BlockColor {
  switch (severity) {
    case 'CRITICAL': return 'red';
    case 'HIGH': return 'blue';
    case 'MEDIUM': return 'yellow';
    default: return 'beige';
  }
}

export const NIGERIAN_STATES = [
  'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno',
  'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT', 'Gombe', 'Imo',
  'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi', 'Kwara', 'Lagos', 'Nasarawa',
  'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba',
  'Yobe', 'Zamfara',
];

export const ISSUE_DOMAINS = ['power', 'roads', 'security', 'water', 'health', 'education'];
