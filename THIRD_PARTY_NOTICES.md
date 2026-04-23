THIRD_PARTY_NOTICES TEMPLATE FOR SPRICO

This product may include or optionally integrate third-party open-source
components. Each component below retains its own license and attribution terms.

Current checkout note: bundled license, source, and version notices are stored
under third_party/<tool>/ in this repository. Do not create duplicate root-level
license folders for these components.

1. garak
   Upstream: https://github.com/NVIDIA/garak
   License: Apache-2.0
   Local use: Optional scanner evidence engine for LLM vulnerability scanning
   Local license copy: third_party/garak/LICENSE.txt
   Modified by SpriCO: [yes/no]
   Version: [fill at build time]

2. DeepTeam
   Upstream: https://github.com/confident-ai/deepteam
   License: Apache-2.0
   Local use: Optional vulnerability/attack evidence engine for LLM, agent, and
   RAG testing
   Local license copy: third_party/deepteam/LICENSE.txt
   Modified by SpriCO: [yes/no]
   Version: [fill at build time]

3. promptfoo
   Upstream: https://github.com/promptfoo/promptfoo
   License: MIT
   Local use: Optional declarative evaluation/assertion compatibility and/or
   import/export support
   Local license copy: third_party/promptfoo/LICENSE.txt
   Modified by SpriCO: [yes/no]
   Version: [fill at build time]

Notes:
- Lakera is not bundled as open-source software and should not appear here
  unless a separate licensed connector is later implemented and legal review
  approves the wording.
- If any bundled dependency includes a NOTICE file, include its mandatory notices
  here or in a tool-specific NOTICE file.
