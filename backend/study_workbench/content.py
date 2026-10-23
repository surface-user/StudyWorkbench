"""M0 fixtures, explicitly not official examination questions."""
DEMO = {
    "schema_version": 1, "id": "demo-integral", "revision": 1,
    "subject": "数学一/高等数学", "kind": "single_choice",
    "stem": [{"type": "text", "text": "计算下列积分（人工演示题）"},
             {"type": "latex", "tex": r"\int_0^1 x^2\,dx", "display": True}],
    "options": [{"id": "a", "content": [{"type": "latex", "tex": r"\frac{1}{3}"}]},
                {"id": "b", "content": [{"type": "latex", "tex": r"\frac{1}{2}"}]}],
    "answer": {"selected": ["a"]},
    "explanation": [{"type": "latex", "tex": r"[x^3/3]_0^1=1/3", "display": True}],
    "knowledge_points": ["定积分"],
    "source": {"kind": "manual", "title": "M0 演示，非真题", "verification": "unverified"},
}
SUBJECTIVE = {**DEMO, "id": "demo-proof", "kind": "subjective", "options": [],
              "stem": [{"type": "text", "text": "说明上述积分的计算过程。"}],
              "answer": {"rubric": "说明原函数与上下限代入。"}}
