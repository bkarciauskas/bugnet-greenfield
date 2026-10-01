# Characterisation tests

This directory holds characterisation tests for the BugNET greenfield rebuild.

Build agents cannot edit it. The Cursor hook denies writes and shell redirects. CI denies pull requests that change it.

The only override is the pull request label `allow-characterisation-edit` applied by GitHub user `bkarciauskas`. An agent cannot apply that override itself.

This introduction is the only automatic exception. After it merges, further edits need Ben's label.
