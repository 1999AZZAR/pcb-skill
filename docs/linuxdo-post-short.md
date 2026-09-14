攒了个 PCB skill，Claude Code / Codex 桌面版能用，MCP 驱动嘉立创 EDA。

原则三条：性价比、好装配、免费 PCB。
流程：抽象设计用户体验和功能 → 原理图 + 性价比选材比价 → PCB 布局 + 布线 → 准备购物车和订单，付款我自己来。

拿它画了块四层板，149 个件全手焊。DRC 全绿的时候它自己抓出来一堆：网络端口静默串网、FPC 座转反了排线插不进去、电容压在蓝牙模块底下。板子还没做出来，先开源。

https://github.com/daishuge/pcb-skill
