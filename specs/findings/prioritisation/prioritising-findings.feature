@domain:findings @area:prioritisation @from:readthrough/merge
Feature: Prioritising findings
  Operators read the report, console summary and multi-repository rollup with the findings most worth fixing first, ranked by severity adjusted for agreement, confidence and verification.

  Background:
    Given a scan of a repository has completed with merged findings

  @id:findings.prioritisation.001 @rule:findings.prioritisation.severity-adjusted-by-agreement-and-confidence @inferred @source:readthrough/merge.py#priority_score @questionable
  Scenario Outline: Findings are ordered by severity, adjusted by agreement, corroboration and confidence
    Given finding A is <a>
    And finding B is <b>
    When the operator builds the report
    Then finding <first> is listed before finding <second>

    Examples:
      | a                                                              | b                                      | first | second |
      | high, confidence medium, agreement 1                           | medium, confidence medium, agreement 1 | A     | B      |
      | medium, confidence high, agreement 3                           | medium, confidence low, agreement 1    | A     | B      |
      | medium, confidence high, agreement 5, corroborated by 8 passes | high, confidence low, agreement 1      | A     | B      |
      | low, confidence medium, agreement 3                            | low, confidence medium, agreement 1    | A     | B      |

  @id:findings.prioritisation.002 @rule:findings.prioritisation.verification-verdict-moves-rank @inferred @source:readthrough/merge.py#priority_score
  Scenario Outline: A confirmed finding rises and a rejected finding sinks in the ranking
    Given two otherwise identical high-severity findings
    And the verification pass marked one of them <verdict>
    When the operator builds the report
    Then the finding marked <verdict> is ranked <position> the unverified one

    Examples:
      | verdict   | position   |
      | confirmed | above      |
      | rejected  | below      |
      | uncertain | level with |
