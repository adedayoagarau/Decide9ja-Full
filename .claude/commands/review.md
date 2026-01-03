# Code Review

Review the recent changes for quality and potential issues.

1. Run `git diff HEAD~1` to see the last commit's changes
2. Check for:
   - Security issues (hardcoded secrets, SQL injection, prompt injection)
   - Missing error handling
   - Nigerian language/locale edge cases
   - Type safety issues
   - Unused imports or dead code
3. Verify any new API endpoints have proper validation
4. Check that Claude/LLM calls use prompt guards
5. Report findings with file:line references
