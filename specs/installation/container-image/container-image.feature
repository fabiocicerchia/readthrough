@domain:installation @area:container-image @from:readthrough/dockerfile
Feature: Running readthrough from the container image
  Lets CI operators audit a mounted repository with readthrough without installing Python packages on the runner.

  Background:
    Given the readthrough container image has been built

  @id:installation.container-image.001 @rule:installation.container.arguments-run-readthrough @inferred @source:Dockerfile#ENTRYPOINT
  Scenario Outline: Arguments given to the container run as a readthrough command
    Given a repository is mounted into the container at /src
    When the operator runs the image with the arguments <arguments>
    Then readthrough runs the <command> command
    And the container exits with readthrough's exit status

    Examples:
      | arguments                   | command |
      | scan /src --out /out --fake | scan    |
      | lenses                      | lenses  |
      | report /out                 | report  |

  @id:installation.container-image.002 @rule:installation.container.no-arguments-shows-help @inferred @source:Dockerfile#CMD
  Scenario: Running the image with no arguments shows the usage help
    When the operator runs the image with no arguments
    Then readthrough's usage help is printed
    And no scan is started

  @id:installation.container-image.003 @rule:installation.container.runs-unprivileged @inferred @source:Dockerfile#USER
  Scenario: The container runs readthrough as an unprivileged user with a fixed id
    Given the operator does not override the container user
    When the operator runs a scan in the container
    Then readthrough runs as user id 10001, not as root
    And an output directory must be writable by user id 10001 or the scan cannot write its results

  @id:installation.container-image.004 @rule:installation.container.reports-in-output-mount @inferred @source:readthrough/cli.py#cmd_scan
  Scenario: A scan of a read-only mounted repository writes its reports and resumable state to the output mount
    Given a repository is mounted read-only at /src
    And a writable directory is mounted at /out
    When the operator runs a scan of /src with output to /out
    Then the reports and the scan state file scan.db appear in the host directory mounted at /out
    And the mounted repository is left unchanged

  @id:installation.container-image.005 @rule:installation.container.default-output-is-ephemeral @inferred @source:readthrough/cli.py#cmd_scan @questionable
  Scenario: Without an output directory, a containerised scan leaves its reports inside the container
    Given a repository is mounted at /src
    And the operator runs the container with automatic removal
    When the operator runs a scan of /src without choosing an output directory
    Then the reports are written to /work/readthrough-reports/src inside the container
    And no reports appear on the host once the container is removed

  @id:installation.container-image.006 @rule:installation.container.progress-streams-live @inferred @source:Dockerfile#ENV
  Scenario: Scan progress appears in the container logs while the scan runs
    Given a scan is running in a detached container
    When the operator follows the container's logs
    Then progress lines appear as the scan advances, not all at once when it exits
