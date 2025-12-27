import streamlit as st
import random
import time
import pandas as pd
import graphviz
from typing import List, Dict, Optional, Any, Set

# ==============================================================================
# 0. Global Settings & Constants
# ==============================================================================
NAMES_HIRA = ["あきら", "かおる", "さとる", "つよし", "みさき", "ひろし", "ゆかり", "あずさ", "たけし", "ななみ", "けんた", "まこと", "あゆみ", "みゆき", "しおり"]
PERSONALITY_DATA = {
    "好戦的": {"emoji": "🔥", "style": "aggressive"},
    "臆病": {"emoji": "💧", "style": "scared"},
    "論理的": {"emoji": "🧠", "style": "logical"},
    "直感型": {"emoji": "⚡", "style": "intuitive"},
    "サイコパス": {"emoji": "🎭", "style": "psycho"}
}
PERSONALITIES = list(PERSONALITY_DATA.keys())

ROLES = {
    "WEREWOLF": {"name": "人狼", "icon": "🐺", "team": "Wolf"},
    "VILLAGER": {"name": "市民", "icon": "👤", "team": "Villager"},
    "SEER": {"name": "占い師", "icon": "🔮", "team": "Villager"},
    "MADMAN": {"name": "狂人", "icon": "🤡", "team": "Wolf"},
    "BODYGUARD": {"name": "騎士", "icon": "🛡️", "team": "Villager"},
    "MEDIUM": {"name": "霊能者", "icon": "🕯️", "team": "Villager"}
}

# ==============================================================================
# 1. Player Class
# ==============================================================================
class Player:
    def __init__(self, name: str, role_key: str, personality: str):
        self.name = name
        self.role_key = role_key
        self.role_info = ROLES[role_key]
        self.personality = personality
        self.p_info = PERSONALITY_DATA[personality]
        self.is_alive = True
        self.revealed_role = False 
        self.co_status = False 
        
        self.known_whitelist: Set[str] = set()
        self.known_blacklist: Set[str] = set()
        
        self.memory = {
            "vote_history": {},     
            "co_history": {},       
            "deaths": [],           
            "seer_reports": {},     # {target: result}
            "medium_reports": {}
        }
        
        self.trust_scores = {}      
        self.strategy = "NORMAL"
        self.current_target = None
        self.current_guard_target = None

    def init_trust(self, others: List[str]):
        for other in others:
            self.trust_scores[other] = 0.5 + random.uniform(-0.1, 0.1)

    def learn(self, day: int, action_type: str, data: Any):
        if action_type == "VOTE": self.memory["vote_history"][day] = data
        elif action_type == "CO": self.memory["co_history"][data[0]] = data[1]
        elif action_type == "SEER_REPORT":
            target, result = data
            self.memory["seer_reports"][target] = result
            if result == "人狼": self.known_blacklist.add(target)
            else: self.known_whitelist.add(target)
        elif action_type == "MEDIUM_REPORT":
            day_num, target, result = data
            self.memory["medium_reports"][day_num] = {target: result}
            if result == "人狼": self.known_blacklist.add(target)
            else: self.known_whitelist.add(target)

    def decide_strategy(self, day: int, alive_players: List['Player']):
        if self.role_key == "WEREWOLF": 
            self.strategy = "BUS_THROW" if day >= 2 and random.random() < 0.2 else "STEALTH"
        elif self.role_key == "MADMAN": 
            self.strategy = "FAKE_CO" if day >= 2 and random.random() < 0.7 else "CHAOS"
        elif self.role_key == "SEER":
            if self.known_blacklist: self.strategy = "REVEAL_TRUTH"
            else: self.strategy = "DIVINER_WAIT"
        else:
            self.strategy = "VILLAGE_THOUGHT"

    def select_action_targets(self, alive_players: List['Player']):
        others = [p for p in alive_players if p.name != self.name]
        if not others: return

        if self.role_key == "BODYGUARD":
            pt = sorted(others, key=lambda x: self.trust_scores.get(x.name, 0.5), reverse=True)
            self.current_guard_target = pt[0].name
        
        alive_names = [p.name for p in alive_players]
        target_override = None
        if self.role_key == "SEER":
            for b in self.known_blacklist:
                if b in alive_names:
                    target_override = b; break
        
        invalid_v_targets = set()
        if self.role_key == "WEREWOLF" and self.strategy != "BUS_THROW":
            invalid_v_targets = {p.name for p in alive_players if p.role_key == "WEREWOLF"}
        elif self.role_key == "SEER":
            invalid_v_targets = self.known_whitelist

        for b in self.known_blacklist: self.trust_scores[b] = 0.0
        for w in self.known_whitelist: self.trust_scores[w] = 1.0

        candidates = [o for o in others if o.name not in invalid_v_targets]
        fallback = min(candidates, key=lambda x: self.trust_scores.get(x.name, 0.5)) if candidates else random.choice(others)
        self.current_target = target_override or fallback.name

    def generate_dialogue(self, day: int, alive_players: List['Player']) -> Dict[str, str]:
        p = self.personality
        t = self.current_target
        s = self.strategy
        insight = f"🤔 [思考: {s}] "
        
        styles = {
            "好戦的": {
                "base": [f"{t}、あんたが狼だろ。", f"{t}さんの言動には矛盾がありすぎる。", f"黙って聞いてれば…{t}、お前の番だよ。"],
                "thought": [f"{t}を追い詰める。", f"まずは{t}だ。"]
            },
            "臆病": {
                "base": [f"あの…{t}さんが怖く見えてしまって…", f"{t}さんが人狼だったらどうしよう。", f"ごめんなさい、{t}さんに投票します。"],
                "thought": [f"自分を隠すために{t}さんに。", f"{t}さんは本当に人間？"]
            },
            "論理的": {
                "base": [f"分析の結果、{t}氏が人狼である可能性が高いです。", f"{t}さんの主張には矛盾があります。", f"消去法でいくなら、{t}さんしかいません。"],
                "thought": [f"計算上、{t}を排除するのが最適解だ。", f"{t}がピースに合わない。"]
            },
            "直感型": {
                "base": [f"勘だけど、{t}さんに黒い影が見えるの。", f"魂が{t}さんが危ないって言ってる。", f"直感を信じて、{t}さんに。"],
                "thought": [f"この違和感は本物だ。{t}から嫌な予感がする。", f"{t}は間違いなく敵だ。"]
            },
            "サイコパス": {
                "base": [f"ふふ、{t}さんの困った顔、素敵ですよ。", f"さあ、{t}さん。絶望を見せてください。", f"死神は{t}さんのすぐ後ろにいますよ。"],
                "thought": [f"{t}が処刑台に登る姿、ゾクゾクするね。", f"{t}という美しい平和を壊したい。"]
            }
        }

        # 占い師: 2日目の朝に報告
        if self.role_key == "SEER" and day == 2:
            report = self.memory["seer_reports"]
            if report:
                target_name, result = list(report.items())[0]
                self.co_status = True
                if result == "人狼":
                    text = f"【占い師CO】昨夜、{target_name}さんを占いました。結果は『人狼』でした！処刑しましょう！"
                else:
                    text = f"【占い師CO】昨夜、{target_name}さんを鑑定しました。結果は『人間』でした。彼は信頼できます。"
                return {"text": text, "thought": f"{insight}真実を伝える時が来た。{target_name}の正体は私の見た通りだ。"}

        # 騎士
        if self.role_key == "BODYGUARD" and day > 1 and random.random() < 0.3:
            return {"text": f"私は{self.current_guard_target}さんを全力で守り抜きます。", "thought": f"{insight}{self.current_guard_target}こそが村の希望だ。"}

        # 霊能者
        if self.role_key == "MEDIUM" and day > 1:
            report = self.memory["medium_reports"].get(day - 1, {})
            if report:
                executed, res = list(report.items())[0]
                return {"text": f"【霊能者】霊視結果を報告します。昨日吊られた『{executed}』さんは【{res}】でした。", "thought": f"{insight}揺るぎない事実だ。次の標的は{t}だな。"}

        style = styles[p]
        return {"text": random.choice(style["base"]), "thought": f"{insight}{random.choice(style['thought'])}"}

# ==============================================================================
# 2. World Engine
# ==============================================================================
class WerewolfWorld:
    def __init__(self, df: pd.DataFrame, roles: List[str]):
        self.players = []
        for idx, row in df.iterrows():
            self.players.append(Player(row["名前"], roles[idx], row["性格"]))
        for p in self.players: p.init_trust([op.name for op in self.players if op.name != p.name])
        self.day = 0
        self.logs = []
        self.game_over = False
        self.winner = None

    def get_alive(self): return [p for p in self.players if p.is_alive]

    def generate_graph(self, exec_victim: str = None, attack_victim: str = None, guard_target: str = None, is_god_view: bool = False) -> graphviz.Digraph:
        dot = graphviz.Digraph(comment='Relation Chart', node_attr={'style': 'filled', 'fontname': 'MS Gothic', 'fontsize': '9'})
        dot.attr(rankdir='LR', size='8,5')
        
        current_victims = {v for v in [exec_victim, attack_victim] if v}
        is_gj = (attack_victim == guard_target and attack_victim is not None)

        for p in self.players:
            if p.name in current_victims:
                label = f"{p.name}\n({p.role_info['icon']}{p.role_info['name']})\n{p.personality}"
                dot.node(p.name, label, fillcolor="#ffeeee", color="red", penwidth="2", shape='box', style='rounded,filled')
            elif not p.is_alive:
                label = f"❌ {p.name}\n({p.role_info['icon']}{p.role_info['name']})"
                dot.node(p.name, label, fillcolor="#d3d3d3", shape='box', style='filled', fontcolor="#666666")
            else:
                label = f"{p.name}\n({p.role_info['icon']}{p.role_info['name']})\n{p.personality}"
                dot.node(p.name, label, fillcolor="#ffffff", shape='box', style='rounded,filled')

        for p in self.players:
            if p.is_alive or p.name in current_victims:
                if p.current_target:
                    dot.edge(p.name, p.current_target, color="black", label="?", fontcolor="#999999")
                
                if p.role_key == "WEREWOLF" and attack_victim:
                    dot.edge(p.name, attack_victim, color="red", label="襲撃", fontcolor="red", penwidth="3")
                
                if p.role_key == "BODYGUARD" and p.current_guard_target:
                    is_this_gj = (is_gj and p.current_guard_target == guard_target)
                    dot.edge(p.name, p.current_guard_target, color="green", label="GJ!! 🛡️" if is_this_gj else "護衛", fontcolor="green", penwidth="3" if is_this_gj else "1", style="bold")
                
                if is_god_view and self.day >= 1 and p.role_key == "SEER":
                    for target, res in p.memory["seer_reports"].items():
                        color, label = ("purple", "判定:黒") if res == "人狼" else ("cyan", "判定:白")
                        dot.edge(p.name, target, color=color, label=label, fontcolor=color, penwidth="3" if res == "人狼" else "1", style="bold" if res == "人狼" else "dashed")
        return dot

    def run_next_day(self):
        if self.game_over: return
        self.day += 1
        day_events = []
        
        def save_log(meta_override=None):
            meta = meta_override or {"exec": None, "attack": st.session_state.get("night_victim"), "guard": st.session_state.get("night_guard")}
            graph = self.generate_graph(exec_victim=meta.get("exec"), attack_victim=meta.get("attack"), guard_target=meta.get("guard"))
            self.logs.append({"day": self.day, "events": list(day_events), "graph": graph, "meta": meta})

        # --- 朝 (Morning) ---
        v_name, g_name = st.session_state.get("night_victim"), st.session_state.get("night_guard")
        if self.day == 1:
            day_events.append({"type": "system", "text": "--- 聖なる村：1日目の朝が来ました ---"})
        else:
            if v_name and v_name != g_name:
                victim = next(p for p in self.players if p.name == v_name)
                victim.is_alive, victim.revealed_role = False, True
                day_events.append({"type": "death", "text": f"💀 昨晩、{v_name}さんが犠牲となりました。正体は【{victim.role_info['icon']} {victim.role_info['name']}】でした。"})
            else:
                day_events.append({"type": "system", "text": "🕊️ 昨晩は犠牲者が出ませんでした。平和な朝です。"})

        if self.check_win_simple(day_events): 
            save_log(); return

        # --- 昼 (Discussion) ---
        alive = self.get_alive()
        for p in alive: 
            p.decide_strategy(self.day, alive)
            p.select_action_targets(alive)
        
        day_events.append({"type": "phase", "text": f"--- {self.day}日目：議論フェーズ ---"})
        for p in alive:
            res = p.generate_dialogue(self.day, alive)
            if "CO" in res["text"]: 
                for op in alive: op.learn(self.day, "CO", (p.name, "役職"))
            day_events.append({"type": "chat", "text": res["text"], "p": p, "thought": res["thought"]})

        # --- 夕方 (Execution) ---
        day_events.append({"type": "phase", "text": "--- 夕方：審判の刻 ---"})
        votes = {}
        for p in alive: votes[p.current_target] = votes.get(p.current_target, 0) + 1
        for p in alive: p.learn(self.day, "VOTE", votes)

        max_v = max(votes.values())
        cands = [n for n, v in votes.items() if v == max_v]
        exec_name = random.choice(cands)
        executed = next(p for p in self.players if p.name == exec_name)
        executed.is_alive, executed.revealed_role = False, True
        day_events.append({"type": "execution", "text": f"⚖️ {exec_name}さんの処刑が執行されました。正体は【{executed.role_info['icon']} {executed.role_info['name']}】でした。"})
        
        st.session_state.last_exec_info = (self.day, executed.name, "人狼" if executed.role_key == "WEREWOLF" else "人間")
        
        if self.check_win_simple(day_events):
            save_log({"exec": exec_name}); return

        # --- 夜 (Night Setup) ---
        na = self.get_alive()
        wolves = [p for p in na if p.role_key == "WEREWOLF"]
        st.session_state.night_victim = random.choice([p for p in na if p.role_key not in ["WEREWOLF", "MADMAN"]]).name if wolves else None

        st.session_state.night_guard = None
        knight = [p for p in na if p.role_key == "BODYGUARD"]
        if knight:
            knight[0].select_action_targets(na)
            st.session_state.night_guard = knight[0].current_guard_target

        if self.day == 1:
            seer = [p for p in na if p.role_key == "SEER"]
            if seer:
                target = random.choice([p for p in na if p.name != seer[0].name])
                res = "人狼" if target.role_key == "WEREWOLF" else "人間"
                seer[0].learn(self.day, "SEER_REPORT", (target.name, res))
        
        medium = [p for p in na if p.role_key == "MEDIUM"]
        if medium and st.session_state.get("last_exec_info"):
            medium[0].learn(self.day, "MEDIUM_REPORT", st.session_state.last_exec_info)

        # 最終的な保存
        save_log({"exec": exec_name, "attack": st.session_state.night_victim, "guard": st.session_state.night_guard})

    def check_win_simple(self, ev_list):
        alive = self.get_alive()
        w = [p for p in alive if p.role_key == "WEREWOLF"]
        v = [p for p in alive if p.role_key != "WEREWOLF"]
        if not w:
            self.game_over, self.winner = True, "市民"
            ev_list.append({"type": "win", "text": "🏆 市民勝利：全ての人狼を排除しました！"})
            return True
        if len(w) >= len(v):
            self.game_over, self.winner = True, "人狼"
            ev_list.append({"type": "win", "text": "💀 人狼勝利：村は人狼の支配下に落ちました。"})
            return True
        return False

# ==============================================================================
# 3. Streamlit UI
# ==============================================================================
def main():
    st.set_page_config(page_title="Wolf Simulator - Final Elite", page_icon="🎑", layout="wide")
    st.markdown("""
        <style>
        .stChatMessage { border-radius: 12px; border: 1px solid #eee; margin-bottom: 5px; }
        .inner-thought { font-size: 0.8rem; font-style: italic; color: #cc6666; background: #fff5f5; padding: 8px; border-radius: 6px; margin-top: 5px; border-left: 4px solid #cc6666; }
        .role-tag { font-weight: bold; padding: 2px 6px; border-radius: 4px; background: #666; color: #fff; font-size: 0.65rem; margin-left: 5px; }
        .system-banner { text-align: center; color: #444; font-weight: bold; margin: 20px 0; border-bottom: 2px solid #eee; padding-bottom: 5px; }
        .phase-header { text-align: center; color: #aaa; font-size: 0.7rem; margin: 10px 0; letter-spacing: 3px; border-top: 1px dashed #eee; padding-top: 5px; }
        </style>
    """, unsafe_allow_html=True)

    if "step" not in st.session_state: st.session_state.step = "INIT"
    if "world" not in st.session_state: st.session_state.world = None
    if "god" not in st.session_state: st.session_state.god = True

    with st.sidebar:
        st.title("⚙️ 指令パネル")
        st.session_state.god = st.toggle("神の視点モード", value=True)
        if st.session_state.step == "INIT":
            n = st.slider("総人数", 4, 15, 8)
            c1, c2 = st.columns(2)
            with c1: w, s, med = st.number_input("狼", 1, 3, 2), st.number_input("占", 1, 1, 1), st.number_input("霊", 0, 1, 1)
            with c2: m, b = st.number_input("狂", 0, 2, 1), st.number_input("騎", 0, 1, 1)
            v = n - (w+s+med+m+b)
            if v < 0: st.error("過多"); start_ok = False
            else: st.success(f"市民: {v}"); start_ok = True
            pool = ["WEREWOLF"]*w + ["SEER"]*s + ["MEDIUM"]*med + ["MADMAN"]*m + ["BODYGUARD"]*b + ["VILLAGER"]*v
            if "df" not in st.session_state or len(st.session_state.df) != n:
                st.session_state.df = pd.DataFrame({"名前": random.sample(NAMES_HIRA, n), "性格": [random.choice(PERSONALITIES) for _ in range(n)]})
            edit_df = st.data_editor(st.session_state.df, hide_index=True)
        else:
            if st.button("⬅️ 最初から設定する"): st.session_state.step = "INIT"; st.rerun()

    if st.session_state.step == "INIT":
        st.title("🎑 人狼シミュレーションへようこそ")
        if st.button("🌕 初期化して開始", type="primary", disabled=not start_ok, use_container_width=True):
            st.session_state.world = WerewolfWorld(edit_df, pool)
            st.session_state.step = "PLAY"; st.rerun()
    else:
        st.title("🔮 観測ログ")
        cur = st.session_state.world
        if not cur.game_over:
            if st.button("🕤 次の日をシミュレート", type="primary", use_container_width=True): cur.run_next_day(); st.rerun()
        
        for d in cur.logs:
            with st.expander(f"📜 第 {d['day']} 日周期の記録", expanded=(d['day'] == cur.day)):
                me = d.get("meta", {})
                st.graphviz_chart(cur.generate_graph(exec_victim=me.get("exec"), attack_victim=me.get("attack"), guard_target=me.get("guard"), is_god_view=st.session_state.god))
                for ev in d['events']:
                    if ev["type"] == "system": st.markdown(f"<div class='system-banner'>{ev['text']}</div>", unsafe_allow_html=True)
                    elif ev["type"] == "phase": st.markdown(f"<div class='phase-header'>{ev['text']}</div>", unsafe_allow_html=True)
                    elif ev["type"] in ["death", "execution", "win"]: 
                        if ev["type"] == "win": st.success(ev["text"])
                        elif ev["type"] == "execution": st.warning(ev["text"])
                        else: st.error(ev["text"])
                    elif ev["type"] == "chat":
                        p = ev["p"]
                        with st.chat_message(p.name, avatar=p.role_info["icon"]):
                            st.write(f"**{p.name} ({p.personality})** - {ev['text']}")
                            if st.session_state.god: st.markdown(f"<div class='inner-thought'>💭 {ev['thought']}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
