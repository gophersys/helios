# Deep User Story Protocol

When a spec involves user-facing features (UI, API, workflows), create deep user stories
that go beyond simple step lists. Each story must be implementable by an agent that has
never seen the codebase.

## When to Create Deep Stories

- Spec has role-based access control (multiple user types)
- Spec involves UI interactions (forms, wizards, navigation)
- Spec involves end-to-end workflows (multi-step processes)
- User asks for "depth", "detail", "every step"

## Story Structure

Store in `<spec-path>/stories/<ROLE>-STORY.md`.

### Per-Step Requirements (ALL 5 dimensions)

For EVERY step in the story, document:

1. **User Action:** Exactly what the user clicks/types
   - CSS selectors or `data-testid` attributes
   - Button text, placeholder text, link text
   - Navigation sequence (sidebar → page → tab → button)

2. **Expected UI State:** What appears on screen
   - Specific text, headings, counts
   - Element visibility (present/absent based on permissions)
   - Loading states, empty states, error states
   - Badge colors, status indicators

3. **Backend Verification:** What happens server-side
   - API endpoint called (method, path, body)
   - Permission decorator that gates the endpoint
   - Database records created/updated/deleted
   - Side effects (notifications, queue entries, K8s deployments)

4. **Failure Modes:** What could go wrong
   - Network timeout, 500 error
   - Permission denied (403)
   - Validation error (400)
   - Conflict (409 — duplicate name, deletion blocked)
   - External system unavailable (Bitbucket, CoreCloud, hardware)

5. **Assertion Strategy:** How Playwright/tests verify
   - `page.waitForSelector()` for DOM elements
   - `expect(locator).toBeVisible()`
   - `expect(locator).toHaveText()`
   - API polling with `waitFor()` for async operations
   - WebSocket event observation via DOM mutations

## Permission Boundary Tests

For each role, explicitly test:

### What IS allowed (positive tests)
```
test('Admin can create product via wizard')
  → Click "Create Product" button (visible)
  → Complete wizard
  → Verify product appears in list
  → Verify API returns 201
```

### What is NOT allowed (negative tests)
```
test('Developer cannot create product')
  → "Create Product" button NOT visible (UI hidden)
  → API: POST /v2/products → 403 (API enforced)
```

Always test BOTH UI visibility AND API enforcement for every permission boundary.

## Cross-Referencing the Codebase

Before writing a story, agents MUST verify against actual code:

1. **Sidebar visibility:** Read `sidebar.svelte` — which permission gates each item?
2. **Route guards:** Read `+page.svelte` files — what does `onMount` check?
3. **API permissions:** Read route handler — what does `@require_permissions()` check?
4. **Form fields:** Read the actual component — what inputs/selectors exist?
5. **Wizard steps:** Read the wizard component — how many steps? What's in each?

Document any discrepancies between the story and the codebase in the story file.

## Gap Analysis Integration

After writing stories, run a gap analysis:
- For each API endpoint mentioned, verify it exists in `router.py`
- For each permission mentioned, verify it exists in `permissions.py`
- For each UI element mentioned, verify it exists in the component file
- Document findings in `GAP-ANALYSIS-DEEP.md`

Findings categories:
- **VERIFIED:** Story matches code
- **WRONG:** Story doesn't match code (fix the story)
- **MISSING:** Code doesn't implement what the story needs (stage must build it)
- **RISK:** Could break at runtime (document for testing)
