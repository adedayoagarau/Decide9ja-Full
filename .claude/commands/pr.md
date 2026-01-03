# Create Pull Request

Create a pull request for the current branch.

1. Check current branch and ensure it's not main/master
2. Run `git status` to verify all changes are committed
3. Push the branch to origin if not already pushed
4. Create a PR using `gh pr create` with:
   - Clear title summarizing the changes
   - Description with:
     - Summary of changes (bullet points)
     - Any breaking changes
     - Testing done
5. Return the PR URL
