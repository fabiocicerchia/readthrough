@domain:findings @area:corroboration @from:readthrough/merge
Feature: Corroborating findings
  Operators see when several passes flagged something at the same lines under different defect classes, so ranges worth reading in full stand out without distinct defects being merged away.

  Background:
    Given a scan of a repository has completed with raw findings from several passes

  @id:findings.corroboration.001 @rule:findings.corroboration.distinct-classes-stay-separate-but-corroborate @inferred @source:readthrough/merge.py#_annotate_colocation
  Scenario: Findings of different classes at the same lines stay separate and each counts the other's passes
    Given the injection lens reported sql-injection in "app/db.py" at lines 10-12
    And the logic lens reported logic-error in "app/db.py" at lines 11-13
    When the operator builds the report
    Then the report lists two findings, one per class
    And each finding shows "agreement 1" and "corroborated by 2 passes"
    And the sql-injection finding shows "Also flagged at these lines" with `logic-error`
