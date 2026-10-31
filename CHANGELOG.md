# Changelog

## [0.15.0](https://github.com/alehar9320/agentic-odi/compare/v0.14.0...v0.15.0) (2026-10-31)


### Features

* **brand:** elevate favicon quality and add PM smart attire ([#253](https://github.com/alehar9320/agentic-odi/issues/253)) ([d7c6044](https://github.com/alehar9320/agentic-odi/commit/d7c604449caacaeb7715bfbecaf13d930dc3ffa6))
* **cli:** add --dry-run to connector ingest ([#188](https://github.com/alehar9320/agentic-odi/issues/188)) ([47a4291](https://github.com/alehar9320/agentic-odi/commit/47a42917fd7d2055260912575490e8c0a5a09f98))
* **cli:** add data-export for backing up the ODI store ([#293](https://github.com/alehar9320/agentic-odi/issues/293)) ([2d92efb](https://github.com/alehar9320/agentic-odi/commit/2d92efbcece5c80ee1468aba459aba463ddf27cc))
* **cli:** add odi summary for a one-screen job report ([#190](https://github.com/alehar9320/agentic-odi/issues/190)) ([9d20227](https://github.com/alehar9320/agentic-odi/commit/9d2022700528b69c08113f559091aeb04af776a4))
* **cli:** check every connector's health in one table ([#289](https://github.com/alehar9320/agentic-odi/issues/289)) ([af8a4cf](https://github.com/alehar9320/agentic-odi/commit/af8a4cf70d6acf196262c767a966e90ac24082e9))
* **cli:** export desired outcomes as CSV or JSON ([#189](https://github.com/alehar9320/agentic-odi/issues/189)) ([fe8f383](https://github.com/alehar9320/agentic-odi/commit/fe8f3837a70bca80f4a01a9ffac8e981ec3db24d))
* **cli:** list built-in connector presets as a markdown table ([#290](https://github.com/alehar9320/agentic-odi/issues/290)) ([f24159f](https://github.com/alehar9320/agentic-odi/commit/f24159fb3abb1a75fb9874c7b2fa1356518358f5))
* **connectors:** add a configurable shared HTTP client ([#292](https://github.com/alehar9320/agentic-odi/issues/292)) ([6046084](https://github.com/alehar9320/agentic-odi/commit/604608446596b2a335cc5e1b1fd9addc88d15446))
* **connectors:** validate evidence drafts before they reach the store ([#287](https://github.com/alehar9320/agentic-odi/issues/287)) ([ca06646](https://github.com/alehar9320/agentic-odi/commit/ca066460ed31033442bf3cc4d9fcc6ab715711d5))
* **core,cli,mcp-server,studio-api:** enforce ODI write contract on every path ([#270](https://github.com/alehar9320/agentic-odi/issues/270)) ([fbcc750](https://github.com/alehar9320/agentic-odi/commit/fbcc750562e6ed254312d21bf58539095ee85a0a))
* **core,cli,studio:** record scheduled work and dispatch it honestly ([#265](https://github.com/alehar9320/agentic-odi/issues/265)) ([167e4c0](https://github.com/alehar9320/agentic-odi/commit/167e4c0caad6e5d36f7ebfe9c4bcc196c4922bce))
* **core,cli:** configurable MCP connection limits ([#294](https://github.com/alehar9320/agentic-odi/issues/294)) ([2cea3a8](https://github.com/alehar9320/agentic-odi/commit/2cea3a8e26ac517b27aaf5f3f7dfd7f55bc0a900))
* **core,cli:** make the tool contract one source of truth, and expose it ([#263](https://github.com/alehar9320/agentic-odi/issues/263)) ([fb296d8](https://github.com/alehar9320/agentic-odi/commit/fb296d8257f27c8afb3d417ac237597e72882ff6))
* **core,studio:** add the V2MOM artifact and capture a vision in the context conversation ([#258](https://github.com/alehar9320/agentic-odi/issues/258)) ([838b721](https://github.com/alehar9320/agentic-odi/commit/838b7210b4f04daa040cc05bc46278ee756021aa))
* **core:** rank outcomes by opportunity score by default ([#185](https://github.com/alehar9320/agentic-odi/issues/185)) ([e11b792](https://github.com/alehar9320/agentic-odi/commit/e11b792f01a05d6f37de20dbc355d9ddca221c82))
* **core:** validate Job names and descriptions at the model level ([#296](https://github.com/alehar9320/agentic-odi/issues/296)) ([29f3bdc](https://github.com/alehar9320/agentic-odi/commit/29f3bdc8fe9e3b1a9e7ad614b200299eab370e5c)), closes [#116](https://github.com/alehar9320/agentic-odi/issues/116)
* **evidence:** keep a link back to the record, and let a quote become an outcome ([#261](https://github.com/alehar9320/agentic-odi/issues/261)) ([8195615](https://github.com/alehar9320/agentic-odi/commit/81956154d818e873f87800e1ebe3da4274badc02))
* **mcp:** add get_health store probe ([#286](https://github.com/alehar9320/agentic-odi/issues/286)) ([d206955](https://github.com/alehar9320/agentic-odi/commit/d206955d765d3500bf59c1ad32d66663edd5e2e0))
* **mcp:** flush and close the event store on a graceful shutdown ([#130](https://github.com/alehar9320/agentic-odi/issues/130)) ([9741447](https://github.com/alehar9320/agentic-odi/commit/9741447570c9938e4a15aaeca4fbc37336925fa2)), closes [#122](https://github.com/alehar9320/agentic-odi/issues/122)
* **mcp:** let the MCP server listen somewhere other than 8000 ([#155](https://github.com/alehar9320/agentic-odi/issues/155)) ([3354bb5](https://github.com/alehar9320/agentic-odi/commit/3354bb58dadedb4808b70848de2b63848703ee4f))
* **mcp:** refuse to serve a registry that disagrees with the contract ([#288](https://github.com/alehar9320/agentic-odi/issues/288)) ([af6a980](https://github.com/alehar9320/agentic-odi/commit/af6a980894d13427b76150a4d87565e12661cbd1))
* **signals:** make "catch up" mean something with a real signal inbox ([#277](https://github.com/alehar9320/agentic-odi/issues/277)) ([d1e3d20](https://github.com/alehar9320/agentic-odi/commit/d1e3d20c2126ded913fb331a07327ebf0ebad808))
* **studio-api:** expose customer outcomes and evidence over /api ([#174](https://github.com/alehar9320/agentic-odi/issues/174)) ([4806c10](https://github.com/alehar9320/agentic-odi/commit/4806c1072bfcc64267e5513bdd609102da7bd081))
* **studio,studio-api:** require evidence or a hypothesis on every claim ([#359](https://github.com/alehar9320/agentic-odi/issues/359)) ([7f7a463](https://github.com/alehar9320/agentic-odi/commit/7f7a46382dc36705a9c0a4d296586da2c0a99b61))
* **studio:** make every shipping surface usable without a mouse ([#364](https://github.com/alehar9320/agentic-odi/issues/364)) ([283ab5b](https://github.com/alehar9320/agentic-odi/commit/283ab5b3fdb0442c23e54d798913ade2e482fad7)), closes [#92](https://github.com/alehar9320/agentic-odi/issues/92)
* **studio:** make the catch-up feed and job map fully keyboard-operable ([#297](https://github.com/alehar9320/agentic-odi/issues/297)) ([2cc6f1a](https://github.com/alehar9320/agentic-odi/commit/2cc6f1ac4154bef982edbd8198c168065404adef)), closes [#115](https://github.com/alehar9320/agentic-odi/issues/115)
* **studio:** mark bundled sample outcomes so they cannot pass as data ([#232](https://github.com/alehar9320/agentic-odi/issues/232)) ([709d2c5](https://github.com/alehar9320/agentic-odi/commit/709d2c5f931d0391b2b67051d33216cad1c74c32))
* **studio:** max assistant-ui integration for the Living Studio ([#266](https://github.com/alehar9320/agentic-odi/issues/266)) ([d78005d](https://github.com/alehar9320/agentic-odi/commit/d78005d6b57ccbaa8154752431bc553b03a481e9))
* **studio:** offer a local, redacted diagnostics bundle ([#346](https://github.com/alehar9320/agentic-odi/issues/346)) ([#358](https://github.com/alehar9320/agentic-odi/issues/358)) ([ece6529](https://github.com/alehar9320/agentic-odi/commit/ece6529884e76b41888804498abb72ef14f836c5))
* **studio:** one banner system for every notice ([#264](https://github.com/alehar9320/agentic-odi/issues/264)) ([a90a708](https://github.com/alehar9320/agentic-odi/commit/a90a7080ac033a805bf070d1bdc48df621b41966))
* **studio:** open on a guided conversation, not a modal ([#268](https://github.com/alehar9320/agentic-odi/issues/268)) ([3426823](https://github.com/alehar9320/agentic-odi/commit/3426823281598cc92a970cdf4dd439dd7c570d9f))
* **studio:** resume the last job, step, or outcome after a reload ([#299](https://github.com/alehar9320/agentic-odi/issues/299)) ([bf1405d](https://github.com/alehar9320/agentic-odi/commit/bf1405d497d7f1312e3aab99fc3e7b77d6f1aa49)), closes [#109](https://github.com/alehar9320/agentic-odi/issues/109)
* **studio:** rewrite starter copy around concrete scenarios ([#316](https://github.com/alehar9320/agentic-odi/issues/316)) ([#361](https://github.com/alehar9320/agentic-odi/issues/361)) ([bf0fcb2](https://github.com/alehar9320/agentic-odi/commit/bf0fcb23845606ab2869424a767772aabc5ea633))
* **studio:** turn a quote into a scored outcome ([#236](https://github.com/alehar9320/agentic-odi/issues/236)) ([a95934b](https://github.com/alehar9320/agentic-odi/commit/a95934b468b441e46e5f974ff6ccc45d61e5b58e))


### Bug Fixes

* **ci:** label stacked pull requests, not only those targeting main ([#373](https://github.com/alehar9320/agentic-odi/issues/373)) ([51a7ad4](https://github.com/alehar9320/agentic-odi/commit/51a7ad4f1e6c1294d9766119138a1a310d5fa1b9))
* **studio:** close setup when starting a new conversation ([#135](https://github.com/alehar9320/agentic-odi/issues/135)) ([e53c73e](https://github.com/alehar9320/agentic-odi/commit/e53c73eaa3531886eb4a671ec21ddce4809030d8))
* **studio:** let Escape stop a running stream first ([#136](https://github.com/alehar9320/agentic-odi/issues/136)) ([2524f64](https://github.com/alehar9320/agentic-odi/commit/2524f642be81d8a8e1ada7cc24bec36997305caa))
* **studio:** make landscape table rows keyboard-selectable ([#137](https://github.com/alehar9320/agentic-odi/issues/137)) ([a6cfd86](https://github.com/alehar9320/agentic-odi/commit/a6cfd86e912f6062044ecc947cae59db66aa376b))
* **studio:** remove the + Simulate update affordance ([#322](https://github.com/alehar9320/agentic-odi/issues/322)) ([#372](https://github.com/alehar9320/agentic-odi/issues/372)) ([4be0071](https://github.com/alehar9320/agentic-odi/commit/4be00716e74d543c27da69f746f06c5269ddfcf8))
* **studio:** tag every offline turn as local guidance ([#142](https://github.com/alehar9320/agentic-odi/issues/142)) ([ab193fd](https://github.com/alehar9320/agentic-odi/commit/ab193fd49285857cea202bebd8ecdfca912fdd8a))

## [0.14.0](https://github.com/alehar9320/agentic-odi/compare/v0.13.0...v0.14.0) (2026-10-29)


### Features

* add on-device llm fallback and model router ([#65](https://github.com/alehar9320/agentic-odi/issues/65)) ([2962ea6](https://github.com/alehar9320/agentic-odi/commit/2962ea6a75fad1b83dfdd09555b322aa82d31faf))
* **release:** close the verifiable-release gaps from [#89](https://github.com/alehar9320/agentic-odi/issues/89) ([#275](https://github.com/alehar9320/agentic-odi/issues/275)) ([ac8a3a6](https://github.com/alehar9320/agentic-odi/commit/ac8a3a671dd75c9816e491260a3937d244d05296))
* **studio:** add a Customize page for managing connectors ([#262](https://github.com/alehar9320/agentic-odi/issues/262)) ([bde4ab3](https://github.com/alehar9320/agentic-odi/commit/bde4ab33406c00ee2f768e94a0133285b54ea575))


### Bug Fixes

* **release:** attach assets and publish stellar instructions on every release ([#257](https://github.com/alehar9320/agentic-odi/issues/257)) ([fd22a04](https://github.com/alehar9320/agentic-odi/commit/fd22a046e39987355f75d13c434bd4942cc2f580))

## [0.13.0](https://github.com/alehar9320/agentic-odi/compare/v0.12.0...v0.13.0) (2026-10-29)


### Features

* add native GitHub Action PR risk classification ([#240](https://github.com/alehar9320/agentic-odi/issues/240)) ([0bab99f](https://github.com/alehar9320/agentic-odi/commit/0bab99fd1ca76d36b706a26836e1a525cea243ac))
* **brand:** Odi the Otter — mascot, app icon, favicon, and CLI banner ([#100](https://github.com/alehar9320/agentic-odi/issues/100)) ([5286b6e](https://github.com/alehar9320/agentic-odi/commit/5286b6eb6956873cb843543f4bec682e05768c4c))
* **cli:** add --json to connectors list ([#177](https://github.com/alehar9320/agentic-odi/issues/177)) ([4cd1e42](https://github.com/alehar9320/agentic-odi/commit/4cd1e4250bf09d04d6e82cd45c182d7203bb807c))
* **cli:** let auto backend fall back to MCP instead of failing ([#230](https://github.com/alehar9320/agentic-odi/issues/230)) ([0785035](https://github.com/alehar9320/agentic-odi/commit/0785035474aa72b64fa86f949631d874c90cbc49))
* **connectors:** cache health probes for thirty seconds ([#220](https://github.com/alehar9320/agentic-odi/issues/220)) ([e5ade31](https://github.com/alehar9320/agentic-odi/commit/e5ade31a97cc5231f25575e720638f719a572baa))
* **connectors:** follow paginated REST responses to exhaustion ([#228](https://github.com/alehar9320/agentic-odi/issues/228)) ([2e416ae](https://github.com/alehar9320/agentic-odi/commit/2e416ae7fcad6dbfcb2fdd1c7c1a2e3aa3a71dc3))
* **core,cli,mcp-server:** generated capability manifest and CLI parity ([#272](https://github.com/alehar9320/agentic-odi/issues/272)) ([e463cd7](https://github.com/alehar9320/agentic-odi/commit/e463cd7c4cb7733327a894221b7edcd625cbc971))
* **core:** add a comprehensive error type hierarchy for ODI operations ([#128](https://github.com/alehar9320/agentic-odi/issues/128)) ([f615ff1](https://github.com/alehar9320/agentic-odi/commit/f615ff1b92b602fde02e4f028dfacf54360cae6c)), closes [#121](https://github.com/alehar9320/agentic-odi/issues/121)
* **core:** give the in-memory repository a reload() ([#150](https://github.com/alehar9320/agentic-odi/issues/150)) ([2548a4e](https://github.com/alehar9320/agentic-odi/commit/2548a4e84d079a5ba23e45e0856a913c291a538e))
* **core:** make acting tools wait for consent ([#152](https://github.com/alehar9320/agentic-odi/issues/152)) ([9854da0](https://github.com/alehar9320/agentic-odi/commit/9854da06a3e3093f68ead729cb1a15f4e35fe7c3))
* **core:** make the evidence-not-found error actionable ([#131](https://github.com/alehar9320/agentic-odi/issues/131)) ([a8165a1](https://github.com/alehar9320/agentic-odi/commit/a8165a1cf771ce0bdc31002b6e3f1806222e4cc7)), closes [#111](https://github.com/alehar9320/agentic-odi/issues/111)
* **core:** paginate list reads across repositories, service, and MCP tools ([#176](https://github.com/alehar9320/agentic-odi/issues/176)) ([c99d80c](https://github.com/alehar9320/agentic-odi/commit/c99d80c8a8912112080bb23e4cbe4db92a112b74))
* **core:** rank outcomes by opportunity and bucket them ([#222](https://github.com/alehar9320/agentic-odi/issues/222)) ([317bc95](https://github.com/alehar9320/agentic-odi/commit/317bc95b928f6b1e3d456e70605fa36acedad6ba))
* **core:** refuse outcome statements that do not match the ODI format ([#229](https://github.com/alehar9320/agentic-odi/issues/229)) ([c4da961](https://github.com/alehar9320/agentic-odi/commit/c4da96197cde1c6bcb0b45b09f0cf60556782cba))
* **core:** reject step orders outside the eight job-map stages ([#184](https://github.com/alehar9320/agentic-odi/issues/184)) ([892151b](https://github.com/alehar9320/agentic-odi/commit/892151b568b773475f79f3f1d1dc49ad82552bae))
* end-to-end error handling and sidecar-down degradation ([#247](https://github.com/alehar9320/agentic-odi/issues/247)) ([a4e4eff](https://github.com/alehar9320/agentic-odi/commit/a4e4effc468851ba5fbb3483b17662a74d0848ad))
* **mcp:** report progress from evidence ingest and statement evaluation ([#231](https://github.com/alehar9320/agentic-odi/issues/231)) ([1117bb9](https://github.com/alehar9320/agentic-odi/commit/1117bb9976f26888eaba79cd9f6cac5926a62197))
* **studio-api:** add read routes for jobs, steps, and outcomes ([#173](https://github.com/alehar9320/agentic-odi/issues/173)) ([44ab6e3](https://github.com/alehar9320/agentic-odi/commit/44ab6e34f029fe17d28b91cb87513acc9d2fdb61))
* **studio-api:** publish the OpenAPI contract under /api ([#219](https://github.com/alehar9320/agentic-odi/issues/219)) ([c3db962](https://github.com/alehar9320/agentic-odi/commit/c3db9622abaad74baa210fd74fcd7a8c9c899b5d))
* **studio:** add a persistent light/dark theme toggle ([#218](https://github.com/alehar9320/agentic-odi/issues/218)) ([02015aa](https://github.com/alehar9320/agentic-odi/commit/02015aa9d01ae792e4269b667f4697a3ac5be36d))
* **studio:** add steps inline from the job map ([#144](https://github.com/alehar9320/agentic-odi/issues/144)) ([7e124f8](https://github.com/alehar9320/agentic-odi/commit/7e124f8eec8b44a19b53bc131a406f5d226849cd))
* **studio:** clear the bell count when catch-up opens ([#224](https://github.com/alehar9320/agentic-odi/issues/224)) ([657c6f0](https://github.com/alehar9320/agentic-odi/commit/657c6f0b7a933b5608bedf6a1f488b908d1d4cc9))
* **studio:** complete browser BFF local-first design ([#249](https://github.com/alehar9320/agentic-odi/issues/249)) ([a60abc3](https://github.com/alehar9320/agentic-odi/commit/a60abc3b0a237ab8ecb2c853612c048eb9cbfb6c))
* **studio:** copy an outcome statement from its card ([#225](https://github.com/alehar9320/agentic-odi/issues/225)) ([d1bb35e](https://github.com/alehar9320/agentic-odi/commit/d1bb35e7c228b98f3b65aba68f87bb3cbbe4693b))
* **studio:** export a conversation as Markdown ([#217](https://github.com/alehar9320/agentic-odi/issues/217)) ([a2229db](https://github.com/alehar9320/agentic-odi/commit/a2229db4399f07a4669affd4cf47174aa1b7f765))
* **studio:** group the command palette by what a command does ([#223](https://github.com/alehar9320/agentic-odi/issues/223)) ([b08345d](https://github.com/alehar9320/agentic-odi/commit/b08345d0b6c607442d8435275476408726964ec2))
* **studio:** let a tour step be skipped without ending the tour ([#227](https://github.com/alehar9320/agentic-odi/issues/227)) ([a8bd2ab](https://github.com/alehar9320/agentic-odi/commit/a8bd2abba17d79c00fadf98ebee121cbd119b916))
* **studio:** let the API key field be revealed ([#146](https://github.com/alehar9320/agentic-odi/issues/146)) ([f607f8b](https://github.com/alehar9320/agentic-odi/commit/f607f8b32945d16433f259753631a5158e49d252))
* **studio:** make assistant-ui conversation controls discoverable ([#245](https://github.com/alehar9320/agentic-odi/issues/245)) ([6508086](https://github.com/alehar9320/agentic-odi/commit/65080866605f1ede51762435cf08d3a7b1bf7206))
* **studio:** make the desktop app update itself ([#76](https://github.com/alehar9320/agentic-odi/issues/76)) ([8f9bf37](https://github.com/alehar9320/agentic-odi/commit/8f9bf37379e08db6c78a54c8edc68cdfc46dcbd5))
* **studio:** order customer evidence by dragging ([#235](https://github.com/alehar9320/agentic-odi/issues/235)) ([884aa6d](https://github.com/alehar9320/agentic-odi/commit/884aa6d5e0f5230a4a565aebf3267ea1eeccea2c))
* **studio:** print the thesis as an A4 document ([#216](https://github.com/alehar9320/agentic-odi/issues/216)) ([7938d97](https://github.com/alehar9320/agentic-odi/commit/7938d97d2cd811372a02019692ea9354346e60ac))
* **studio:** remember which release notes were read ([#203](https://github.com/alehar9320/agentic-odi/issues/203)) ([65431ec](https://github.com/alehar9320/agentic-odi/commit/65431ec9222dbbd5dff58c59c5aa802353e0102d))
* **studio:** replace sample evidence with an honest empty state ([#133](https://github.com/alehar9320/agentic-odi/issues/133)) ([5df8d17](https://github.com/alehar9320/agentic-odi/commit/5df8d1728a8ce4420673efbc4d37ad724e9d3921))
* **studio:** run the conversation on assistant-ui ([#238](https://github.com/alehar9320/agentic-odi/issues/238)) ([b3c2157](https://github.com/alehar9320/agentic-odi/commit/b3c21571fc9f4c3b2e827cf8968f48cc6b82519a))
* **studio:** save a scored outcome as a shareable opportunity thesis ([#233](https://github.com/alehar9320/agentic-odi/issues/233)) ([7c0ffa6](https://github.com/alehar9320/agentic-odi/commit/7c0ffa6a00aca3c8c356d17facf398445426a2d7))
* **studio:** show memory skeletons while loading ([#148](https://github.com/alehar9320/agentic-odi/issues/148)) ([8a1430d](https://github.com/alehar9320/agentic-odi/commit/8a1430d603d62b77b534d2fb0f9ae68fca515f98))
* **v2mom:** implement living V2MOM artifact detection, persistence, MCP tools, and Studio UI ([#104](https://github.com/alehar9320/agentic-odi/issues/104)) ([a5e8f1e](https://github.com/alehar9320/agentic-odi/commit/a5e8f1e23f141ad096067bca913bc24cdb8aa9af))
* **website:** every doc heading links to its own section ([#207](https://github.com/alehar9320/agentic-odi/issues/207)) ([2775699](https://github.com/alehar9320/agentic-odi/commit/277569975e337eda2f249aad5e36495b42c81176))
* **website:** let readers pick light or dark ([#208](https://github.com/alehar9320/agentic-odi/issues/208)) ([5eaacae](https://github.com/alehar9320/agentic-odi/commit/5eaacaec68915fe6d64b0304644f56792f2bc82d))
* **website:** publish a generated connector preset reference ([#212](https://github.com/alehar9320/agentic-odi/issues/212)) ([1d71161](https://github.com/alehar9320/agentic-odi/commit/1d711614badf4c4248888c35fed75878a517df55))
* **website:** rebuild the project site for the AI era ([#103](https://github.com/alehar9320/agentic-odi/issues/103)) ([a462af7](https://github.com/alehar9320/agentic-odi/commit/a462af7174ca67f2635c1217d1ea182fc8caed3a))
* **website:** search the docs from any page with Ctrl+K ([#213](https://github.com/alehar9320/agentic-odi/issues/213)) ([c939f7c](https://github.com/alehar9320/agentic-odi/commit/c939f7c2a69a429bba45cb68b925bac2608d83a2))


### Bug Fixes

* **cli:** parse MCP payloads that carry prose around them ([#179](https://github.com/alehar9320/agentic-odi/issues/179)) ([eb1125e](https://github.com/alehar9320/agentic-odi/commit/eb1125e8557500ebba4e4587b3589e53a6b4b5a1))
* **cli:** resolve the connector registry through the shared path helper ([#178](https://github.com/alehar9320/agentic-odi/issues/178)) ([9c76939](https://github.com/alehar9320/agentic-odi/commit/9c76939a7477b8ec58f0a012053f4cbfd5590456))
* **connectors:** validate connector config at startup ([#124](https://github.com/alehar9320/agentic-odi/issues/124)) ([#237](https://github.com/alehar9320/agentic-odi/issues/237)) ([1fabd72](https://github.com/alehar9320/agentic-odi/commit/1fabd7273af228689ef8fa80e7b4293c2ac61671))
* **core:** seed the pagination tests with valid job-map step orders ([#248](https://github.com/alehar9320/agentic-odi/issues/248)) ([611d7b5](https://github.com/alehar9320/agentic-odi/commit/611d7b5df7cf2044ef3c7c58d9cd27645e0073fc))
* **core:** state the SQLite concurrency contract at the connection ([#210](https://github.com/alehar9320/agentic-odi/issues/210)) ([121c9f5](https://github.com/alehar9320/agentic-odi/commit/121c9f50d0157c4e70219dafdbfb64c9b8a71d7b))
* **infra:** send security headers from the Living Studio Worker ([#181](https://github.com/alehar9320/agentic-odi/issues/181)) ([81e14c5](https://github.com/alehar9320/agentic-odi/commit/81e14c592742f543bfa29886397e44bb85ff9a94))
* **mcp:** answer a missing job with the shared error string ([#154](https://github.com/alehar9320/agentic-odi/issues/154)) ([f810a58](https://github.com/alehar9320/agentic-odi/commit/f810a5857c2343017a82dd7fec8d230c429f8983))
* **release:** make releases fully automatic ([#250](https://github.com/alehar9320/agentic-odi/issues/250)) ([5152516](https://github.com/alehar9320/agentic-odi/commit/5152516a9ef226453d1ccaabbb98708f5626edb2))
* **release:** make the checksum download one command ([#156](https://github.com/alehar9320/agentic-odi/issues/156)) ([f3b3a04](https://github.com/alehar9320/agentic-odi/commit/f3b3a0453f79d428ad2f2a7f3bc4376783275d88))
* **studio-api:** repair the outcomes route and its test after the main merges ([#254](https://github.com/alehar9320/agentic-odi/issues/254)) ([4103885](https://github.com/alehar9320/agentic-odi/commit/4103885264a4207d16ef67c4772800b969ec4233))
* **studio-api:** report real capabilities from /capabilities ([#169](https://github.com/alehar9320/agentic-odi/issues/169)) ([0ad4e99](https://github.com/alehar9320/agentic-odi/commit/0ad4e99cc62144fcf80fcf5d68e357c5eb29b917))
* **studio:** announce tool traces as they arrive ([#139](https://github.com/alehar9320/agentic-odi/issues/139)) ([eb39eee](https://github.com/alehar9320/agentic-odi/commit/eb39eee182883571cf342b8238ac476a6c2ae8ed))
* **studio:** disable landscape filters while the canvas loads ([#145](https://github.com/alehar9320/agentic-odi/issues/145)) ([e158f58](https://github.com/alehar9320/agentic-odi/commit/e158f5836a1d03de1a8d2877089a888d1e7beaf9))
* **studio:** drop dead connector rows from Settings ([#134](https://github.com/alehar9320/agentic-odi/issues/134)) ([feb465a](https://github.com/alehar9320/agentic-odi/commit/feb465a7a2a6ce9efbfe6d3f76520ca3fb6de71e))
* **studio:** give the composer's controls a real keyboard focus ring ([#205](https://github.com/alehar9320/agentic-odi/issues/205)) ([accfb38](https://github.com/alehar9320/agentic-odi/commit/accfb38a82625024414cff71e172e7d538aac854))
* **studio:** give unsupported surfaces a recovery path ([#140](https://github.com/alehar9320/agentic-odi/issues/140)) ([e290740](https://github.com/alehar9320/agentic-odi/commit/e290740734902a5670c30784e8ae114e5e2a2b1b))
* **studio:** label connector chips as suggestions ([#141](https://github.com/alehar9320/agentic-odi/issues/141)) ([7d48b8d](https://github.com/alehar9320/agentic-odi/commit/7d48b8d41e973f096e5f7b6c4144aed1a434ac1a))
* **studio:** label demo, seed, and simulated surfaces ([#78](https://github.com/alehar9320/agentic-odi/issues/78)) ([#274](https://github.com/alehar9320/agentic-odi/issues/274)) ([0e04de1](https://github.com/alehar9320/agentic-odi/commit/0e04de1d0591bedd484432b877c64647c41bfd54))
* **studio:** let update errors stay inline ([#147](https://github.com/alehar9320/agentic-odi/issues/147)) ([b444a52](https://github.com/alehar9320/agentic-odi/commit/b444a524127acbeca10322cf43962412739ed45a))
* **studio:** make failure as considered as success ([#129](https://github.com/alehar9320/agentic-odi/issues/129)) ([8cc0815](https://github.com/alehar9320/agentic-odi/commit/8cc08159eebc69a44bcd596354a480bb4be6845e))
* **studio:** name the model health control ([#138](https://github.com/alehar9320/agentic-odi/issues/138)) ([4b16999](https://github.com/alehar9320/agentic-odi/commit/4b169998cec831a58a893642fddd4c4d9fc7b440))
* **studio:** name the Ulwick phase on job map rows ([#143](https://github.com/alehar9320/agentic-odi/issues/143)) ([eeb68bb](https://github.com/alehar9320/agentic-odi/commit/eeb68bb2881307a3f0ddd32aa260759aeaa2e1ab))
* **studio:** preserve assistant-ui turn context ([#241](https://github.com/alehar9320/agentic-odi/issues/241)) ([74e67f8](https://github.com/alehar9320/agentic-odi/commit/74e67f85335b82ea4bf5ed9eaeccfec40bc6dac4))

## [0.12.0](https://github.com/alehar9320/agentic-odi/compare/v0.11.0...v0.12.0) (2026-10-21)


### Features

* **studio:** keep the conversation on stage while a view is open ([#71](https://github.com/alehar9320/agentic-odi/issues/71)) ([ab6db19](https://github.com/alehar9320/agentic-odi/commit/ab6db196d0f8e533a69c580b3fc89e480b6ab971))

## [0.11.0](https://github.com/alehar9320/agentic-odi/compare/v0.10.0...v0.11.0) (2026-10-21)


### Features

* add feature flags accessible via CLI and Studio settings ([#72](https://github.com/alehar9320/agentic-odi/issues/72)) ([52b2273](https://github.com/alehar9320/agentic-odi/commit/52b2273c477fa2c7f36882e24f3d52b23d048ccb))
* **studio:** add discrete changelog drawer with Steve Jobs quality experience ([#60](https://github.com/alehar9320/agentic-odi/issues/60)) ([01dc737](https://github.com/alehar9320/agentic-odi/commit/01dc737dbf3ce6a8742e26ffe45e66254cc987cf))
* **studio:** add feature-flagged first-run wizard ([#69](https://github.com/alehar9320/agentic-odi/issues/69)) ([3d07761](https://github.com/alehar9320/agentic-odi/commit/3d077618db0cb9cc3498af5d99b38cadf8ab2608))
* **studio:** add intent and outcome notification catch-up experience ([#58](https://github.com/alehar9320/agentic-odi/issues/58)) ([b89e8f4](https://github.com/alehar9320/agentic-odi/commit/b89e8f419610954d6a9caeddf6b746076723c220))
* **studio:** introduce 20 micro interactions and animations ([#61](https://github.com/alehar9320/agentic-odi/issues/61)) ([1fc5411](https://github.com/alehar9320/agentic-odi/commit/1fc5411db724b465040cd79db56c3a5713543959))


### Bug Fixes

* **deploy:** add required previews block for Worker previews ([#74](https://github.com/alehar9320/agentic-odi/issues/74)) ([00e3943](https://github.com/alehar9320/agentic-odi/commit/00e39436001bd0555405c637e05d71748447bdb7))
* **pages:** deploy the website from main again ([#73](https://github.com/alehar9320/agentic-odi/issues/73)) ([f806382](https://github.com/alehar9320/agentic-odi/commit/f8063826cf827cb37fb108e564abd62439f1b7a8))

## [0.10.0](https://github.com/alehar9320/agentic-odi/compare/v0.9.0...v0.10.0) (2026-10-21)


### Features

* MCP ↔ Living Studio connectors (presets, REST API, SSE suggestions) ([#56](https://github.com/alehar9320/agentic-odi/issues/56)) ([9b4c5aa](https://github.com/alehar9320/agentic-odi/commit/9b4c5aa1d56a44d225f1676a91abede120722fad))
* **studio:** render agent-composed surfaces inline in chat ([#55](https://github.com/alehar9320/agentic-odi/issues/55)) ([97f7e95](https://github.com/alehar9320/agentic-odi/commit/97f7e95f7da831e6b78ef297895beef1330ddf12))

## [0.9.0](https://github.com/alehar9320/agentic-odi/compare/v0.8.0...v0.9.0) (2026-10-21)


### Features

* **release:** publish end-user download & run instructions on every release ([#35](https://github.com/alehar9320/agentic-odi/issues/35)) ([bf8c147](https://github.com/alehar9320/agentic-odi/commit/bf8c14717f7c028c2269ee2d0b78c4b8ec4fb79a))
* **storage:** local-first event store with Cloudflare D1 sync foundation ([#42](https://github.com/alehar9320/agentic-odi/issues/42)) ([b6487ac](https://github.com/alehar9320/agentic-odi/commit/b6487ac40a6c6184e4067c44f2bd47709f959a71))
* **studio:** add world-class interactive data visualizations for opportunity landscape and job map ([#44](https://github.com/alehar9320/agentic-odi/issues/44)) ([50c38d6](https://github.com/alehar9320/agentic-odi/commit/50c38d6dbe8a1b24f35c927c6bfb6b45e639d388))
* **studio:** chat-first interface with drawer and workspace panel ([#34](https://github.com/alehar9320/agentic-odi/issues/34)) ([ee1f154](https://github.com/alehar9320/agentic-odi/commit/ee1f154c815314c6a272cad6f3fb7cd0a324dea0))
* **studio:** conversational first-run, commands, and offline manual work ([#43](https://github.com/alehar9320/agentic-odi/issues/43)) ([a3b8a33](https://github.com/alehar9320/agentic-odi/commit/a3b8a336c20cb2744cbc544da682f712dcd92efd))


### Bug Fixes

* **ci:** let tauri-build run without signing secrets ([#45](https://github.com/alehar9320/agentic-odi/issues/45)) ([2dc14e4](https://github.com/alehar9320/agentic-odi/commit/2dc14e4ae2065b465f920e8a1aa4e5b7a1d6b425))
* **cli:** implement onboarding card and narrow profile except ([#49](https://github.com/alehar9320/agentic-odi/issues/49)) ([7346f6a](https://github.com/alehar9320/agentic-odi/commit/7346f6a76ab20246b0760f9b3bad2fd1a7362766))
* **cli:** make the unreachable-server test hermetic ([#53](https://github.com/alehar9320/agentic-odi/issues/53)) ([8c04a1e](https://github.com/alehar9320/agentic-odi/commit/8c04a1ed099cb893239ef380c7a21f5dddfb4a8b))
* **cli:** remove unused EvidenceNotFoundError import ([#51](https://github.com/alehar9320/agentic-odi/issues/51)) ([abbe628](https://github.com/alehar9320/agentic-odi/commit/abbe62877f06e2c46695dcba17f3f87a4933b4c7))
* harden error handling and not-found checks ([#50](https://github.com/alehar9320/agentic-odi/issues/50)) ([7afe4a3](https://github.com/alehar9320/agentic-odi/commit/7afe4a344ab014ce0b5eaae5a6812ddf733391ff))
* **website:** fix CSS variable, duplicate sections, SVG, description, apostrophes ([#47](https://github.com/alehar9320/agentic-odi/issues/47)) ([b8e141b](https://github.com/alehar9320/agentic-odi/commit/b8e141b9ec310a73322f75eb271f4b702c836f18))

## [0.8.0](https://github.com/alehar9320/agentic-odi/compare/v0.7.0...v0.8.0) (2026-10-20)


### Features

* add Kiro CLI superpowers integration ([8af114f](https://github.com/alehar9320/agentic-odi/commit/8af114f977bf7b849e176dbd3648e8a93310c97a))
* **cli:** entity parity commands for jobs, steps, outcomes, and evidence ([b89388d](https://github.com/alehar9320/agentic-odi/commit/b89388d854dcaaca1afe3b1950fabc02e115d121))
* **connectors:** REST connector and evidence mapping ([c02e2fc](https://github.com/alehar9320/agentic-odi/commit/c02e2fc594bba0d14c00b2d782785fa569b728e2))
* **core:** full entity CRUD over a shared SQLite store ([ff3336f](https://github.com/alehar9320/agentic-odi/commit/ff3336f3a94bdfca14dba91405bed093edb2d61d))
* **mcp:** CRUD tool parity, shared store, and evidence tools ([b4d170f](https://github.com/alehar9320/agentic-odi/commit/b4d170f721883418b9a372f014703dccc7ce2866))

## [0.7.0](https://github.com/alehar9320/agentic-odi/compare/v0.6.0...v0.7.0) (2026-10-20)


### Features

* **cli:** offline-first REPL with /connect wizard and LLM profile persistence ([7aa01cf](https://github.com/alehar9320/agentic-odi/commit/7aa01cf42dc2dbbcb94e4b929a7e3dffcacaaf4c))
* **deploy:** serve the Living Studio from a free Cloudflare Worker ([83e491e](https://github.com/alehar9320/agentic-odi/commit/83e491eee766b4a9c26710177b68ed4839a67d7d))


### Bug Fixes

* **cli:** resolve mypy and ruff CI failures ([5acc4fc](https://github.com/alehar9320/agentic-odi/commit/5acc4fc05ed6a29acd0df3586f8b9715e913254e))

## [0.6.0](https://github.com/alehar9320/agentic-odi/compare/v0.5.0...v0.6.0) (2026-10-19)


### Features

* **website:** design system colors typography spacing grid motion focus-visible ([1707932](https://github.com/alehar9320/agentic-odi/commit/1707932622072b3ebf118ec079f89745f43120e5))
* **website:** GitHub Pages site with progressive loading, ghost elements, and dual-interaction experience ([7a574d4](https://github.com/alehar9320/agentic-odi/commit/7a574d4b4ad2343a777769fe0d243d1795297296))
* **website:** reproducible OG image generator with committed art ([e5aa4a8](https://github.com/alehar9320/agentic-odi/commit/e5aa4a8b71a51a29056f9dee80dbdc4710ae44d0))


### Bug Fixes

* **website:** run site checks in main CI ([402f0a5](https://github.com/alehar9320/agentic-odi/commit/402f0a5e8cd7bb939d31246dd1b1f99290595250))

## [0.5.0](https://github.com/alehar9320/agentic-odi/compare/v0.4.0...v0.5.0) (2026-10-19)


### Features

* minimalistic conversational GUI ([c4ef8f5](https://github.com/alehar9320/agentic-odi/commit/c4ef8f55a559319a633fd147484fc8837db86d4a))


### Bug Fixes

* **studio:** wire engagement level into studio context ([0aaa54e](https://github.com/alehar9320/agentic-odi/commit/0aaa54efa616e5eb791847e7cad52e48a41bda95))

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
