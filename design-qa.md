# ChefBot design QA

## Evidence

- Approved loaded-state reference: `docs/design/chefbot-ui-reference.png`
- User-reported regression: `docs/design/chefbot-ui-empty-before.png`
- Corrected empty state: `docs/design/chefbot-ui-empty-fixed.png`
- Empty-state comparison: `docs/design/chefbot-ui-empty-comparison.png`
- One-item transition: `docs/design/chefbot-ui-one-item-fixed.png`
- Corrected mobile empty state: `docs/design/chefbot-ui-empty-mobile-fixed.png`
- Corrected loaded state: `docs/design/chefbot-ui-implementation-loaded.png`
- Loaded-state comparison: `docs/design/chefbot-ui-comparison-loaded.png`
- Empty desktop viewport: `1462 x 647` CSS pixels at `deviceScaleFactor: 2`
  (`2924 x 1294` screenshot pixels), exactly matching the regression capture.
- Loaded desktop viewport: `1487 x 1058` at `deviceScaleFactor: 1`, exactly
  matching the approved reference.
- Mobile viewport: `390 x 844` at `deviceScaleFactor: 1`.

Both desktop comparisons place the source and current implementation together at
identical viewport, state, and density. The regression screenshot is defect evidence,
not an intended visual target.

## Findings resolved

- [P1] The add-product placeholder appeared twice because CSS generated a second copy.
  The synthetic `::after` content is gone; the browser reports one visible placeholder
  and pseudo-element content `none`.
- [P1] Clearing the last ingredient left the CTA actually enabled because `st.form`
  batched the multiselect change until submission. The picker and button now rerun
  independently, so the CTA immediately becomes disabled and visually neutral.
- [P1] The empty input occupied only `381 px` while the CTA sat on the far edge of the
  screen. The input now fills its column (`1045 px`) with a `37 px` gap to the `262 px`
  CTA at the regression viewport.
- [P2] The follow-up control appeared before there was recipe or conversation context.
  It is now hidden in the initial and empty states.
- [P2] The first flex correction briefly let the input wrapper overlap ingredient tags.
  Keeping the wrapper `position: relative` preserves normal layout and click targets.
- [P2] The desktop flex basis initially made the empty mobile input `272 px` tall. The
  mobile rule resets that basis; the final input is `69 px` high with no horizontal
  overflow.
- [P2] A nested `st.container()` moved the loaded-state follow-up input into page flow
  and below the viewport. It is now a direct `st.chat_input`, restored to Streamlit's
  sticky bottom container at `y=930`, fully visible within the `1058 px` viewport.

No actionable P0, P1, or P2 visual mismatch remains.

## Functional browser checks

- Deleted all three initial tags one at a time and observed a rerender after each.
- Empty state contained exactly one placeholder, a disabled CTA, the requirement hint,
  and no chat input.
- Typed and selected `рис`; one ingredient appeared, the CTA enabled, and the empty hint
  disappeared.
- Mobile empty state had `390 px` client and scroll widths and a normal-height input.
- Loaded state retained three ingredients, an enabled CTA, grounded recipe content, and
  a fully visible sticky follow-up control.
- Browser QA reported zero console errors and zero page errors in both flows.

## Intentional P3 differences

- The approved mockup shows quantities inside the selected-product chips. The product
  does not collect inventory quantities, so the implementation shows ingredient names
  only rather than inventing user data.
- The loaded preview renders the verified local recipe record, so its ingredients and
  steps can differ from illustrative mockup copy.
- The chef mark uses the closest Material Symbols icon because no standalone logo asset
  was supplied.

## Implementation checklist

- [x] Empty desktop state compared at identical viewport, density, and state.
- [x] Loaded desktop state compared at identical viewport, density, and state.
- [x] Empty, one-item, loaded, and mobile interactions exercised.
- [x] Disabled, enabled, hidden-context, and sticky follow-up states measured in-browser.
- [x] Typography, spacing, colors, affordances, copy, and responsive behavior reviewed.
- [x] All P1/P2 findings fixed and recaptured.

final result: passed
