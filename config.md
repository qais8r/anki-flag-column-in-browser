# Flag Column in Browser

## Flag Outline

Controls the outline color of the flag glyph in the Browser.

### flag_outline

- `auto` (default): Matches the current theme (black in light mode, white in dark mode).
- `black`: Always use a black outline.
- `white`: Always use a white outline.
- `flag`: Match the outline color to the flag color.

### flag_border_enabled

- `true` (default): Draw the flag glyph with an outline.
- `false`: Draw the flag glyph fill only.

### selection_style

- `border` (default): Use border-only row selection so suspended/buried/marked backgrounds remain visible.
- `classic`: Use Anki's default selected-row fill.

### state_icons_enabled

- `true` (default): Show a state column with badges for Marked (`*`), Suspended (`!`), and Buried (`→`).
- `false`: Hide the state icon column.

### sticky_columns_enabled

- `false` (default): Normal horizontal scrolling behavior.
- `true`: Keep the Flag and State columns visible while horizontally scrolling.
