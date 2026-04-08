"""MRK1 — UPSC failure / life-reset script (6 clips, Hindi/Hinglish).

Used in test_pipeline.py as a real-world integration test corpus.
"""

# Full 6-clip script as delivered to the pipeline
SAMPLE_SCRIPT_MRK1 = """
Teen attempt ho gaye. Prelims clear nahi hua.
Gharwale bol rahe hain, chhod de ya shaadi kar le.
Main log kya sochenge, woh sab sochti rahi.

Ek raat Rishika didi ki video dekhi.
Unhone bola, ek baar apne aap se poocho —
kya ye sirf UPSC hai, ya kuch aur bhi hai?

Woh sawaal mere andar ghus gaya.
Main honestly baith gayi apne aap ke saath.
Aur pehli baar roya bhi, aur samjhi bhi.

Rishika didi ne kaha, pehle neend theek karo.
Baki sab baad mein. Maine try kiya.
Ek hafte mein fark dikh gaya.

Abhi bhi uncertain hoon career mein.
Lekin andar se ek zyada sthirta aa gayi hai.
Yeh meri life hai, main decide karungi.

SuperLiving pe Rishika didi ke saath baat karo.
Pehla session free hai.
Sirf apne liye ek kadam uthao.
""".strip()

# 4-clip version for faster tests
SAMPLE_SCRIPT_MRK1_SHORT = """
Teen attempt ho gaye, prelims clear nahi hua.
Gharwale bol rahe hain, chhod de ya shaadi kar le.

Rishika didi ki ek video ne sawaal diya —
kya ye sirf UPSC hai, ya kuch aur bhi hai?

Woh sawaal mere andar ghus gaya.
Maine pehli baar khud se honestly baat ki.

Andar se ek sthirta aa gayi hai.
SuperLiving pe Rishika didi ke saath pehla session free hai.
""".strip()

# Coach used in both scripts
SAMPLE_COACH = "Rishika"
