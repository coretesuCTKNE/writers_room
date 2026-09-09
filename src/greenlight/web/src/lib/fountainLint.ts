import type { LintIssue } from './types';

// Mirrors greenlight/tools/fountain_normalizer.py heuristics (kept in sync manually).

const SCENE_HEADING_RE = /^(INT\.|EXT\.|INT\/EXT\.|I\/E\.|EST\.)\s+.+/i;
const CUE_EXT_RE = /^([A-Z][A-Z0-9 .'\-&]*?)\s*\(([A-Z .'\-]+)\)\s*$/;
const CUE_PLAIN_RE = /^[A-Z][A-Z0-9 .'\-&]*$/;
const PAREN_RE = /^\(.*\)$/;
const STANDALONE_TRANSITIONS = new Set(['FADE IN:', 'FADE IN', 'FADE OUT.', 'FADE OUT', 'THE END']);
const ACTION_VERBS =
  'kiss|kisses|kissing|nod|nods|nodded|smile|smiles|smiled|laugh|laughs|laughed|' +
  'stare|stares|stared|turn|turns|turned|walk|walks|walked|leave|leaves|left|' +
  'stand|stands|stood|sit|sits|sat|look|looks|looked|reach|reaches|reached|' +
  'grab|grabs|grabbed|hug|hugs|hugged|pause|pauses|paused|react|reacts|reacted|' +
  'sigh|sighs|sighed|gulp|gulps|gulped|cringe|cringes|cringed|glance|glances|' +
  'glanced|cross|crosses|crossed|lean|leans|leaned|rise|rises|rose|fall|falls|' +
  'fell|break|breaks|broke|erupt|erupts|erupted|exchange|exchanges|exchanged|' +
  'share|shares|shared|grip|grips|gripped|touch|touches|touched|exit|exits|' +
  'exited|enter|enters|entered|pull|pulls|pulled|push|pushes|pushed|chuckle|' +
  'chuckles|chuckled|gasp|gasps|gasped|whisper|whispers|whispered|shout|shouts|' +
  'shouted|stagger|staggers|staggered|lunge|lunges|lunged|freeze|freezes|frozen|beat';
const DIALOGUE_EXIT_RE = new RegExp(`^(He|She|They|It|Both|Everyone)\\s+(?:${ACTION_VERBS})\\b.*[.!]$`);
const NAME_ACTION_RE = new RegExp(`^(?:${ACTION_VERBS})\\w*\\b`);

function endsDialogue(s: string, knownNames: string[]): boolean {
  if (!s || s.startsWith('"')) return false;
  if (DIALOGUE_EXIT_RE.test(s)) return true;
  if (!/[.!?]$/.test(s)) return false;
  const upper = s.toUpperCase();
  for (const name of knownNames) {
    const prefix = name.toUpperCase() + ' ';
    if (upper.startsWith(prefix) && NAME_ACTION_RE.test(s.slice(prefix.length))) return true;
  }
  return false;
}

function isCue(s: string): boolean {
  if (!s || s.length > 35 || /[.!?,]$/.test(s)) return false;
  const ext = CUE_EXT_RE.exec(s);
  const name = ext ? ext[1].trim() : CUE_PLAIN_RE.test(s) ? s : null;
  if (name === null || !/[A-Z]/.test(name)) return false;
  if (SCENE_HEADING_RE.test(name)) return false;
  if (name.toUpperCase().endsWith(' TO')) return false;
  if (name.split(/\s+/).length > 4) return false;
  return true;
}

export function lintFountain(text: string): LintIssue[] {
  const issues: LintIssue[] = [];
  const lines = text.split('\n');
  if (!lines.some((l) => SCENE_HEADING_RE.test(l.trim()))) {
    issues.push({ line: 1, severity: 'warn', message: 'No scene headings in document' });
  }

  let block: { line: number; s: string }[] = [];
  const cueNames: string[] = [];

  const checkBlock = () => {
    if (block.length === 0) return;
    const [first] = block;
    if (SCENE_HEADING_RE.test(first.s) && first.s !== first.s.toUpperCase()) {
      issues.push({ line: first.line, severity: 'warn', message: 'Scene heading should be ALL CAPS' });
    }
    if (isCue(first.s) && !STANDALONE_TRANSITIONS.has(first.s.toUpperCase())) {
      const name = (CUE_EXT_RE.exec(first.s)?.[1] || first.s).trim();
      if (!cueNames.includes(name)) cueNames.push(name);
      if (block.length === 1) {
        issues.push({ line: first.line, severity: 'warn', message: 'Blank line between character cue and dialogue' });
      }
    }
    if (PAREN_RE.test(first.s) && block.length === 1) {
      issues.push({ line: first.line, severity: 'warn', message: 'Blank line separates parenthetical from dialogue' });
    }
    if (/[a-z]/.test(first.s[0]) && !'#=>![.(@'.includes(first.s[0])) {
      issues.push({ line: first.line, severity: 'warn', message: 'Suspected wrapped paragraph — remove the blank line between blocks' });
    }
    for (const { line, s } of block.slice(1)) {
      if (SCENE_HEADING_RE.test(s)) {
        issues.push({ line, severity: 'warn', message: 'Missing blank line before scene heading' });
      } else if (isCue(s)) {
        issues.push({ line, severity: 'warn', message: 'Character cue mid-block — add a blank line before it' });
      } else if (isCue(first.s) && endsDialogue(s, cueNames)) {
        issues.push({ line, severity: 'warn', message: 'Action line inside dialogue — add a blank line before it' });
      }
    }
  };

  lines.forEach((raw, i) => {
    const s = raw.trim();
    if (!s) {
      checkBlock();
      block = [];
      return;
    }
    block.push({ line: i + 1, s });
  });
  checkBlock();
  return issues;
}
