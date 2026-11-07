@domain:findings @area:deduplication @from:readthrough/merge
Feature: Merging duplicate findings
  Operators triaging an audit see each defect once, however many lenses, repeats or overlapping chunks reported it, so the report reads as a list of defects rather than a list of model replies.

  Background:
    Given Given a scan of a repository has completed with raw findings from several passes

  @id:findings.deduplication.001 @rule:findings.deduplication.nearby-same-class-findings-merge @inferred @source:readthrough/merge.py#merge_findings
  Scenario Outline: Findings of the same class in the same file at overlapping or nearby lines become one finding
    Given a pass reported a "<class>" finding in "app/db.py" at lines <first>
    And another pass reported a "<class>" finding in "app/db.py" at lines <second>
    When the operator builds the report
    Then the report lists <count> "<class>" finding(s) in "app/db.py"
    And the merged finding, when there is one, spans lines <span>

    Examples:
      | class         | first | second | count | span  |
      | sql-injection | 10-12 | 11-14  | 1     | 10-14 |
      | sql-injection | 10-12 | 15-18  | 1     | 10-18 |
      | sql-injection | 10-12 | 19-20  | 2     | n/a   |
      | sql-injection | 10-12 | 3-4    | 1     | 3-12  |

  @id:findings.deduplication.002 @rule:findings.deduplication.category-aliases-share-a-class @inferred @source:readthrough/merge.py#_family
  Scenario Outline: Different names for the same defect are merged under one defect class
    Given the authorization lens reported "<first>" in "app/views.py" at lines 40-42
    And the logic lens reported "<second>" in "app/views.py" at lines 41-44
    When the operator builds the report
    Then the report lists one finding at "app/views.py":40-44
    And the finding is shown with class "<class>"

    Examples:
      | first                    | second         | class            |
      | idor                     | missing-authz  | access-control   |
      | missing-authn            | tenancy-leak   | access-control   |
      | race-condition           | toctou         | concurrency      |
      | missing-input-validation | type-confusion | input-validation |

  @id:findings.deduplication.003 @rule:findings.deduplication.merged-finding-keeps-worst-case @inferred @source:readthrough/merge.py#_collapse @questionable
  Scenario: A merged finding carries the most severe rating, the highest confidence and the fullest wording any pass gave
    Given one pass reported a finding at "app/db.py":10-12 with severity high, confidence low and a short explanation
    And another pass reported the same class at "app/db.py":11-13 with severity medium, confidence high and a longer explanation and a suggested fix
    When the operator builds the report
    Then the merged finding has severity high
    And the merged finding has confidence high
    And the merged finding shows the longer explanation and the suggested fix
    And the merged finding lists both passes' titles as variants

  @id:findings.deduplication.004 @rule:findings.deduplication.agreement-counts-independent-passes @inferred @source:readthrough/merge.py#_collapse
  Scenario: Agreement counts independent passes, not repeated reports from one pass
    Given the scan ran lenses injection and logic with 2 repeats
    And the injection lens reported the same defect from two overlapping chunks in its first repeat
    And the logic lens reported it in its second repeat
    When the operator builds the report
    Then the finding shows "agreement 2/4"
    And the finding shows it was found by injection and logic

  @id:findings.deduplication.005 @rule:findings.deduplication.fingerprint-follows-file-class-and-span @inferred @source:readthrough/merge.py#fingerprint @questionable
  Scenario: A finding keeps its fingerprint only while its file, class and line span stay the same
    Given a finding in "app/db.py" of class sql-injection spans lines 10-14 and has a verification verdict
    And a later pass on the same scan reports the same class at lines 16-20
    When the operator builds the report
    Then the finding now spans lines 10-20 and shows a different fingerprint
    And the earlier verification verdict is no longer shown on it
