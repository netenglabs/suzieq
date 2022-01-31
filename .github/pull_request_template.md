### Set `develop` as target branch of this PR (delete this line before issuing the PR)

## Test inclusion requirements
In case the PR contains an enhancement or a new platform/service support, some tests have to be added for the new functionality:
- any fix or enhancement SHOULD include relevant new tests or test updates, if any tests need updating.
- a new platform support MUST include the relevant input files similar to what we have in tests/integration/sqcmds/-input directories, along with the relevant tests in the tests/integration/sqcmds/-samples dir. That list MUST include the all.yml file fully filled out.
- any new service (or table) addition MUST include comments about what network OS are supported (along with version) with this command along with test samples for those platforms and input files in the *-input dir

For additional informations about tests, follow this [link](https://suzieq.readthedocs.io/en/latest/developer/testing/)
## Description
Please include a summary of the change and which issue is fixed. Please also include relevant motivation and context. List any dependencies that are required for this change.

Fixes # [issue_number](issue_link)

## Type of change
Please delete options that are not relevant.

- Bug fix (non-breaking change which fixes an issue)
- New feature (non-breaking change which adds functionality)
- Breaking change (fix or feature that would cause existing functionality to not work as expected)
- Documentation update

## Comments
Include additional comments about the this pull request
