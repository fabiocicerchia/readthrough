@domain:command-line @area:entry-points @from:readthrough/readthrough
Feature: Launching readthrough
  Lets an operator start readthrough as a Python module when the console command is not on their PATH, with the same commands and exit status.

  @id:command-line.entry-points.001 @rule:command-line.entry-points.module-launch-matches-command @inferred @source:readthrough/__main__.py#main
  Scenario Outline: Launching readthrough as a Python module behaves like the readthrough command
    Given readthrough is installed in the operator's Python environment
    When the operator runs "python -m readthrough <arguments>"
    Then the same command runs as for "readthrough <arguments>"
    And the process exits with status <exit status>

    Examples:
      | arguments                                    | exit status |
      | lenses                                       | 0           |
      | scan . --fake, interrupted with Ctrl-C twice | 130         |
