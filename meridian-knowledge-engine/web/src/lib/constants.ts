export const CLIENT_DESKS = [
  { value: 'ALL', label: 'All Clients' },
  { value: 'Arvana Infra', label: 'Arvana Infra Projects' },
  { value: 'Arvana Pharma', label: 'Arvana Pharma' },
  { value: 'Arvana Retail', label: 'Arvana Retail' },
] as const;

export const EXECUTION_LANES = [
  { value: 'COMPUTABLE', label: 'Computable (Calculators)', color: 'bg-blue-100 text-blue-700' },
  { value: 'LOOKUP', label: 'Lookup (Retrieval)', color: 'bg-green-100 text-green-700' },
  { value: 'JUDGMENT', label: 'Judgment/Tacit', color: 'bg-purple-100 text-purple-700' },
  { value: 'ESCALATED', label: 'Escalated', color: 'bg-red-100 text-red-700' },
  { value: 'REFUSED', label: 'Refused', color: 'bg-gray-100 text-gray-700' },
] as const;

export const STATUS_BADGES = {
  PASS: 'badge-success',
  PRICE_VAR: 'badge-warning',
  IRN_MISSING: 'badge-error',
  TDS_SECTION_UNCLEAR: 'badge-warning',
  ABSTAIN: 'badge-info',
  ESCALATED: 'badge-error',
  REFUSED: 'badge-info',
  SUCCESS: 'badge-success',
  ERROR: 'badge-error',
  SYSTEM: 'badge-info',
  READY: 'badge-info',
} as const;

export const SOURCE_TYPES = [
  'client_memo',
  'sop_v4',
  'desk_instruction',
  'expert_interview',
  'approved_practice',
  'sop_v3',
  'faq_2023',
  'training_video_old',
  'meeting',
  'email',
  'chat',
] as const;

export const AUTHORITY_RANKS = {
  1: { label: 'Client Memo', color: 'bg-red-100 text-red-700' },
  2: { label: 'SOP v4.0 / DI', color: 'bg-blue-100 text-blue-700' },
  3: { label: 'Tacit (Approved)', color: 'bg-purple-100 text-purple-700' },
  4: { label: 'Superseded', color: 'bg-gray-100 text-gray-700' },
  5: { label: 'Live Sources', color: 'bg-orange-100 text-orange-700' },
} as const;

export const CONFLICT_TYPES = [
  'direct_contradiction',
  'parameter_drift',
  'scope_overlap',
  'authority_clash',
] as const;

export const CONFLICT_SEVERITIES = {
  critical: 'badge-error',
  high: 'badge-warning',
  medium: 'badge-info',
  low: 'badge-success',
} as const;

export const JOB_TYPES = [
  'ingest',
  'extract',
  'conflict_scan',
  'sop_sync',
  'notification',
  'replay',
] as const;

export const JOB_STATUSES = {
  queued: 'badge-info',
  running: 'badge-warning',
  completed: 'badge-success',
  failed: 'badge-error',
  retrying: 'badge-warning',
} as const;

export const ROUTES = {
  TDS_SECTIONS: ['194C', '194J', '194I', '194Q', 'TDS_SECTION_UNCLEAR'] as const,
  MSME_CATEGORIES: ['MICRO', 'SMALL', 'MEDIUM', 'NONE'] as const,
  AATO_BANDS: ['ABOVE_5CR', 'BELOW_5CR'] as const,
  PAYMENT_RUN_DAYS: [1, 4] as const, // Tuesday=1, Friday=4
} as const;