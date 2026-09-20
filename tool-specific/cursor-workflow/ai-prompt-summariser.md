# AI Interaction Summarizer

Summarize AI-assisted development interactions for the activity specified in the invocation.

## Inputs

- **Activity:** Task or component to summarize.
- **Implementation:** Relevant files/directories.
- **Context:** Supporting project documents.
- **Output:** Destination file under `ai-prompts/`.

## Source and Scope

- Use the current Cursor conversation as the source of truth.
- Include only interactions relevant to the specified activity.
- Use referenced files for context and verification, not to reconstruct missing conversations.
- If earlier interactions are unavailable, acknowledge the gap rather than inventing history.

## Summary Structure

For initial implementation:

- **Prompt / Request:** What I asked Cursor to implement.
- **Cursor Output:** What Cursor generated or suggested.
- **Review / Decision:** What I accepted, changed or rejected, and why.

For refinements or fixes:

- **Reason for Refinement:** Issue or feedback that triggered the change.
- **Changes Requested:** What I explicitly asked to change.
- **Cursor Implementation:** What Cursor changed in response.
- **Review / Decision:** Outcome and reasoning, when available.

## Attribution Rules

- Distinguish my engineering decisions from Cursor's independent suggestions.
- Never present user-requested changes as Cursor's suggestions.
- Preserve meaningful accepted, modified and rejected suggestions.
- Do not invent prompts, decisions, debugging events or test results.

## Output Rules

- Create or update the specified output file chronologically.
- Preserve existing factual entries; avoid duplication.
- Keep meaningful interactions concise and specific.
- Include testing/debugging only when supported by the conversation.
- Do not claim validation passed unless it was executed.
- Do not document this summarization request itself.
- Do not modify implementation or project documentation files.