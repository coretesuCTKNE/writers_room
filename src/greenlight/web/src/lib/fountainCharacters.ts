const CHARACTER_CUE_RE = /^([A-Z][A-Z\s'.\-#\^]*?)(\(.*?\))?\s*$/;

export const NARRATOR = 'NARRATOR';

/**
 * Extract the ordered, de-duplicated list of dialogue speakers from a Fountain
 * scene. Mirrors the backend `parse_scene` character-collection rule
 * (tools/fountain_parser.py): a line is a new character cue when it matches
 * CHARACTER_CUE_RE, is all-caps, and is under 50 chars. Speakers appear only
 * after they have at least one dialogue line.
 *
 * When `includeNarrator` is true, appends NARRATOR (the actor voicing scene
 * headings + action paragraphs) to the character list so it can be assigned a
 * voice and toggled in the cast UI.
 */
export function parseFountainCharacters(
  text: string,
  includeNarrator = false,
): string[] {
  const lines = text.split(/\r?\n/);
  const characters: string[] = [];
  let currentSpeaker: string | null = null;
  let pendingDialogue = false;

  const flush = () => {
    if (currentSpeaker && pendingDialogue && !characters.includes(currentSpeaker)) {
      characters.push(currentSpeaker);
    }
    currentSpeaker = null;
    pendingDialogue = false;
  };

  for (const raw of lines) {
    const stripped = raw.trim();
    if (!stripped) continue;

    const charMatch = CHARACTER_CUE_RE.exec(stripped);
    if (charMatch && stripped.length < 50 && stripped === stripped.toUpperCase()) {
      flush();
      currentSpeaker = charMatch[1].trim();
      continue;
    }

    if (currentSpeaker && stripped.startsWith('(') && stripped.endsWith(')')) {
      continue;
    }

    if (currentSpeaker) {
      pendingDialogue = true;
    }
  }
  flush();

  if (includeNarrator && !characters.includes(NARRATOR)) {
    characters.push(NARRATOR);
  }
  return characters;
}
