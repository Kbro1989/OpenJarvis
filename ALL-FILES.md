# OpenJarvis ALL-FILES.md
# Complete .md manifest for NodeTester/runtime endpoint health-test seed inject
# Total: 135 files

## Manifest

001| .github\pull_request_template.md
002| .hermes\kingwen\kw_progressive_map.md
003| ALL-FILES.md
004| blueprints\jarvis-logical-tooling-runtime.md
005| blueprints\jarvis-slash-parity.md
006| CHANGELOG.md
007| CODE_OF_CONDUCT.md
008| configs\openjarvis\prompts\personas\jarvis.md
009| configs\openjarvis\prompts\personas\neutral.md
010| CONTRIBUTING.md
011| deploy\windows\README.md
012| docs\architecture\agents.md
013| docs\architecture\channels.md
014| docs\architecture\design-principles.md
015| docs\architecture\engine.md
016| docs\architecture\intelligence.md
017| docs\architecture\learning.md
018| docs\architecture\memory.md
019| docs\architecture\overview.md
020| docs\architecture\query-flow.md
021| docs\architecture\security.md
022| docs\architecture\skills.md
023| docs\assets\showcase\README.md
024| docs\deployment\api-server.md
025| docs\deployment\docker.md
026| docs\deployment\index.md
027| docs\deployment\launchd.md
028| docs\deployment\systemd.md
029| docs\design\2026-05-05-apple-silicon-pearl-mining-design.md
030| docs\design\2026-05-05-apple-silicon-pearl-mining-plan-v1.md
031| docs\design\2026-05-05-pearl-coordination-discussion-draft.md
032| docs\design\2026-05-05-vllm-pearl-mining-integration-design.md
033| docs\design\2026-05-05-vllm-pearl-mining-integration-plan.md
034| docs\desktop-auto-update.md
035| docs\development\contributing.md
036| docs\development\mining-nvidia-validation.md
037| docs\development\mining.md
038| docs\development\pearl-model-enablement.md
039| docs\development\release-checklist.md
040| docs\development\roadmap.md
041| docs\downloads.md
042| docs\getting-started\configuration.md
043| docs\getting-started\install.md
044| docs\getting-started\installation.md
045| docs\getting-started\linux.md
046| docs\getting-started\macos.md
047| docs\getting-started\quickstart.md
048| docs\getting-started\snippets.md
049| docs\getting-started\snowflake-guide.md
050| docs\getting-started\windows-native.md
051| docs\getting-started\wsl2.md
052| docs\includes\abbreviations.md
053| docs\index.md
054| docs\leaderboard.md
055| docs\learning\ace.md
056| docs\oracle-voice-emotion-spec.md
057| docs\rsmd-avatar-integration-map.md
058| docs\rsmv-decoder-audit-2026-07-19.md
059| docs\showcase\coding-assistant.md
060| docs\showcase\CONTRIBUTING.md
061| docs\showcase\cost-savings.md
062| docs\showcase\discord-companion.md
063| docs\showcase\index.md
064| docs\showcase\morning-brief.md
065| docs\showcase\persistent-memory.md
066| docs\telemetry.md
067| docs\temporal-domain-classification.md
068| docs\testing\agent-qa-runbook.md
069| docs\tutorials\code-companion.md
070| docs\tutorials\deep-research.md
071| docs\tutorials\index.md
072| docs\tutorials\messaging-hub.md
073| docs\tutorials\scheduled-ops.md
074| docs\tutorials\skills-workflow.md
075| docs\user-guide\agents.md
076| docs\user-guide\benchmarks.md
077| docs\user-guide\channels-and-connectors.md
078| docs\user-guide\channels.md
079| docs\user-guide\chat-simple.md
080| docs\user-guide\cli.md
081| docs\user-guide\code-assistant.md
082| docs\user-guide\deep-research.md
083| docs\user-guide\evaluations.md
084| docs\user-guide\llm-guided-spec-search.md
085| docs\user-guide\mcp-external-servers.md
086| docs\user-guide\memory.md
087| docs\user-guide\mining-apple-silicon.md
088| docs\user-guide\mining.md
089| docs\user-guide\morning-digest.md
090| docs\user-guide\pearl.md
091| docs\user-guide\python-sdk.md
092| docs\user-guide\scheduled-monitor.md
093| docs\user-guide\scheduler.md
094| docs\user-guide\security.md
095| docs\user-guide\skills.md
096| docs\user-guide\telemetry.md
097| docs\user-guide\tools.md
098| examples\browser_assistant\README.md
099| examples\code_companion\README.md
100| examples\daily_digest\README.md
101| examples\deep_research\README.md
102| examples\doc_qa\README.md
103| examples\messaging_hub\README.md
104| examples\multi_model_router\README.md
105| examples\scheduled_ops\README.md
106| examples\security_scanner\README.md
107| jarvis-system-avatar-research.md
108| king_wen_codebasemap.md
109| kingwen_oracle_wire_extracted\ORACLE_WIRE.md
110| kingwen_service_extracted\INTEGRATION.md
111| learn_capture_extracted\LEARN_WIRE.md
112| openjarvis_blueprints_v2 (1)_extracted\INTEGRATION_v2.md
113| openjarvis_blueprints_v2_extracted\INTEGRATION_v2.md
114| OPENJARVIS_IMPLEMENTATION_CHECKLIST.md
115| README.md
116| REVIEW.md
117| scripts\pearl\README.md
118| skills\kingwen-emotion-voice\SKILL.md
119| skills\kingwen-voice-bridge\SKILL.md
120| src\openjarvis\slash\CHAT_CMD_WIRE.md
121| src\openjarvis\agents\hybrid\README.md
122| src\openjarvis\agents\hybrid\skillorchestra\README.md
123| src\openjarvis\recipes\data\operators\correspondent_prompt.md
124| src\openjarvis\recipes\data\operators\openjarvis_twitter_bot_prompt.md
125| src\openjarvis\recipes\data\operators\researcher_prompt.md
126| src\openjarvis\recipes\data\operators\sentinel_prompt.md
127| tests\fixtures\docs\channels.md
128| tests\fixtures\docs\engines.md
129| tests\fixtures\docs\hardware.md
130| tests\fixtures\docs\memory.md
131| tests\install\cases\missing-git.md
132| tests\install\cases\README.md
133| tests\install\cases\run-as-root.md
134| tests\mining\fixtures\README.md
135| tools\pearl-reference-oracle\README.md

## Runtime Endpoint Health Test Seed Inject Sites
# Derived from manifest above.
# Each path maps to a neurological map inject site by first path segment.
# endpoint_seed = sha256:<first16(path)>; health probe = HTTP/health-doc-check

| path | category | endpoint_seed | health_probe |
|------|----------|---------------|--------------|
| .github\pull_request_template.md | .github\pull_request_template.md | sha256:f5141ac606195b67 | HTTP/health-doc-check |
| .hermes\kingwen\kw_progressive_map.md | .hermes\kingwen\kw_progressive_map.md | sha256:3c6ae9751bb5c8bf | HTTP/health-doc-check |
| ALL-FILES.md | ALL-FILES.md | sha256:35744e5abc639364 | HTTP/health-doc-check |
| blueprints\jarvis-logical-tooling-runtime.md | blueprints\jarvis-logical-tooling-runtime.md | sha256:b34c0bad3840d453 | HTTP/health-doc-check |
| blueprints\jarvis-slash-parity.md | blueprints\jarvis-slash-parity.md | sha256:c33cb631f14efe8e | HTTP/health-doc-check |
| CHANGELOG.md | CHANGELOG.md | sha256:06572a96a58dc510 | HTTP/health-doc-check |
| CODE_OF_CONDUCT.md | CODE_OF_CONDUCT.md | sha256:ffdbe3a1e7ee93ca | HTTP/health-doc-check |
| configs\openjarvis\prompts\personas\jarvis.md | configs\openjarvis\prompts\personas\jarvis.md | sha256:699da58c5aa46704 | HTTP/health-doc-check |
| configs\openjarvis\prompts\personas\neutral.md | configs\openjarvis\prompts\personas\neutral.md | sha256:dbadf8a4f02dff25 | HTTP/health-doc-check |
| CONTRIBUTING.md | CONTRIBUTING.md | sha256:eca12c0a30e25b4b | HTTP/health-doc-check |
| deploy\windows\README.md | deploy\windows\README.md | sha256:102dd331570e813e | HTTP/health-doc-check |
| docs\architecture\agents.md | docs\architecture\agents.md | sha256:57080beebe3aeb69 | HTTP/health-doc-check |
| docs\architecture\channels.md | docs\architecture\channels.md | sha256:5bc3b0d04947c817 | HTTP/health-doc-check |
| docs\architecture\design-principles.md | docs\architecture\design-principles.md | sha256:66086e340f5efa4f | HTTP/health-doc-check |
| docs\architecture\engine.md | docs\architecture\engine.md | sha256:1d2a8dbcd92ef3b0 | HTTP/health-doc-check |
| docs\architecture\intelligence.md | docs\architecture\intelligence.md | sha256:44d0e4eb8eea983e | HTTP/health-doc-check |
| docs\architecture\learning.md | docs\architecture\learning.md | sha256:ff91bb69a73c05de | HTTP/health-doc-check |
| docs\architecture\memory.md | docs\architecture\memory.md | sha256:9c5bb251f63e85d2 | HTTP/health-doc-check |
| docs\architecture\overview.md | docs\architecture\overview.md | sha256:e7996b64a3f3bb5f | HTTP/health-doc-check |
| docs\architecture\query-flow.md | docs\architecture\query-flow.md | sha256:beb61738ca93bc05 | HTTP/health-doc-check |
| docs\architecture\security.md | docs\architecture\security.md | sha256:802af9d0b8009c54 | HTTP/health-doc-check |
| docs\architecture\skills.md | docs\architecture\skills.md | sha256:75592aa92bf54b6a | HTTP/health-doc-check |
| docs\assets\showcase\README.md | docs\assets\showcase\README.md | sha256:d3c148685d6a983e | HTTP/health-doc-check |
| docs\deployment\api-server.md | docs\deployment\api-server.md | sha256:58774a9369834401 | HTTP/health-doc-check |
| docs\deployment\docker.md | docs\deployment\docker.md | sha256:e3ffc8007fb215a4 | HTTP/health-doc-check |
| docs\deployment\index.md | docs\deployment\index.md | sha256:634598b2ae853ea6 | HTTP/health-doc-check |
| docs\deployment\launchd.md | docs\deployment\launchd.md | sha256:7201b48dd5511237 | HTTP/health-doc-check |
| docs\deployment\systemd.md | docs\deployment\systemd.md | sha256:d64a14dc4a11415c | HTTP/health-doc-check |
| docs\design\2026-05-05-apple-silicon-pearl-mining-design.md | docs\design\2026-05-05-apple-silicon-pearl-mining-design.md | sha256:bb97ea4573a74100 | HTTP/health-doc-check |
| docs\design\2026-05-05-apple-silicon-pearl-mining-plan-v1.md | docs\design\2026-05-05-apple-silicon-pearl-mining-plan-v1.md | sha256:595030af725620c1 | HTTP/health-doc-check |
| docs\design\2026-05-05-pearl-coordination-discussion-draft.md | docs\design\2026-05-05-pearl-coordination-discussion-draft.md | sha256:3a3e07e133b0978d | HTTP/health-doc-check |
| docs\design\2026-05-05-vllm-pearl-mining-integration-design.md | docs\design\2026-05-05-vllm-pearl-mining-integration-design.md | sha256:4f759cfb0989c08e | HTTP/health-doc-check |
| docs\design\2026-05-05-vllm-pearl-mining-integration-plan.md | docs\design\2026-05-05-vllm-pearl-mining-integration-plan.md | sha256:10301ce65318f3fd | HTTP/health-doc-check |
| docs\desktop-auto-update.md | docs\desktop-auto-update.md | sha256:9b0142fe203375bf | HTTP/health-doc-check |
| docs\development\contributing.md | docs\development\contributing.md | sha256:eaadd5db02e5f3c5 | HTTP/health-doc-check |
| docs\development\mining-nvidia-validation.md | docs\development\mining-nvidia-validation.md | sha256:c93c14e3927ebc6a | HTTP/health-doc-check |
| docs\development\mining.md | docs\development\mining.md | sha256:e69d33f87f74edc5 | HTTP/health-doc-check |
| docs\development\pearl-model-enablement.md | docs\development\pearl-model-enablement.md | sha256:336fa3d2a11f6b39 | HTTP/health-doc-check |
| docs\development\release-checklist.md | docs\development\release-checklist.md | sha256:806274fb8bf2860b | HTTP/health-doc-check |
| docs\development\roadmap.md | docs\development\roadmap.md | sha256:7f0fed1a1ebd71e3 | HTTP/health-doc-check |
| docs\downloads.md | docs\downloads.md | sha256:dc2ea8e3726fb412 | HTTP/health-doc-check |
| docs\getting-started\configuration.md | docs\getting-started\configuration.md | sha256:f5fc1a9cd9e6a7e8 | HTTP/health-doc-check |
| docs\getting-started\install.md | docs\getting-started\install.md | sha256:5193411f821744fe | HTTP/health-doc-check |
| docs\getting-started\installation.md | docs\getting-started\installation.md | sha256:b5c8d8126a77d7db | HTTP/health-doc-check |
| docs\getting-started\linux.md | docs\getting-started\linux.md | sha256:0e85be2234aa18bc | HTTP/health-doc-check |
| docs\getting-started\macos.md | docs\getting-started\macos.md | sha256:36eab410f39e327a | HTTP/health-doc-check |
| docs\getting-started\quickstart.md | docs\getting-started\quickstart.md | sha256:1a836b486c81439d | HTTP/health-doc-check |
| docs\getting-started\snippets.md | docs\getting-started\snippets.md | sha256:4b16fa2b1f72c46d | HTTP/health-doc-check |
| docs\getting-started\snowflake-guide.md | docs\getting-started\snowflake-guide.md | sha256:7a49d36c755d65d4 | HTTP/health-doc-check |
| docs\getting-started\windows-native.md | docs\getting-started\windows-native.md | sha256:8d442c961ed0d5c9 | HTTP/health-doc-check |
| docs\getting-started\wsl2.md | docs\getting-started\wsl2.md | sha256:ad1cad43a9c13390 | HTTP/health-doc-check |
| docs\includes\abbreviations.md | docs\includes\abbreviations.md | sha256:8ca53a51e1e0e076 | HTTP/health-doc-check |
| docs\index.md | docs\index.md | sha256:374f3f4597694a41 | HTTP/health-doc-check |
| docs\leaderboard.md | docs\leaderboard.md | sha256:2e53afcff552f0be | HTTP/health-doc-check |
| docs\learning\ace.md | docs\learning\ace.md | sha256:a9b10180c41b7235 | HTTP/health-doc-check |
| docs\oracle-voice-emotion-spec.md | docs\oracle-voice-emotion-spec.md | sha256:f67b01518ba0738a | HTTP/health-doc-check |
| docs\rsmd-avatar-integration-map.md | docs\rsmd-avatar-integration-map.md | sha256:28c47d82e63f4346 | HTTP/health-doc-check |
| docs\rsmv-decoder-audit-2026-07-19.md | docs\rsmv-decoder-audit-2026-07-19.md | sha256:926689ebd24d5615 | HTTP/health-doc-check |
| docs\showcase\coding-assistant.md | docs\showcase\coding-assistant.md | sha256:6813371f33a38acb | HTTP/health-doc-check |
| docs\showcase\CONTRIBUTING.md | docs\showcase\CONTRIBUTING.md | sha256:fdf5b6914ec9c929 | HTTP/health-doc-check |
| docs\showcase\cost-savings.md | docs\showcase\cost-savings.md | sha256:77361d41faf4cb3d | HTTP/health-doc-check |
| docs\showcase\discord-companion.md | docs\showcase\discord-companion.md | sha256:db60bbfceb534f02 | HTTP/health-doc-check |
| docs\showcase\index.md | docs\showcase\index.md | sha256:4423458ceb2946b0 | HTTP/health-doc-check |
| docs\showcase\morning-brief.md | docs\showcase\morning-brief.md | sha256:d992e97af1709184 | HTTP/health-doc-check |
| docs\showcase\persistent-memory.md | docs\showcase\persistent-memory.md | sha256:1cdbbec4931cf0c1 | HTTP/health-doc-check |
| docs\telemetry.md | docs\telemetry.md | sha256:9c5d13066e96511d | HTTP/health-doc-check |
| docs\temporal-domain-classification.md | docs\temporal-domain-classification.md | sha256:f4d06d30c9fb0cd5 | HTTP/health-doc-check |
| docs\testing\agent-qa-runbook.md | docs\testing\agent-qa-runbook.md | sha256:7a717c9608c2a11a | HTTP/health-doc-check |
| docs\tutorials\code-companion.md | docs\tutorials\code-companion.md | sha256:095caa854740fc8c | HTTP/health-doc-check |
| docs\tutorials\deep-research.md | docs\tutorials\deep-research.md | sha256:ee3cc34b567958da | HTTP/health-doc-check |
| docs\tutorials\index.md | docs\tutorials\index.md | sha256:f35950ec6894f6d2 | HTTP/health-doc-check |
| docs\tutorials\messaging-hub.md | docs\tutorials\messaging-hub.md | sha256:6ee7f690292dd3a1 | HTTP/health-doc-check |
| docs\tutorials\scheduled-ops.md | docs\tutorials\scheduled-ops.md | sha256:261ec7ea79a6ab9a | HTTP/health-doc-check |
| docs\tutorials\skills-workflow.md | docs\tutorials\skills-workflow.md | sha256:c46a41e94339fae8 | HTTP/health-doc-check |
| docs\user-guide\agents.md | docs\user-guide\agents.md | sha256:98b9ee9f2c3a1988 | HTTP/health-doc-check |
| docs\user-guide\benchmarks.md | docs\user-guide\benchmarks.md | sha256:b65505a0294a0dfe | HTTP/health-doc-check |
| docs\user-guide\channels-and-connectors.md | docs\user-guide\channels-and-connectors.md | sha256:64c9044b02d669be | HTTP/health-doc-check |
| docs\user-guide\channels.md | docs\user-guide\channels.md | sha256:95cdacd8d284551c | HTTP/health-doc-check |
| docs\user-guide\chat-simple.md | docs\user-guide\chat-simple.md | sha256:943cad60bd5b9de1 | HTTP/health-doc-check |
| docs\user-guide\cli.md | docs\user-guide\cli.md | sha256:bde22a14f9b6d577 | HTTP/health-doc-check |
| docs\user-guide\code-assistant.md | docs\user-guide\code-assistant.md | sha256:08d64e77a3065e95 | HTTP/health-doc-check |
| docs\user-guide\deep-research.md | docs\user-guide\deep-research.md | sha256:dfce689fbc190b8a | HTTP/health-doc-check |
| docs\user-guide\evaluations.md | docs\user-guide\evaluations.md | sha256:65deaeb04b194462 | HTTP/health-doc-check |
| docs\user-guide\llm-guided-spec-search.md | docs\user-guide\llm-guided-spec-search.md | sha256:6de9e699c9c57f71 | HTTP/health-doc-check |
| docs\user-guide\mcp-external-servers.md | docs\user-guide\mcp-external-servers.md | sha256:37920be44dffb7c6 | HTTP/health-doc-check |
| docs\user-guide\memory.md | docs\user-guide\memory.md | sha256:399a46e07cb3d72a | HTTP/health-doc-check |
| docs\user-guide\mining-apple-silicon.md | docs\user-guide\mining-apple-silicon.md | sha256:70c8ba2829d30c82 | HTTP/health-doc-check |
| docs\user-guide\mining.md | docs\user-guide\mining.md | sha256:00a04e016b0c6983 | HTTP/health-doc-check |
| docs\user-guide\morning-digest.md | docs\user-guide\morning-digest.md | sha256:5bbbce0fb6ed7126 | HTTP/health-doc-check |
| docs\user-guide\pearl.md | docs\user-guide\pearl.md | sha256:21b58f53d86da266 | HTTP/health-doc-check |
| docs\user-guide\python-sdk.md | docs\user-guide\python-sdk.md | sha256:4e75296508b30fab | HTTP/health-doc-check |
| docs\user-guide\scheduled-monitor.md | docs\user-guide\scheduled-monitor.md | sha256:da4c536ce772d3f7 | HTTP/health-doc-check |
| docs\user-guide\scheduler.md | docs\user-guide\scheduler.md | sha256:0ea4dc1bffbbf8e9 | HTTP/health-doc-check |
| docs\user-guide\security.md | docs\user-guide\security.md | sha256:ec97e3c7af324cae | HTTP/health-doc-check |
| docs\user-guide\skills.md | docs\user-guide\skills.md | sha256:064b1c94d6719f98 | HTTP/health-doc-check |
| docs\user-guide\telemetry.md | docs\user-guide\telemetry.md | sha256:9ffab4a014a84a52 | HTTP/health-doc-check |
| docs\user-guide\tools.md | docs\user-guide\tools.md | sha256:637bba9cdf678098 | HTTP/health-doc-check |
| examples\browser_assistant\README.md | examples\browser_assistant\README.md | sha256:2f26cc2f83aaa5eb | HTTP/health-doc-check |
| examples\code_companion\README.md | examples\code_companion\README.md | sha256:b3f359eb26c8e2b3 | HTTP/health-doc-check |
| examples\daily_digest\README.md | examples\daily_digest\README.md | sha256:a41519c59265b44f | HTTP/health-doc-check |
| examples\deep_research\README.md | examples\deep_research\README.md | sha256:178b35bf206e8068 | HTTP/health-doc-check |
| examples\doc_qa\README.md | examples\doc_qa\README.md | sha256:55e0187b01c8b758 | HTTP/health-doc-check |
| examples\messaging_hub\README.md | examples\messaging_hub\README.md | sha256:9015837087d4d292 | HTTP/health-doc-check |
| examples\multi_model_router\README.md | examples\multi_model_router\README.md | sha256:b9b91783520341ad | HTTP/health-doc-check |
| examples\scheduled_ops\README.md | examples\scheduled_ops\README.md | sha256:109824a192fae5f3 | HTTP/health-doc-check |
| examples\security_scanner\README.md | examples\security_scanner\README.md | sha256:0d79783fc8a912c2 | HTTP/health-doc-check |
| jarvis-system-avatar-research.md | jarvis-system-avatar-research.md | sha256:665a3cdb539829a3 | HTTP/health-doc-check |
| king_wen_codebasemap.md | king_wen_codebasemap.md | sha256:f96091ed978a2592 | HTTP/health-doc-check |
| kingwen_oracle_wire_extracted\ORACLE_WIRE.md | kingwen_oracle_wire_extracted\ORACLE_WIRE.md | sha256:5bf63f61c42c276f | HTTP/health-doc-check |
| kingwen_service_extracted\INTEGRATION.md | kingwen_service_extracted\INTEGRATION.md | sha256:41adde3909eebed0 | HTTP/health-doc-check |
| learn_capture_extracted\LEARN_WIRE.md | learn_capture_extracted\LEARN_WIRE.md | sha256:2a66211925bfa3d2 | HTTP/health-doc-check |
| openjarvis_blueprints_v2 (1)_extracted\INTEGRATION_v2.md | openjarvis_blueprints_v2 (1)_extracted\INTEGRATION_v2.md | sha256:dc7d4be7e256332b | HTTP/health-doc-check |
| openjarvis_blueprints_v2_extracted\INTEGRATION_v2.md | openjarvis_blueprints_v2_extracted\INTEGRATION_v2.md | sha256:72e1aeb475fb49fa | HTTP/health-doc-check |
| OPENJARVIS_IMPLEMENTATION_CHECKLIST.md | OPENJARVIS_IMPLEMENTATION_CHECKLIST.md | sha256:f2310dd3ff2efcc7 | HTTP/health-doc-check |
| README.md | README.md | sha256:b335630551682c19 | HTTP/health-doc-check |
| REVIEW.md | REVIEW.md | sha256:4b776210ba07a121 | HTTP/health-doc-check |
| scripts\pearl\README.md | scripts\pearl\README.md | sha256:9c20c556b3520704 | HTTP/health-doc-check |
| skills\kingwen-emotion-voice\SKILL.md | skills\kingwen-emotion-voice\SKILL.md | sha256:c5caba5b8a1566ca | HTTP/health-doc-check |
| skills\kingwen-voice-bridge\SKILL.md | skills\kingwen-voice-bridge\SKILL.md | sha256:abf2afcf5bb8cf99 | HTTP/health-doc-check |
| src\openjarvis\slash\CHAT_CMD_WIRE.md | src\openjarvis\slash\CHAT_CMD_WIRE.md | sha256:afc3df4e929cf970 | HTTP/health-doc-check |
| src\openjarvis\agents\hybrid\README.md | src\openjarvis\agents\hybrid\README.md | sha256:68f685e818da64cd | HTTP/health-doc-check |
| src\openjarvis\agents\hybrid\skillorchestra\README.md | src\openjarvis\agents\hybrid\skillorchestra\README.md | sha256:93fbfa7c81a96034 | HTTP/health-doc-check |
| src\openjarvis\recipes\data\operators\correspondent_prompt.md | src\openjarvis\recipes\data\operators\correspondent_prompt.md | sha256:3e12a1b98e7c1870 | HTTP/health-doc-check |
| src\openjarvis\recipes\data\operators\openjarvis_twitter_bot_prompt.md | src\openjarvis\recipes\data\operators\openjarvis_twitter_bot_prompt.md | sha256:cea2510b6ce53e00 | HTTP/health-doc-check |
| src\openjarvis\recipes\data\operators\researcher_prompt.md | src\openjarvis\recipes\data\operators\researcher_prompt.md | sha256:82f536d395228d60 | HTTP/health-doc-check |
| src\openjarvis\recipes\data\operators\sentinel_prompt.md | src\openjarvis\recipes\data\operators\sentinel_prompt.md | sha256:c9e41395916efb4f | HTTP/health-doc-check |
| tests\fixtures\docs\channels.md | tests\fixtures\docs\channels.md | sha256:18619abd1bb4081a | HTTP/health-doc-check |
| tests\fixtures\docs\engines.md | tests\fixtures\docs\engines.md | sha256:ad82ab1d21505618 | HTTP/health-doc-check |
| tests\fixtures\docs\hardware.md | tests\fixtures\docs\hardware.md | sha256:d79289021d2db3a8 | HTTP/health-doc-check |
| tests\fixtures\docs\memory.md | tests\fixtures\docs\memory.md | sha256:4f403f5711060260 | HTTP/health-doc-check |
| tests\install\cases\missing-git.md | tests\install\cases\missing-git.md | sha256:d99d7604a4835b8d | HTTP/health-doc-check |
| tests\install\cases\README.md | tests\install\cases\README.md | sha256:8cd8f5d68728e113 | HTTP/health-doc-check |
| tests\install\cases\run-as-root.md | tests\install\cases\run-as-root.md | sha256:0f6d0d58e58eb44d | HTTP/health-doc-check |
| tests\mining\fixtures\README.md | tests\mining\fixtures\README.md | sha256:be992861db8e0e8f | HTTP/health-doc-check |
| tools\pearl-reference-oracle\README.md | tools\pearl-reference-oracle\README.md | sha256:e8cc9d2026621ae8 | HTTP/health-doc-check |
