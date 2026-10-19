# Changelog

## [0.4.0](https://github.com/alehar9320/agentic-odi/compare/v0.3.0...v0.4.0) (2026-10-19)


### Features

* **cli:** local-first backend seam, customer-outcomes, readable output ([2e25c03](https://github.com/alehar9320/agentic-odi/commit/2e25c03713c4ebb5fd8d64e73b79b4bf5e6f0867))
* **connectors:** add MCP connector presets for common ODI workflows ([dd81daf](https://github.com/alehar9320/agentic-odi/commit/dd81daf489f7903c0d03a93c4f2ef35663f7cd7e))


### Bug Fixes

* **ci:** unblock autonomous releases and make release assets attach ([9ce8db5](https://github.com/alehar9320/agentic-odi/commit/9ce8db5eb69d7924f2fda4bdf38ba6abd8f90517))

## [0.3.0](https://github.com/alehar9320/agentic-odi/compare/v0.2.0...v0.3.0) (2026-10-18)


### Features

* **cli:** add interactive chat mode with streaming MCP tool loop ([45453eb](https://github.com/alehar9320/agentic-odi/commit/45453eb5124932eeaa4a293bc5aedea77b63de6f))

## [0.2.0](https://github.com/alehar9320/agentic-odi/compare/v0.1.0...v0.2.0) (2026-10-18)


### Features

* add `agent_instructions.md` to define AI developer guardrails and project guidelines for LLMs. ([40eba65](https://github.com/alehar9320/agentic-odi/commit/40eba6543cd5da4ae58c4484b9affe0ca890f0e7))
* Add `run.py` for concurrent server/client launch, document agent-driven dev workflow, and update README with deployment details and new dependencies. ([8baf978](https://github.com/alehar9320/agentic-odi/commit/8baf97861875ff69ffcf88abf64d30cef8ce1391))
* Add AI agent instructions and guardrails covering technology stack, core practices, and testing strategy. ([fb4099a](https://github.com/alehar9320/agentic-odi/commit/fb4099a082fa54774ed27c2b06bc46b3d63c70dd))
* Add AI agent instructions and guardrails for ODI methodology, README maintenance, and core development practices. ([197471b](https://github.com/alehar9320/agentic-odi/commit/197471bf64a60019909ad2f715c0af6f5de82bae))
* Add GitHub Actions CI workflow for dependency management, linting, type checking, security scanning, and testing. ([a4f1ed0](https://github.com/alehar9320/agentic-odi/commit/a4f1ed0fbb7494b73195e9a46495a853e7d88214))
* Add initial README.md outlining the project's vision, current state, setup instructions, and roadmap for Agentic ODI. ([fd822f3](https://github.com/alehar9320/agentic-odi/commit/fd822f3eb3c25aa7ba06a4b99b09962ebc2bdf85))
* Add port availability checks for server and client, and refactor process management for improved robustness. ([d154097](https://github.com/alehar9320/agentic-odi/commit/d1540979452d7078a35740d5ac19a419e7c1f13f))
* Add step to create virtual environment in CI workflow for improved dependency management. ([f45fe9e](https://github.com/alehar9320/agentic-odi/commit/f45fe9e57d26fe16455d4a8f1e97a483b7164d0c))
* Add test configuration and initial test cases for job management and greeting functionality ([3334104](https://github.com/alehar9320/agentic-odi/commit/333410459b875146f2e3c9baae74a7da019f61ec))
* **cli:** add connectors list/add/health/ingest commands ([e049313](https://github.com/alehar9320/agentic-odi/commit/e049313cceb6c7ba7abe2adbcbf5e1df59f9bc04))
* **cli:** add POSIX and PowerShell installers (checksums.txt based) ([75f1d0c](https://github.com/alehar9320/agentic-odi/commit/75f1d0c77cf33f665b2e7489a9f0c325024c94b5))
* **cli:** build metadata and version display ([c2fef5e](https://github.com/alehar9320/agentic-odi/commit/c2fef5e3aa1e0dfc4a18d8afba4b19bca8c51538))
* **client:** implement The Living Studio GUI with progressive loadin… ([102030a](https://github.com/alehar9320/agentic-odi/commit/102030a313c9a42600e507cd89dce79be3d9fa40))
* **client:** implement The Living Studio GUI with progressive loading, ghost elements, and dual-interaction experience ([a645779](https://github.com/alehar9320/agentic-odi/commit/a64577931abb2d28a2a8cdb6ad9f73d381c6f389))
* **cli:** odi update command and startup auto-update hook ([6407d5d](https://github.com/alehar9320/agentic-odi/commit/6407d5d3b2fce8f155edb5842400395d339ec74d))
* **cli:** standalone local backend with --backend flag ([ebe977e](https://github.com/alehar9320/agentic-odi/commit/ebe977ebe8202e7c4494667dbd99b607108eab97))
* **cli:** update check, 24h cache, and download ([6138534](https://github.com/alehar9320/agentic-odi/commit/61385347aa06703da161e88d8b49c73599fa44c0))
* **cli:** update engine primitives (verify, extract, atomic swap) ([078fcdb](https://github.com/alehar9320/agentic-odi/commit/078fcdb098334c277399380a9ab39f2153d9ff61))
* **cli:** XDG-aware path resolution ([54fcd71](https://github.com/alehar9320/agentic-odi/commit/54fcd71996ee6966eb3f7b98b2d6e40f4ab457e8))
* **connectors:** add in-memory ingest sink ([c6c3a69](https://github.com/alehar9320/agentic-odi/commit/c6c3a69166444fcbe6562ca356fdd576999824ac))
* **connectors:** add JSON connection registry and kind dispatcher ([fad3436](https://github.com/alehar9320/agentic-odi/commit/fad34364d4e2cb71bb531e271a1e3fcff61df0df))
* **connectors:** add MCP client connector with health and ingest ([ad92100](https://github.com/alehar9320/agentic-odi/commit/ad92100987a99a512fda34ca01dea837c17f57f0))
* **connectors:** add shared models, Connector protocol, and errors ([a66137c](https://github.com/alehar9320/agentic-odi/commit/a66137c65eb1f8e6499caf00b1fc0b3ca9e830a7))
* **connectors:** scaffold agentic-odi-connectors workspace package ([5b19013](https://github.com/alehar9320/agentic-odi/commit/5b190137b222d02d01b8758225120f2171427e46))
* Enhance client and server functionality with LLM health checks, improved configuration management, and comprehensive README updates for local development ([4c414fa](https://github.com/alehar9320/agentic-odi/commit/4c414fa7491555957b09a6ca2875848cd5a94d66))
* Establish agent instructions and guardrails for Outcome-Driven Innovation, including foundational knowledge, core tools, and tests. ([944fa12](https://github.com/alehar9320/agentic-odi/commit/944fa1202b35e6e7fedf33562675f90481ab2983))
* Explicitly configure `mcp.run` with HTTP transport and port 8000. ([3daaa64](https://github.com/alehar9320/agentic-odi/commit/3daaa64d03510881c81a3ce99808d007a9cc5f72))
* Implement ODI data models and MCP tools on the server, create a client workflow to test them. ([08dea98](https://github.com/alehar9320/agentic-odi/commit/08dea9859578454526037ece54f3e734ba197472))
* introduce pytest-based testing suite, add initial tool test, and update documentation. ([dff027b](https://github.com/alehar9320/agentic-odi/commit/dff027ba4e099f3feeca4c856434711e808f53f3))
* Living Studio — React SPA + FastAPI sidecar + Tauri 2 desktop shell ([12e42da](https://github.com/alehar9320/agentic-odi/commit/12e42da37f0a9362bf30c25d1f0018bef4799b6b))
* **local_server:** port Living Studio API to FastAPI sidecar with SSE chat ([bb4d6fe](https://github.com/alehar9320/agentic-odi/commit/bb4d6fe173a4b5ba60e5f6cd84689b6719653ea0))
* **studio:** add React Living Studio SPA with SSE copilot ([b11cf6d](https://github.com/alehar9320/agentic-odi/commit/b11cf6d88e7b53ef37fe388993584ac180262685))
* **tauri:** thin desktop shell spawning the Python sidecar ([e520aac](https://github.com/alehar9320/agentic-odi/commit/e520aac913ed74910cba48011e1e82d57f43220b))


### Bug Fixes

* **ci:** align workspace, lockfile, and CI with server-&gt;mcp_server refactor ([d6f5c79](https://github.com/alehar9320/agentic-odi/commit/d6f5c79a913c1cfbb464356176e13e7ced455b99))
* **ci:** color-agnostic cli help test and honor python matrix ([005e732](https://github.com/alehar9320/agentic-odi/commit/005e732a5211dd9c0a92bdbd470aba09c5abe687))
* **ci:** exclude vendored Superpowers skills from Ruff ([2c2ea28](https://github.com/alehar9320/agentic-odi/commit/2c2ea2824506a30560bd555c3ea40e1de275751b))
* **ci:** require Python 3.11 to match StrEnum usage ([3e9a2b7](https://github.com/alehar9320/agentic-odi/commit/3e9a2b74ae52d0d9f53aae692616652b9d8abf8d))
* **ci:** send required mcp_url in sidecar smoke probes ([7fea831](https://github.com/alehar9320/agentic-odi/commit/7fea831e3077f6c975e5be1eafb0130dd68fa10f))
* **cli:** add timeout to default update fetch requests ([c89a843](https://github.com/alehar9320/agentic-odi/commit/c89a84316536fe9ba7e9ae86f05d70276e267ad9))
* **cli:** correct Windows install_root fallback and drop undocumented bin-dir override ([590cd9f](https://github.com/alehar9320/agentic-odi/commit/590cd9f4e070fdfe7138578f3fcf972aa12d9d34))
* **cli:** harden self-update extraction and URL handling for security scan ([4812155](https://github.com/alehar9320/agentic-odi/commit/481215536880b091169464ee900533c047cb3108))
* **cli:** reconcile version command and add --version --verbose ([22d11cc](https://github.com/alehar9320/agentic-odi/commit/22d11cc07f2519baf88b0903ccb5f96e3cb9eb32))
* **connectors:** repair rebased branch so CI passes ([0f0300f](https://github.com/alehar9320/agentic-odi/commit/0f0300fb52a1ebcc425a7bdcf1fe8e8136d87908))
* **studio:** track src/lib by anchoring root lib/ gitignore pattern ([11be5c2](https://github.com/alehar9320/agentic-odi/commit/11be5c2ca9d140450063880b12c4c0b84e96f26e))
* **workspace:** reconcile members, lockfile, and CI with core/mcp_server/local_server ([e17dc6d](https://github.com/alehar9320/agentic-odi/commit/e17dc6dad4276b07c13f4db4374bf7882f3fe66b))


### Performance Improvements

* **cli:** lazily import fastmcp client ([b5f9b0d](https://github.com/alehar9320/agentic-odi/commit/b5f9b0d7051158d2236d18dcc900f6bc2abbc94f))
