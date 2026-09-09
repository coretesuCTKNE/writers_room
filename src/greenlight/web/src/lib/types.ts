export interface Script {
  id: string;
  title: string;
  author: string;
  draft: number;
  genre: string;
  created_at: string;
}

export interface Branch {
  branch_id: string;
  name: string;
  head_version_id: string;
  created_at: string;
}

export interface SessionState {
  loaded: boolean;
  scriptId: string;
  branchId: string;
  versionId: string;
  title: string;
  branches: Branch[];
}

export interface CoverageData {
  coverage_id?: string;
  script_id?: string;
  title?: string;
  verdict?: string;
  logline?: string;
  synopsis?: string;
  comments?: Record<string, string>;
  analyst_notes?: string;
  source?: string;
  created_at?: string;
}

export interface VersionMeta {
  version_id: string;
  branch_id: string;
  parent_version_id: string;
  message: string;
  author: string;
  created_at: string;
}

export interface Scene {
  num: number;
  heading: string;
  text: string;
}

export interface EditEntry {
  edit_id: string;
  scene_id: string;
  source: string;
  before_md: string;
  after_md: string;
  created_at: string;
}

export interface TableReadTurn {
  speaker: string;
  text: string;
  duration_ms: number;
  audio_url: string | null;
}

export interface DictationSession {
  active: boolean;
  scriptId: string;
  sceneNumber: number;
  vocabularyCount: number;
  characters: string[];
  stoplistCollisions: string[];
  startedAt: number;
}

export interface DictationCommand {
  action: string;
  value: string;
  scope?: string;
}

export interface UndoEntry {
  start: number;
  length: number;
  snapshot: string;
}

export interface NormalizerStats {
  scenes: number;
  cues: number;
  dialogue_lines: number;
  action_blocks: number;
  elements: number;
}

export interface ScriptUploadResult {
  id: string;
  title: string;
  hash: string;
  char_count: number;
  source_format: string;
  normalized: boolean;
  confidence: number;
  warnings: string[];
  stats: NormalizerStats;
  loaded: {
    loaded: boolean;
    scene_count: number;
    branch_id: string;
    version_id: string;
  } | null;
}

export interface NormalizeRetryResult {
  script_id: string;
  version_id: string;
  normalized: boolean;
  unchanged: boolean;
  confidence: number;
  warnings: string[];
  stats: NormalizerStats;
  scene_count: number;
}

export interface LintIssue {
  line: number;
  severity: string;
  message: string;
}

export interface BeautifyResult {
  text: string;
  changed: boolean;
  confidence: number;
  stats: NormalizerStats;
  lint: LintIssue[];
}

export interface BibleFact {
  fact_id: string;
  script_id: string;
  character_id: string;
  category: string;
  claim: string;
  source_page: number;
}

export interface ScriptStats {
  script_id: string;
  scene_count: number;
  character_count: number;
  bible_fact_count: number;
  coverage_count: number;
  coverage_breakdown: Record<string, number>;
}

export interface CoverageHistoryEntry {
  verdict: string;
  logline: string;
  scores: string;
  created_at: string;
}

export interface AgentRun {
  run_id: string;
  agent: string;
  script_id: string;
  scene_id: string;
  status: string;
  prompt: string;
  result: unknown;
  elapsed_s: number;
  created_at: string;
}

export type GoalMetric = 'words' | 'pages' | 'scenes';

export interface WritingGoal {
  goal_id: string;
  metric: GoalMetric;
  target: number;
  deadline: string | null;
  note: string;
  created_at: string;
  current: number;
  pct: number;
  remaining: number;
  days_left: number | null;
}

export interface CommitEntry {
  created_at: string;
  word_count: number;
  page_count: number;
  message: string;
}

export interface SceneStat {
  scene_number: number;
  heading: string;
  setting: string;
  time_of_day: string;
  dialogue_words: number;
  action_words: number;
  characters: string[];
}

export interface AgentRunSummary {
  run_id: string;
  agent: string;
  status: string;
  elapsed_s: number;
  created_at: string;
}

export interface StoryOpsPayload {
  script_id: string;
  summary: ScriptStats;
  goals: WritingGoal[];
  commit_history: CommitEntry[];
  scene_stats: SceneStat[];
  coverage_history: CoverageHistoryEntry[];
  agent_runs: AgentRunSummary[];
}
