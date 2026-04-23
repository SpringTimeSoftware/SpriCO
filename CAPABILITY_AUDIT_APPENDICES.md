# PyRIT Capability Audit - Appendices

## A. Supported Target Types

- OpenAIChatTarget (pyrit/prompt_target/openai/openai_chat_target.py)
- AzureMLChatTarget (pyrit/prompt_target/azure_ml_chat_target.py)
- HuggingFaceChatTarget (pyrit/prompt_target/hugging_face/hugging_face_chat_target.py)
- OpenAIRealtimeTarget (pyrit/prompt_target/openai/openai_realtime_target.py)
- WebSocketCopilotTarget (pyrit/prompt_target/websocket_copilot_target.py)
- PlaywrightCopilotTarget (pyrit/prompt_target/playwright_copilot_target.py)
- OpenAICompletionTarget (pyrit/prompt_target/openai/openai_completion_target.py)
- HuggingFaceEndpointTarget (pyrit/prompt_target/hugging_face/hugging_face_endpoint_target.py)
- HTTPTarget (pyrit/prompt_target/http_target/http_target.py)
- OpenAIImageTarget (pyrit/prompt_target/openai/openai_image_target.py)
- OpenAITTSTarget (pyrit/prompt_target/openai/openai_tts_target.py)
- OpenAIVideoTarget (pyrit/prompt_target/openai/openai_video_target.py)
- GandalfTarget (pyrit/prompt_target/gandalf_target.py)
- PromptShieldTarget (pyrit/prompt_target/prompt_shield_target.py)
- PlaywrightTarget (pyrit/prompt_target/playwright_target.py)
- TextTarget (pyrit/prompt_target/text_target.py)
- RPCClient (pyrit/prompt_target/rpc_client.py)
- AzureBlobStorageTarget (pyrit/prompt_target/azure_blob_storage_target.py)
- CrucibleTarget (pyrit/prompt_target/crucible_target.py)

## B. Attack Strategies

- PromptSendingAttack
- SkeletonKeyAttack
- FlipAttack
- RolePlayAttack
- ManyShotJailbreakAttack
- ContextComplianceAttack
- RedTeamingAttack
- CrescendoAttack
- TreeOfAttacksWithPruningAttack
- ChunkedRequestAttack
- MultiPromptSendingAttack

## C. Scorers

- SelfAskTrueFalseScorer
- SelfAskRefusalScorer
- SelfAskCategoryScorer
- SelfAskQuestionAnswerScorer
- SelfAskGeneralTrueFalseScorer
- SubStringScorer
- DecodingScorer
- FloatScaleThresholdScorer
- MarkdownInjectionScorer
- GandalfScorer
- PromptShieldScorer
- AudioTrueFalseScorer
- VideoTrueFalseScorer
- BatchScorer
- TrueFalseCompositeScorer
- HumanScorer

## D. Memory Implementations

- SqliteMemory
- AzureSqlMemory
- InMemoryMemory

## E. Frontend Pages / Components

- App.tsx
- ChatWindow.tsx
- ChatInputArea.tsx
- MessageList.tsx
- ConversationPanel.tsx
- TargetConfig.tsx
- TargetTable.tsx
- CreateTargetDialog.tsx
- AttackHistory.tsx
- AttackTable.tsx
- HistoryFiltersBar.tsx
- HistoryPagination.tsx
- LabelsBar.tsx
- ConnectionBanner.tsx
- ErrorBoundary.tsx

## F. Scenario Types

- FoundryScenario
- AIRT content_harms
- AIRT cyber
- AIRT jailbreak
- AIRT leakage
- AIRT psychosocial
- AIRT scam
- Garak section

## G. CLI Commands

- pyrit_backend (pyrit/cli/pyrit_backend.py)
- pyrit_shell (pyrit/cli/pyrit_shell.py)
- pyrit_scan (pyrit/cli/pyrit_scan.py)

## H. Quick local demo steps

1. pyrit_backend --database InMemory
2. cd frontend && npm run dev
3. pyrit_shell or pyrit_scan
