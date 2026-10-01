# ADR-003: Accounts belong to Positions, not to people

**Status:** accepted
**Date:** 2026-10-01

## Context

AWM's Officers change every year. The client brief says "there will be passwords
that are passed down from spring semester to fall semester each year." That can
be built two ways: one Account per Position, whose password is handed to
whoever holds the Position next, or one Account per person, created and
deactivated by the Co-VPs each year.

Per-person Accounts are the usual choice, because a former Officer who still
knows a shared password can still sign in. Per-Position Accounts were chosen
anyway, for the client's stated reason: "it isnt that top secret, former
position members will hardly think about it."

## Decision

There is one Account per Position: Co-VP, Co-President, Social Chair, and
Treasurer. The two Co-VPs share one Account and the two Co-Presidents share
another. Passwords are passed down at Handover. The Co-VP Account is the Admin;
the other three are Editors.

## Consequences

- The Author of a Post is a Position ("Social Chair"), never a named person. The
  console cannot tell which of the two Co-VPs did something.
- A former Officer who remembers a password can still sign in until a Co-VP
  sets a new one. The console runs only on a Co-VP's laptop (ADR-001), so they
  would also need that laptop.
- Co-VPs can set a new password for any Account. There is no "forgot my
  password" email.
- Deactivating is for a Position that is vacant, not for a person who has left.
  A deactivated Account's Posts stay on the site, and Accounts are never deleted.
- The last active Admin Account can never be deactivated or changed to Editor,
  because with one shared Admin Account that would lock everyone out.
- Moving to per-person Accounts later would mean re-deciding who the Author of
  every existing Post is.
