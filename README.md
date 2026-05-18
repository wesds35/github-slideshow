# Your GitHub Learning Lab Repository for Introducing GitHub

Welcome to **your** repository for your GitHub Learning Lab course. This repository will be used during the different activities that I will be guiding you through. See a word you don't understand? We've included an emoji 📖 next to some key terms. Click on it to see its definition.

Oh! I haven't introduced myself...

I'm the GitHub Learning Lab bot and I'm here to help guide you in your journey to learn and master the various topics covered in this course. I will be using Issue and Pull Request comments to communicate with you. In fact, I already added an issue for you to check out.

![issue tab](https://lab.github.com/public/images/issue_tab.png)

I'll meet you over there, can't wait to get started!

This course is using the :sparkles: open source project [reveal.js](https://github.com/hakimel/reveal.js/). In some cases we’ve made changes to the history so it would behave during class, so head to the original project repo to learn more about the cool people behind this project.

## Market Game Theory Analyzer

This repository now includes `market_game_theory.py`, a Python script that scores stocks/ETFs and countries using a game-theory-inspired payoff model.

### Data sources (free APIs)
- Yahoo Finance public endpoints (price history, profile, and news search where available)
- World Bank API (GDP growth and population growth)

### What it evaluates
- Price momentum and volatility-adjusted return
- News headline sentiment (keyword-based)
- Company quality/valuation proxies when available
- Country macro profile (GDP + population growth)

### Example
```bash
python3 market_game_theory.py --ticker AAPL --ticker SPY --country USA
```

### Ratings
- `Strong Buy` (80+)
- `Buy` (67-79.99)
- `Hold` (52-66.99)
- `Reduce` (37-51.99)
- `Avoid` (<37)
