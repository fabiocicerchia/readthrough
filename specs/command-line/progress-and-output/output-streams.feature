@domain:command-line @area:progress-and-output @from:readthrough/console
Feature: Keeping results and diagnostics on separate output streams
  Operators who pipe or redirect readthrough's output need its results on standard output and its refusals and diagnostics on standard error, so a redirected report never contains an error message.

  @id:command-line.progress-and-output.001 @rule:cli.output.results-on-stdout-diagnostics-on-stderr @inferred @source:readthrough/console.py#err
  Scenario Outline: Results go to standard output and diagnostics go to standard error
    Given the operator redirects standard output to a file
    When the operator runs <command>
    Then standard output contains <stdout>
    And standard error contains <stderr>

    Examples:
      | command                                                     | stdout              | stderr                                                  |
      | readthrough report readthrough-reports/acme-api --stdout    | the markdown report | nothing                                                 |
      | readthrough report readthrough-reports/missing --stdout     | nothing             | no scan.db in readthrough-reports/missing               |
      | readthrough scan ./not-a-dir                                | nothing             | not a directory: <resolved path>                        |
      | readthrough scan ./acme-api --lenses injection,bogus --fake | nothing             | unknown lenses: bogus, followed by the available lenses |
