@domain:findings @area:verification @from:readthrough/cli
Feature: Second-opinion verification during a scan
  Gives an operator a second model pass over the serious findings so false positives can be rejected before anyone acts on them.

  Background:
    Given a scan of "shop-api" whose merged findings are 1 critical, 2 high and 3 medium

  @id:findings.verification.001 @rule:cli.verify.only-at-or-above-threshold @gap @source:readthrough/cli.py#_verify @questionable
  Scenario Outline: Only findings at or above the chosen severity are sent for verification
    Given none of the findings has a verdict yet
    When the operator runs the scan with `--verify <threshold>`
    Then the message "verifying <count> findings (severity >= <level>)" is printed
    And each of those findings receives a verdict

    Examples:
      | threshold                      | count | level    |
      | (no --verify-min-severity)     | 3     | high     |
      | --verify-min-severity critical | 1     | critical |
      | --verify-min-severity medium   | 6     | medium   |

  @id:findings.verification.002 @rule:cli.verify.failure-recorded-as-uncertain @gap @source:readthrough/cli.py#_verify
  Scenario: A finding whose verification fails is marked uncertain instead of being lost
    Given the model call for verifying one high finding fails
    When the operator runs the scan with `--verify`
    Then that finding keeps its severity and gets the verdict "uncertain" with reasoning starting "verification failed:"
    And the progress line counts it as failed
    And the scan still writes its reports and exits with status 0
