# BI row access — how it works

Per-user row-level security (RLS) for Power BI / SSAS, managed from Odoo. This
covers the `bi.user.access` feature only (the "BI Access" tab on a user's
form). The Windows/AD/local-group manager (`win.access.group`) is separate
and not covered here.

## 1. Why this exists

SSAS row-level security at Shaka is **dynamic**: every protected table carries
the *same* generic DAX filter. It doesn't check "is this user in role X" —
it looks the current Windows user up in a data table, `vwUserAccess`, at
query time:

```dax
1 IN SELECTCOLUMNS(
    CALCULATETABLE(vwUserAccess, vwUserAccess[UserName] = USERNAME()),
    "IsAllReader", vwUserAccess[IsAllReader])
|| 1 IN SELECTCOLUMNS(
    CALCULATETABLE(vwUserAccess,
        vwUserAccess[UserName] = USERNAME(),
        vwUserAccess[EntityID] = 1000171),
    "IsAllMember", vwUserAccess[IsAllMember])
|| DimWarehouse[Label] IN SELECTCOLUMNS(
    CALCULATETABLE(vwUserAccess,
        vwUserAccess[UserName] = USERNAME(),
        vwUserAccess[EntityID] = 1000171,
        vwUserAccess[EntityColumnName] = "Label"),
    "MemberID", vwUserAccess[MemberID])
```

The consequence: **a user's access is data, not configuration.** Nobody
edits a DAX expression or an SSAS role per user. Granting or revoking access
is entirely a matter of adding or removing rows in one table,
`MD.UserAccess`, and its view `MD.vwUserAccess`. This addon is a UI over
that table — nothing more, nothing SSAS-side.

Because of this, `win_access` never creates SSAS roles or DAX for this
feature, and there's no such thing as "this user's personal role."

## 2. Where the data lives

- **Database:** `Shaka_DW` (SQL Server). Odoo connects to it through the
  `raes_dw_connector` addon's `raes.dw.connection` record — the same
  connection the entity/module mirror (`entity` addon) is built from.
- **Table:** `MD.UserAccess`. Columns that matter here: `UserName`,
  `EntityID`, `EntityName`, `MemberID`, `IsAllReader`, `IsAllMember`,
  `EntityColumnName`.
- **View:** `MD.vwUserAccess` — a thin `SELECT` over `MD.UserAccess` that
  exposes the exact nine columns the DAX above depends on. This is what the
  tabular model actually queries; the table is Odoo's write surface.

`EntityID` is the *same* integer as `raes.md.entity.id` in Odoo (both trace
back to the ERP's own `MD.Entity` table, e.g. `DimWarehouse` = 1000171 in
both places) — that's what lets Odoo pick an entity from a dropdown and
write its id straight into the warehouse without any translation.

### The one-time repair (`scripts/01_md_useraccess.sql`)

Before Odoo can use any of this, a DBA runs
`addons/win_access/scripts/01_md_useraccess.sql` once, by hand, against
`Shaka_DW`. It:

1. Adds `UserName`, `EntityName`, `EntityColumnName` to `MD.UserAccess` (the
   table pre-dates this feature and didn't have them).
2. Quarantines the pre-existing legacy rows (copies them to
   `MD.UserAccess_legacy`, then deletes them from the live table) — they
   used an old, incompatible `EntityID` numbering and would silently grant
   wrong access if left in place.
3. Recreates `MD.vwUserAccess` as a **local** view over `Shaka_DW.MD.UserAccess`.
   Before this, the view pointed at `[ShakasystemDB].MD.vwUserAccess` — a
   database name that doesn't exist — so every read failed.
4. One-time imports the live grants that already existed in
   `Shaka_System_DB.MD.vwUserAccess` into `Shaka_DW`, so nothing is lost.

Odoo never runs this script itself; it's reviewed SQL, run by hand, once.

## 3. The Odoo data model

```
res.users (core, extended)
  └─ bi_username           Char, e.g. "RAEES\\jane"
  └─ bi_access_ids         One2many → bi.user.access

bi.user.access             one record per (user, entity)
  ├─ user_id                → res.users
  ├─ module_id               → raes.gnr.module   (just for the wizard's cascading dropdown)
  ├─ entity_id                → raes.md.entity   (.id IS the warehouse EntityID)
  ├─ ssas_table              Char, e.g. "DimBranch"
  ├─ is_all_reader           Boolean — IsAllReader
  ├─ is_all_member           Boolean — IsAllMember for this entity
  ├─ line_ids                One2many → bi.user.access.line
  ├─ state                   draft / synced / error
  └─ sync_result             Json — step-by-step result, shown in the sync panel

bi.user.access.line         one row per (column, value) the user may see
  ├─ access_id                → bi.user.access
  ├─ column_name              Char, e.g. "BranchID"  (an SSAS column name)
  └─ member_id                Char, e.g. "17000000000000023"  (kept as text: values
                               exceed 32-bit int range and the base table's type
                               is inconsistent across databases)
```

A `bi.user.access` record with `is_all_reader`/`is_all_member` set writes
one warehouse row with a `NULL` member/column and the flag on. Every line
under `line_ids` writes its own warehouse row with that column/value pair
and both flags off. All of it maps 1:1 onto rows of `MD.UserAccess` — the
Odoo model doesn't add any interpretation on top.

## 4. The UI flow

### 4.1 The button

Settings → Users → a user → **BI Access** tab (added by
`views/bi_user_access_views.xml`, inheriting `base.view_users_form`). It
shows:

- `bi_username` — the Windows account SSAS's `USERNAME()` will return for
  this person, e.g. `RAEES\jane`. It's computed once from the AD domain
  `win_access` already derives plus the Odoo login, but it's an editable
  field, not a hidden default — **the live warehouse rows use the `RAEES\`
  domain while the AD `win_access` talks to reports `SHAKA`**, so this field
  must be checked/corrected per user, not trusted blindly.
- Three buttons: **Add access**, **Import from warehouse**, **Sync all**.
- A list of the user's existing `bi_access_ids`.

### 4.2 Popup 1 — pick the target (`bi.user.access.wizard`)

Opened by `action_bi_add()`. Three cascading fields:

1. **Module** (`raes.gnr.module`).
2. **Entity** (`raes.md.entity`), domain-restricted to that module.
3. **SSAS table** (`win.access.option`, `kind='ssas_table'`), narrowed to
   the tables whose name matches the entity, computed by
   `match_ssas_tables()`:

   ```python
   rx = re.compile(r"^%s\s*\d*$" % re.escape(entity_name), re.I)
   ```

   i.e. the table name must be the entity name, optionally followed by
   whitespace and digits — `DimParty` matches `DimParty`, `DimParty 1`,
   `DimParty 2`, but never `DimPartyType`. Most entities (111 of 114 that
   match anything) have exactly one candidate table and it auto-selects;
   a few (`DimParty`, `DimDate`, `DimDetailedLedger`) offer a real choice.

`action_confirm()` creates the `bi.user.access` record, then immediately
opens popup 2 for it.

### 4.3 Popup 2 — add a value (`bi.user.access.line.wizard`)

Loads the chosen table's columns lazily from the live SSAS API
(`win.access.option.load_columns()`, `kind='ssas_column'`) — not from
`raes.md.entity_column`, because the two disagree (SSAS's column set for a
table isn't the same as the ERP metadata's). Only the internal
`RowNumber-<guid>` technical column is filtered out; hidden business
columns (like `BranchID`, which is the column the real grants actually use)
are kept.

Fields: **SSAS column** (dropdown) and **Value** (the `MemberID`, typed as
text and validated as a whole number up to 18 digits). Two buttons:

- **Save & add another** — creates the line, reopens the same popup for the
  next pair.
- **Save & close** — creates the line and closes.

This lets one `bi.user.access` record carry several column/value grants
(e.g. several `MemberID`s the same user may see on the same entity).

## 5. Sync — writing to the warehouse

`bi.user.access.action_sync()` runs a `Runner()` (the same step-by-step,
per-step-error-handling helper `win.access.group` uses) with two steps:

1. **Windows account** — `_check_user()` just verifies `bi_username` isn't
   empty; if it is, sync fails right there with a clear message instead of
   silently writing a row nothing will ever match.
2. **Replace access rows of `<entity>`** — `_write_rows()`:
   - Connects via `raes.dw.catalog._mssql_connect(connection)` (pymssql,
     reusing the DW connector's helper — never opens pymssql directly).
   - In one transaction: `DELETE FROM MD.UserAccess WHERE UserName = ...
     AND EntityID = ...`, then re-`INSERT`s every row implied by the
     current state (`is_all_reader`/`is_all_member` plus each line).
   - Commits, or rolls back and raises with a hint if anything fails.

The result of each step (ok/failed/skipped + message) is stored on
`sync_result` and rendered by the generic `win_access_sync` OWL widget —
the same panel used for Windows/PBIRS groups.

**Delete-then-insert, not diff.** Every sync fully replaces that user's
rows for that entity. This means sync is idempotent and simple, but it also
means two people syncing the same user+entity concurrently can race; that's
accepted as out of scope (this is an admin tool, not a high-concurrency one).

Deleting a `bi.user.access` record does the mirror operation first: it
clears its own lines/flags and calls `_write_rows()` (which now writes
nothing for that user+entity) *before* the Odoo record is removed, so the
warehouse never keeps access Odoo no longer lists.

## 6. Import — reading from the warehouse

`bi.user.access.import_user(user)` (triggered by **Import from warehouse**)
does the reverse: it reads every row of `MD.vwUserAccess` for that user's
`bi_username`, groups them by `EntityID`, and for each group:

- Resolves the entity via `raes.md.entity.browse(entity_id).exists()` —
  entities the warehouse knows about but Odoo doesn't (an id mismatch, or
  an entity Odoo hasn't mirrored) are counted as **skipped**, not created,
  and the count is shown in the result notification.
- Creates or updates the matching `bi.user.access` record and its lines
  from the warehouse data, and guesses `ssas_table` the same way popup 1
  does (`match_ssas_tables`).
- Marks the record `synced` immediately, since the data *is* what's live in
  the warehouse — there's nothing to push.

This is how the 3 pre-existing live grants (for `mr.hanifi`, `mis.hanifi`,
`saharkhiz` on `DimBranch`) become visible and editable in Odoo without
anyone re-entering them by hand.

## 7. What this does *not* do

- **No SSAS roles or DAX per user.** The one shared DAX filter (already on
  the model, or to be added once — see §8) is what reads these rows; Odoo
  never touches SSAS for this feature.
- **No coverage for non-Odoo users.** Odoo currently has a handful of real
  (non-portal) users while the ERP's own `SCR.User` table has ~194. Anyone
  without an Odoo account can't be granted access through this button —
  their warehouse rows, if any, are only visible/editable by direct SQL or
  by giving them an Odoo account.
- **No conflict detection across SSAS roles.** If a user is also in some
  other SSAS role that leaves a protected table unfiltered, they'll see
  everything regardless of what's in `MD.UserAccess` — this addon only
  manages the rows the shared DAX consults, not the full set of roles a
  user might belong to.

## 8. What's deliberately not built (optional future work)

Odoo could, in principle, also *generate and push* the DAX filter itself
(`PUT /v1/ssas/{instance}/databases/{db}/roles/{role}/tables/{table}` with
a `filter_expression` built from `entity_id`/table/column). This wasn't
built because it has a hard prerequisite outside Odoo's reach: `vwUserAccess`
must first be imported as a table into the `Shaka_SSAS` tabular model via
Visual Studio / Tabular Editor — there is no API endpoint for that. Until
someone does that import, generating DAX from Odoo has nothing to attach
to, so this stays manual/optional.

## 9. Files

| File | Role |
|---|---|
| `models/bi_user_access.py` | `bi.user.access`, `bi.user.access.line`, the MSSQL read/write helpers, `match_ssas_tables()` |
| `models/res_users.py` | `bi_username`, `bi_access_ids`, the three button actions |
| `models/group.py` | shared `Runner`, `ApiError`, and `win.access.option` (pick-list cache incl. `ssas_table`/`ssas_column`) |
| `wizard/bi_user_access_wizard.py` | the two popups |
| `views/bi_user_access_views.xml` | popup views, the user-form "BI Access" page |
| `scripts/01_md_useraccess.sql` | the one-time DBA repair script |
| `tests/test_win_access.py` | `match_ssas_tables()` unit tests |
