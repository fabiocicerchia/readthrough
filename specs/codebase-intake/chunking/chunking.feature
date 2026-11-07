@domain:codebase-intake @area:chunking @from:readthrough/discover
Feature: Reviewing large files in overlapping windows
  Lets the operator audit long files without losing defects that straddle a window boundary, with findings pointing at real line numbers.

  @id:codebase-intake.chunking.001 @rule:intake.chunking.overlapping-windows @inferred @source:readthrough/discover.py#chunk_file
  Scenario Outline: A file longer than the window is reviewed in overlapping windows that keep real line numbers
    Given an eligible file "app/service.py" of <lines> lines
    When the operator scans with --chunk-lines <window> and --overlap <overlap>
    Then each lens reviews "app/service.py" as windows covering lines <windows>

    Examples:
      | lines | window | overlap | windows                 |
      | 300   | 350    | 60      | 1-300                   |
      | 800   | 350    | 60      | 1-350, 291-640, 581-800 |
      | 800   | 400    | 0       | 1-400, 401-800          |
