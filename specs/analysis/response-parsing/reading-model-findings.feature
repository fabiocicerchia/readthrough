@domain:analysis @area:response-parsing @from:readthrough/engine
Feature: Reading findings from the model's reply
  Operators rely on every reported finding pointing at real code with valid labels, so replies are cleaned rather than trusted.

  Background:
    Given a file section covering lines 1 to 40 is analysed by a lens

  @id:analysis.response-parsing.001 @rule:analysis.response-parsing.wrapped-reply-accepted @inferred @source:readthrough/engine.py#_extract_json
  Scenario Outline: Findings wrapped in code fences or surrounding prose are still read
    Given the model returns its findings object <wrapping>
    When the operator runs the scan
    Then the pass is reported as done
    And its findings appear in the report

    Examples:
      | wrapping                        |
      | inside a ```json code fence     |
      | after a sentence of explanation |
      | as bare JSON                    |

  @id:analysis.response-parsing.002 @rule:analysis.response-parsing.findings-confined-to-shown-lines @inferred @source:readthrough/engine.py#_clean_findings
  Scenario Outline: A finding is kept only when it points inside the code shown and has a title and explanation
    Given the model reports a finding with title "<title>", an explanation, start line <start> and end line <end>
    When the operator runs the scan
    Then the finding is <outcome>

    Examples:
      | title                     | start | end | outcome                 |
      | SQL built from user input | 12    | 14  | reported at lines 12-14 |
      | SQL built from user input | 14    | 12  | reported at lines 12-14 |
      | SQL built from user input | 38    | 55  | reported at lines 38-40 |
      | SQL built from user input | 72    | 75  | not reported            |
      | (empty)                   | 12    | 14  | not reported            |

  @id:analysis.response-parsing.003 @rule:analysis.response-parsing.unknown-labels-default @inferred @source:readthrough/engine.py#_clean_findings
  Scenario Outline: Unrecognised severity, confidence or category labels are replaced with defaults
    Given the model reports a finding with severity "<severity>", confidence "<confidence>" and category "<category>" from the injection lens
    When the operator runs the scan
    Then the finding is reported with severity "<shown_severity>"
    And its confidence is "<shown_confidence>"
    And its category is "<shown_category>"

    Examples:
      | severity     | confidence | category                 | shown_severity | shown_confidence | shown_category                    |
      | HIGH         | Low        | (a category of the lens) | high           | low              | (that category)                   |
      | catastrophic | sure       | made-up                  | medium         | medium           | (the lens's last listed category) |
