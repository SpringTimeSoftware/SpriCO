# SpriCo Target Setup And Interactive Audit

## Purpose
This note explains, in a presentation-friendly way, how SpriCo was configured to audit retrieval-backed targets using the existing **Target Configuration** and **Interactive Audit** flow.

It focuses on:
- target setup
- provider-backed retrieval stores
- uploaded `.pdf` / `.md` source content
- Interactive Audit execution and scoring

It does **not** introduce any separate workflow. The same SpriCo audit UI is used throughout.

## Screenshots
- Target Configuration: [Target.jpg](../SS/Target.jpg)
- Interactive Audit: [Audit.jpg](../SS/Audit.jpg)

## Demo Setup Summary
The current demo uses three retrieval-backed targets visible in **Target Configuration**.

### 1. SpriCo Hospital Data
- Target Type: `OpenAIVectorStoreTarget`
- Model: `gpt-4.1`
- Endpoint: `https://api.openai.com/v1`
- Retrieval backend: OpenAI vector store
- Source content: hospital / patient document corpus uploaded as provider-managed files

### 2. SpriCo Legal Data
- Target Type: `OpenAIVectorStoreTarget`
- Model: `gpt-4.1`
- Endpoint: `https://api.openai.com/v1`
- Retrieval backend: OpenAI vector store
- Source content: Indian Supreme Court judgment PDFs uploaded into OpenAI retrieval storage

### 3. SpriCo HR Data
- Target Type: `GeminiFileSearchTarget`
- Model: `gemini-2.5-flash`
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/`
- Retrieval backend: Gemini File Search store
- Source content: HR markdown files uploaded into Gemini File Search storage

## How The Retrieval Stores Were Created
The key idea is simple: SpriCo does not maintain a separate local search product for this demo. Instead, it connects to provider-native retrieval stores that were created in advance.

### OpenAI Retrieval Setup
For the Legal and Hospital demos:
1. source documents were prepared as `.md` and `.pdf`  files or provider-supported file content
2. those files were uploaded into OpenAI-managed retrieval storage
3. an OpenAI vector store was created
4. the vector store ID was saved in SpriCo target configuration as `retrieval_store_id`
5. SpriCo used that configured target during Interactive Audit

### Gemini Retrieval Setup
For the HR demo:
1. HR source records were prepared as `.md` files
2. those markdown files were uploaded into a Gemini File Search store
3. the store ID looked like `fileSearchStores/...`
4. that store ID was saved in SpriCo target configuration as `retrieval_store_id`
5. SpriCo used the Gemini provider-specific runtime to query the configured store during Interactive Audit

## Why `.md` And `.pdf` Were Used
- `.pdf` works well for legal and document-style corpora where original file structure matters
- `.md` works well for HR-style structured text records because it keeps metadata and field structure easy to retrieve
- SpriCo stays provider-agnostic at the audit layer while allowing provider-native retrieval storage underneath

## How Target Configuration Works In SpriCo
In **Target Configuration**, each saved target stores:
- display name
- target type
- endpoint
- model name
- retrieval store ID
- encrypted API credential

This means the operator can switch between:
- OpenAI retrieval-backed targets
- Gemini retrieval-backed targets
- non-retrieval targets such as standard chat targets

without changing the audit workflow.

## Interactive Audit Flow
Once a target is active, the operator uses the standard **Interactive Audit** page.

### Step 1. Select Or Activate Target
From **Target Configuration**, the auditor activates the required target:
- Hospital retrieval target
- Legal retrieval target
- HR retrieval target

### Step 2. Open Interactive Audit
The active target name is shown at the top of the Interactive Audit screen.

Example from the screenshot:
- `New SpriCo Hospital Data (gpt-4.1)`

### Step 3. Ask A Prompt
The auditor sends a prompt directly through the normal chat-style interface.

Example:
- a privacy test
- a prompt injection attempt
- a document-grounded factual query

### Step 4. Retrieval Happens In The Provider Backend
The selected target sends the prompt to the configured retrieval store:
- OpenAI target uses OpenAI file search / vector store retrieval
- Gemini target uses Gemini File Search retrieval

### Step 5. The Final Answer Returns To SpriCo
Only the final assistant natural-language answer is shown in the main chat bubble.

### Step 6. Existing Evaluator Scores The Turn
SpriCo then applies the same existing audit logic already used elsewhere:
- verdict
- risk
- safety
- refusal
- outcome
- score

For retrieval-backed targets, SpriCo also preserves retrieval evidence and grounding metadata for audit interpretation.

## What The Screenshot Demonstrates
The Interactive Audit screenshot shows:
- the active retrieval-backed target in the header
- a user privacy-sensitive prompt
- a model refusal
- existing audit verdict output in the same turn card

This demonstrates that retrieval-backed targets are audited through the same SpriCo evaluation path as other targets, rather than through a special-case manual workflow.

## Presentation Message
The core message for the presentation is:

> SpriCo can audit retrieval-backed AI systems by connecting the existing audit platform to provider-managed retrieval stores. The operator configures the target once, activates it, and then uses the same Interactive Audit and scoring pipeline already used across the product.

## Short Talk Track
You can present it in this sequence:

1. We prepared the source corpus as provider-friendly files.
2. We uploaded those files into provider-native retrieval stores.
3. We registered each store in SpriCo as a normal auditable target.
4. We activated the target from Target Configuration.
5. We ran prompts through the normal Interactive Audit experience.
6. SpriCo preserved the retrieved evidence and scored the answer using the existing evaluator.

## One-Line Conclusion
SpriCo is not acting as a separate search product here; it is acting as the audit and evaluation layer on top of OpenAI- and Gemini-backed retrieval systems.
