# Agent Guidelines

## Project Overview
This project appears to be a parental-control system with:
- a backend API service,
- database management utilities,
- event processing / enforcement logic,
- logging helpers,
- a small client/front-end component.

## Working Principles
- Prefer small, focused changes.
- Keep existing behavior unless a change is explicitly requested.
- Do not refactor unrelated code while implementing a task.
- Preserve compatibility with the current project structure.
- Avoid introducing new dependencies unless they are clearly needed.

## Codebase Conventions
- Follow the existing style in each file rather than forcing a new style globally.
- Keep database access centralized where possible.
- Reuse existing helper classes for logging, IDs, and persistence.
- When changing API behavior, check all call sites and dependent logic.
- When adding new tables, queries, or fields, update related initialization and data-access code together.

## Backend Notes
- The project uses Python for backend logic.
- There is an API layer for receiving events and checking app access.
- There is a database layer that manages schema creation and user/app rules.
- There is engine logic that processes app start/stop events and session tracking.
- Logging is already supported through a shared logger helper.

## Database Notes
- Be careful when changing schema definitions: table creation, inserts, and queries must stay in sync.
- If a field is renamed or added, update all SQL statements using it.
- Avoid destructive database actions unless the task explicitly requests them.
- Do not assume tables or columns exist unless they are created by the project itself.

## Logging Notes
- Use the existing logging helper for new log output.
- Keep log messages informative and short.
- Do not log sensitive secrets, credentials, or personal data.

## Security and Privacy
- Never hardcode credentials, tokens, or secrets in source files.
- Do not expose private data in logs, responses, or generated documentation.
- Treat identifiers and user/device data as sensitive.

## When Making Changes
Before editing:
1. Identify the smallest file set that can solve the task.
2. Check for related methods, database queries, and callers.
3. Verify whether the change affects runtime behavior, schema, or logs.

After editing:
1. Validate the affected code paths.
2. Ensure syntax and imports are still correct.
3. Check for any broken references or missing database columns.

## Testing Guidance
- Prefer adding or updating tests when behavior changes.
- If tests are not available, describe how to verify the change manually.
- Validate API endpoints, database operations, and event handling after modifications.

## If You Need to Add New Functionality
- Reuse the current architecture instead of introducing a parallel one.
- Keep domain logic in the engine/service layer.
- Keep persistence logic in the database layer.
- Keep request parsing and response formatting in the API layer.

## Files of Interest
- Backend/API entrypoint
- Database helper module
- Event-processing engine
- Logger setup helper
- SID/identity helper
- Client/front-end files

## Communication Style
When responding to tasks:
- Be clear about what changed.
- Mention any assumptions.
- Call out follow-up steps if something may require manual verification.
