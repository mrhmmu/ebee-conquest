
<picture>
  <source
    width="100%"
    srcset="./images/Banner.png"
    media="(prefers-color-scheme: dark)"
  />
  <source
    width="100%"
    srcset="./images/Banner.png"
    media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)"
  />
  <img width="250" src="./images/Banner.png" />
</picture>

<h1 align="center">Turn-Based Sandbox Grand Strategy War Simulator</h1>

<p align="center">
  <a href="https://propro.click/courses/298/lecturers/1/projects/888"><img src="https://img.shields.io/badge/ProPro-Proposal-red"></a>
  <a href="https://google.com"><img src="https://img.shields.io/badge/build-development-orange"></a>
  <a href="https://github.com/RyanMMU/ebee-conquest/LICENSE"><img src="https://img.shields.io/github/license/moeru-ai/airi.svg?style=flat&colorA=080f12&colorB=1fa669"></a>
  <a href="https://discord.com/app"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fdiscord.com%2Fapi%2Finvites%2Fpython%3Fwith_counts%3Dtrue&query=%24.approximate_member_count&suffix=%20members&logo=discord&logoColor=white&label=%20&color=7389D8&labelColor=6A7EC2"></a>
  <a href="https://x.com/EbeeConquest"><img src="https://img.shields.io/badge/%40EbeeConquest-black?style=flat&logo=x&labelColor=%23101419&color=%232d2e30"></a>
</p>


### Powered by the Ebee Engine (EE)

A **Google Maps-style, 2D turn-based grand strategy war simulator** where players command nations and shape global history through conquest, diplomacy, and economic growth. Featuring **dNPC™ system**, non-player nations controlled by LLMs for dynamic, personality-driven geopolitics.
> **Note:** This project was developed as an ongoing collaboration with MMU. The main focus is modular architecture and the integration of modern AI agents into a war scenario game.

> [!WARNING]
> **Attention:** This game currently only **supports Windows** and is still under **active development**. Please check the documentation below and proceed with caution.


![Current Progress for Ebee Engine](images/engineprogresschart.png)
> **Figure 1:** Currently developed functions assosciated with Ebee Engine shown in a flowchart form. 

![Gameplay Example](images/example.gif)
> **Figure 2:** Example gameplay showing implemented A* pathfinding, and border highlighting using Kruskal's Algorithm. 

## 🚀 Quick Start

### Prerequisites

  * **Python:** 3.9+ (Windows)
  * **Dependencies:** See `requirements.txt` (uses `pygame-ce` and `pygame-gui`)
  * **API Key:** An OpenAI API key is required for dNPC™ functionality (or a local Ollama instance).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/RyanMMU/ebee-conquest.git
    cd ebee-conquest
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Test the Engine:**
    ```bash
    python main.py
    ```

>[!WARNING]
> If you previously installed `pygame`, uninstall it first to avoid runtime conflicts with `pygame-ce`.
>
> ```bash
> pip uninstall pygame
> pip install -r requirements.txt
> ```

-----

## Support of LLM API Providers for dNPC™️(powered by [EbeeEngineAPI](https://github.com/ebee-conquest/engine/api.py))

- [ ] [Graph-based (Recommended)](https://github.com/RyanMMU/ebee-conquest)
- [x] [DeepSeek](https://www.deepseek.com/)
- [ ] [AIHubMix](https://aihubmix.com/?aff=OOiX)
- [ ] [OpenRouter](https://openrouter.ai/)
- [ ] [vLLM](https://github.com/vllm-project/vllm)
- [ ] [SGLang](https://github.com/sgl-project/sglang)
- [ ] [Ollama](https://github.com/ollama/ollama)
- [ ] [302.AI](https://share.302.ai/514k2v)
- [ ] [OpenAI](https://platform.openai.com/docs/guides/gpt/chat-completions-api)
  - [ ] [Azure OpenAI API](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [ ] [Anthropic Claude](https://anthropic.com)
  - [ ] [AWS Claude](https://docs.anthropic.com/en/api/claude-on-amazon-bedrock) 
- [ ] [Qwen](https://help.aliyun.com/document_detail/2400395.html)
- [ ] [Google Gemini](https://developers.generativeai.google)
- [ ] [xAI](https://x.ai/)
- [ ] [Groq](https://wow.groq.com/)
- [ ] [Mistral](https://mistral.ai/)
- [ ] [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/)
- [ ] [Together.ai](https://www.together.ai/)
- [ ] [Fireworks.ai](https://www.together.ai/)
- [ ] [Novita](https://www.novita.ai/)
- [ ] [Zhipu](https://bigmodel.cn)
- [ ] [SiliconFlow](https://cloud.siliconflow.cn/i/rKXmRobW)
- [ ] [Stepfun](https://platform.stepfun.com/)
- [ ] [Baichuan](https://platform.baichuan-ai.com)
- [ ] [Minimax](https://api.minimax.chat/)
- [ ] [Moonshot AI](https://platform.moonshot.cn/)
- [ ] [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro)
- [ ] [Player2](https://player2.game/)
- [ ] [Tencent Cloud](https://cloud.tencent.com/document/product/1729)
- [ ] [Sparks](https://www.xfyun.cn/doc/spark/Web.html)
- [ ] [Volcano Engine](https://www.volcengine.com/experience/ark?utm_term=202502dsinvite&ac=DSASUQY5&rc=2QXCA1VI)

-----

## Tech Stack

  * **Engine:** Ebee Engine (Custom Python Map/Physics Engine)
  * **Graphics/UI:** Pygame, Pygame-GUI
  * **AI Orchestration:** Pydantic-AI, LangGraph, OpenAI API
  * **Data Management:** SQLite3, JSON (for persistence and SVG metadata)

-----

## Ebee Engine (EE) | Self-Developed Engine

The **Ebee Engine** is the project's main engine, converting static SVG data into an interactive, gameplay-ready strategic render.

### Map & Geometry

  * **SVG Processing:** Converts path data into renderable polygons and hitboxes.
  * **Interactive Projection:** Maps world coordinates to screen points with horizontal "infinite scroll" wrapping.
  * **Centroid Calculation:** Automatically determines label and unit placement for provinces (To be fixed).

### Pathfinding & Movement

  * **Adjacency Graph:** Built dynamically to allow AI and players to navigate provinces.
  * \**A* Pathfinding:\*\* Implements optimal routing with terrain-based cost modifiers (Mountains, Urban, Plains).

### Ebee Super Optimization (ESO)

  * **Geometry Cache:** Preprocessed SVG map geometry is cached to reduce startup parsing cost.
  * **Fast Reloads:** Subsequent runs can skip heavy reprocessing when cache is valid (you will see `ESO cache hit ...` logs).
  * **Large Map Ready:** Helps keep startup responsive even with high province counts.

-----

## Key Features

### 1\. dNPC™ (LLM-Driven Diplomacy)

Non-player nations aren't just scripts; they are agents.

  * **Personality-Driven:** Leaders react based on ideology, reputation, and world tension.
  * **Hybrid Intelligence:** Combines LLM reasoning with a rigid algorithmic validation layer to prevent "AI hallucinations" in game logic.

### 2\. National Economy System

  * **The "Pulse":** A turn-based system handling tax collection, population growth, and infrastructure scaling.
  * **Resource Management:** Balance recruitment costs against economic stability.

### 3\. Procedural World Events

  * Generates dynamic news reports and political shifts based on player actions.
  * Utilizes LLMs to write immersive narrative descriptions of in-game developments.


## AI Integration 

To ensure the game remains playable in all environments, we utilize a three-tier AI fallback strategy:

1.  **Online Mode:** Premium reasoning via OpenAI APIs.
2.  **Local Mode:** Offline LLM support via Ollama.
3.  **Offline Mode:** A robust rule-based heuristic system for zero-latency/offline play.
