---
name: write-tests
description: Write unit or integration tests for code. Use when user asks to test, add tests, or improve test coverage.
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - Bash
---

Write tests for $ARGUMENTS (file, function, or feature).

## Process

1. **Read the code** to understand what it does
2. **Check existing tests** — find test files, test framework, patterns used in the project
3. **Follow project conventions** — same framework, file naming, directory structure
4. **Write tests** covering:
   - Happy path (normal expected behavior)
   - Edge cases (empty input, null, boundaries)
   - Error cases (invalid input, failures)
5. **Run the tests** to make sure they pass

## Test Structure (Arrange-Act-Assert)

```
describe('functionName', () => {
  it('should do X when given Y', () => {
    // Arrange: set up test data
    // Act: call the function
    // Assert: check the result
  });
});
```

## Rules
- Match the project's existing test framework and style
- Test BEHAVIOR, not implementation details
- Each test should test ONE thing
- Use descriptive test names that explain the scenario
- Don't mock everything — prefer integration tests for complex logic
- Run tests after writing them to verify they pass
