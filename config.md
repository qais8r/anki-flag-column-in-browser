# Flag Column in Browser

## Flag Outline

Controls the outline color of the flag glyph in the Browser.

### flag_outline

- `flag` (default): Match the outline color to the flag color.
- `auto`: Matches the current theme (black in light mode, white in dark mode).
- `black`: Always use a black outline.
- `white`: Always use a white outline.

### flag_border_enabled

- `true` (default): Draw the flag glyph with an outline.
- `false`: Draw the flag glyph fill only.

### selection_style

- `classic` (default): Use Anki's default selected-row fill.
- `border`: Use border-only row selection so suspended/buried/marked backgrounds remain visible.

### state_icons_enabled

- `false` (default): Hide the state icon column.
- `true`: Show a state column with badges for Marked (`*`), Suspended (`!`), and Buried (`→`).

### sticky_columns_enabled

- `false` (default): Normal horizontal scrolling behavior.
- `true`: Keep the Flag and State columns visible while horizontally scrolling.
