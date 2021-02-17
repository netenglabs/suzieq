# Suzieq Release Checklist

This is the checklist in releasing Suzieq:

- Make sure all tests pass:
  : ```pytest```
- Update the version string in Dockerfile
- Build the docker image with the specified version
  : At the top level project directory, execute ```docker build -t netenglabs/suzieq:<release-version> .```
- Build the latest tag docker image:
  : At the top level project directory, execute ```docker build -t netenglabs/suzieq:latest .```
- Delete and mkdir parquet directory under the main suzieq directory
- Copy the tests/data/{nxos, junos, multidc/ospf-ibgp, basic_dual_bgp/}/parquet-out files to the parquet directory
- Uncomment the line ```COPY ./parquet /suzieq/parquet``` from the Dockerfile
- Build the suzieq-demo container: ```docker build -t netenglabs/suzieq-demo:latest```
- Push out all the docker containers: netenglabs/suzieq:<release-version>, netenglabs/suzieq:latest and netenglabs/suzieq-demo:latest to dockerhub
- Write the release notes (under docs/release-notes.md) and commit it
- Update the release version in README.md
- Tag the release: ```git tag -a v<release-version> -m <add a commit message>```
- Push the tag to the repo: ```git push origin v<release-version>```
- Goto https://github.com/netenglabs/suzieq/releases and create a new release based on the tag
- Make the announcement on LI, Twitter, #suzieq channel on netenglabs Slack and on networktocode slack

