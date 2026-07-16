import os

path = 'src/pages/CompetitorMatcher.jsx'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

repls = [
    ('from-indigo-500 to-purple-600', 'from-[#059669] to-[#047857]'),
    ('from-indigo-600/30 to-purple-600/30', 'from-[#059669]/10 to-[#047857]/10'),
    ('text-indigo-400', 'text-emerald-400'),
    ('border-indigo-500/20', 'border-[#059669]/20'),
    ('hover:border-indigo-500/40', 'hover:border-[#059669]/40'),
    ('bg-indigo-500/10', 'bg-[#059669]/10'),
    ('text-indigo-300', 'text-[#10b981]'),
    ('bg-purple-500/10 text-purple-300 border border-purple-500/20', 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'),
    ('bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500', 'bg-[#212121] hover:bg-[#333]'),
    ('shadow-indigo-600/20', 'shadow-black/20'),
    ('bg-indigo-500/15', 'bg-[#059669]/20'),
    ('group-hover:text-indigo-400', 'group-hover:text-emerald-400'),
    ('bg-indigo-500/20 border-t-indigo-400', 'border-[#059669]/20 border-t-[#10b981]'),
    ('text-indigo-400 animate-pulse', 'text-emerald-400 animate-pulse'),
    ('text-indigo-300 font-mono', 'text-[#10b981] font-mono'),
    ('hover:border-indigo-500/50', 'hover:border-[#059669]/50'),
    ('focus:border-indigo-500/50', 'focus:border-[#059669]/50'),
    ('hover:bg-indigo-500/10', 'hover:bg-[#059669]/10'),
    ('selectedProduct?.id === p.id ? "bg-indigo-500/15"', 'selectedProduct?.id === p.id ? "bg-[#059669]/20"')
]
for old, new in repls:
    c = c.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated colors successfully')
