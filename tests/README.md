# The offline tests

Every test in here runs with no browser, no network and no LinkedIn. They are
unit-sized tests against strings and fakes, and they exist because the
independent inspection of 2026-09-09 handed us concrete breaking inputs - a urn
in a query parameter, a first-match motif in a slug, `1,2K` becoming 12000,
`12+3` becoming 123, an empty `headline=` expectation, a missing `--page`
silently skipping a whole block.

Run them:

    py -3.11 -m unittest discover -s tests -t . -v

EVERY ONE OF THESE WAS WATCHED FAILING against the behaviour it replaces before
the fix was written. What was seen is written down in
`docs/inspection-fixes.md`, symptom by symptom. A test that has never been
watched failing is decoration.
