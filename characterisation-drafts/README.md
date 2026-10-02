# Characterisation drafts

Write new characterisation tests in this folder. It is not locked. `characterisation-tests/` is locked: the hook denies creating a new file there, and it denies editing a file that is already there.

1. Write the test under `characterisation-drafts/` and run it against the legacy BugNET host until it passes.
2. Ben reviews the draft.
3. A pull request moves the files into `characterisation-tests/`. GitHub user `bkarciauskas` applies the label `allow-characterisation-edit`. An agent cannot apply that label itself.

To change a test that is already locked, draft the change here. Do not write the file under `characterisation-tests/`. The same review and the same label are required before that change lands.

Recording, labelling, and choosing the first slice wait until Ben says to start.
