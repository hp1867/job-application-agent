# AIHawk adaptation
Source: https://github.com/feder-cr/AIHawk
Inspected commit: afe1f66dd3f1572d59a78ea67688a0d0e49e8b25
Version: 0.11.1. Current source is MIT; pre-2 September 2026 releases retain their earlier AGPL terms.

This project adapts the small action-summary formatter from src/aihawk/actions_help.py in backend/app/integrations/aihawk_adapter.py. Typed values are redacted; arbitrary tool argument rendering is removed. AIHawk 0.11.1 and its declared dependencies are now installed in the isolated .venv/aihawk environment. Real AIHawk actions and snapshots have been exercised through our guarded application queue on a synthetic loopback form using the Edge session adapter and upload extension. The original Firefox engine was also tested; its file-upload compatibility issue remains unresolved. The unrestricted LLM executor is not enabled. Our orchestrator retains eligibility, validation and approval ownership. The complete inspected upstream checkout is retained in vendor/AIHawk and excluded from project Git. Local compatibility changes and reproducibility limitations are documented in docs/AIHAWK_RUNTIME.md and docs/AIHAWK_ROUTE_FIX.md; upstream license notices remain intact.

MIT License

Copyright (c) 2024-2026 AIHawk contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
