-- Phase 1.5b: Fountain spec compliance — extend script_elements.type enum
ALTER TABLE greenlight.script_elements
    MODIFY COLUMN `type` Enum8(
        'scene_heading' = 1,
        'action' = 2,
        'character' = 3,
        'parenthetical' = 4,
        'dialogue' = 5,
        'transition' = 6,
        'title_page' = 7,
        'note' = 8,
        'synopsis' = 9,
        'section' = 10,
        'centered' = 11
    );
