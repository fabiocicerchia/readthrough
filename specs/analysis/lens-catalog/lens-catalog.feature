@domain:analysis @area:lens-catalog @from:readthrough/lenses
Feature: Choosing review lenses
  Lets an operator see which focused review passes exist and pick which ones a scan runs, since the lens set is both the coverage and the biggest cost lever.

  Background:
    Given readthrough is installed

  @id:analysis.lens-catalog.002 @rule:analysis.lenses.catalog-listed @inferred @source:readthrough/lenses.py#LENSES
  Scenario Outline: The lens catalogue lists seven lenses and marks the four defaults
    When the operator lists the available lenses
    Then the line for lens "<lens>" shows the title "<title>"
    And that line is marked as enabled by default: <default>
    And the listing ends with "* = enabled by default"

    Examples:
      | lens        | title                                       | default |
      | injection   | Untrusted input and injection               | yes     |
      | authz       | Authentication, authorization and tenancy   | yes     |
      | secrets     | Secrets, crypto and configuration           | no      |
      | logic       | Invariants and business logic               | yes     |
      | errors      | Error handling, resources and failure modes | yes     |
      | concurrency | Concurrency and shared state                | no      |
      | data        | Data handling, boundaries and types         | no      |

  @id:analysis.lens-catalog.003 @rule:analysis.lenses.default-set @inferred @source:readthrough/lenses.py#DEFAULT_LENSES
  Scenario: A scan without a lens choice runs injection, authz, logic and errors
    Given a repository the operator has not scanned before
    When the operator scans the repository without choosing lenses
    Then the report header reads "lenses: injection, authz, logic, errors"
    And the console reports "4 lenses x 1 repeat(s)"

  @id:analysis.lens-catalog.004 @rule:analysis.lenses.unknown-refused @verified @source:readthrough/cli.py#cmd_scan @test:tests/test_smoke.py#test_unknown_lens_is_rejected_before_spending_anything
  Scenario Outline: A scan naming an unknown lens is refused before any work starts
    When the operator scans a repository with lenses "<requested>"
    Then the scan exits with status 2
    And the error output reads "unknown lenses: <unknown>"
    And the error output lists the available lenses "injection, authz, secrets, logic, errors, concurrency, data"
    And no pass is run and no API key is required

    Examples:
      | requested      | unknown   |
      | nonsense       | nonsense  |
      | injection,sqli | sqli      |
      | Injection      | Injection |

  @id:analysis.lens-catalog.005 @rule:analysis.lenses.empty-selection-runs-nothing @inferred @source:readthrough/cli.py#cmd_scan @questionable
  Scenario: An empty lens choice produces a scan that reviews nothing yet succeeds
    Given a repository with one eligible file
    When the operator scans the repository with an empty lens list
    Then the console reports "0 passes to run (0 lenses x 1 repeat(s))" and "nothing to do"
    And the report header lists no lenses
    And the scan exits with status 0
