# Set `develop` as target branch of this PR (delete this line before issuing the PR)

## Test inclusion requirements

In case the PR contains an enhancement or a new platform/service support, some tests have to be added for the new functionality:

- any fix or enhancement SHOULD include relevant new tests or test updates, if any tests need updating.
- a new platform support MUST include the relevant input files similar to what we have in tests/integration/sqcmds/-input directories, along with the relevant tests in the tests/integration/sqcmds/-samples dir. That list MUST include the all.yml file fully filled out.
- any new service (or table) addition MUST include comments about what network OS are supported (along with version) with this command along with test samples for those platforms and input files in the *-input dir

For additional information about tests, follow this [link](https://suzieq.readthedocs.io/en/latest/developer/testing/)

## Related Issue

<!--Add the related issue in the form of #issue-number (Example #100)-->
Fixes #<!-- issue number -->

## Description

Please include a summary of the change and which issue is fixed. Please also include relevant motivation and context. List any dependencies that are required for this change.

## Type of change

Please delete options that are not relevant.

- Bug fix (non-breaking change which fixes an issue)
- New feature (non-breaking change which adds functionality)
- Breaking change (fix or feature that would cause existing functionality to not work as expected)
- Documentation update

## New Behavior

<!--
Please describe in a few words the intentions of your PR.
-->

...

## Contrast to Current Behavior

<!--
Please describe in a few words how the new behavior is different
from the current behavior.
-->

...

## Discussion: Benefits and Drawbacks

<!--
Please make your case here:

- Why do you think this project and the community will benefit from your
  proposed change?
- What are the drawbacks of this change?
- Is it backwards-compatible?
- Anything else that you think is relevant to the discussion of this PR.

(No need to write a huge article here. Just a few sentences that give some
additional context about the motivations for the change.)
-->

...

## Changes to the Documentation

<!--
If the docs must be updated, please include the changes in the PR.
-->

...

## Proposed Release Note Entry

<!--
Please provide a short summary of your PR that we can copy & paste
into the release notes.
-->

...

## Comments

Include additional comments about the this pull request

## Double Check

<!--
Please put an x into the brackets (like `[x]`) if you've completed that task.
-->

- [ ] I have read the comments and followed the [CONTRIBUTING.md](https://github.com/netenglabs/suzieq/blob/master/CONTRIBUTING.md).
- [ ] I have explained my PR according to the information in the comments or in a linked issue.
- [ ] My PR source branch is created from the `develop` branch.
- [ ] My PR targets the `develop` branch.
- [ ] All my commits have `--signoff` applied
