with open('dashboard.py', encoding='utf-8') as f:
    lines = f.readlines()

# 找到断行的 value="\n 并合并成正确的一行
i = 0
new_lines = []
while i < len(lines):
    line = lines[i]
    # 检测断裂的 value="\n (下一行以 ".join 开头)
    if line.rstrip('\n').endswith('value="') and i + 1 < len(lines) and lines[i+1].lstrip().startswith('".join('):
        next_line = lines[i+1].lstrip()
        indent = line[: len(line) - len(line.lstrip())]
        new_lines.append(indent + 'value="\\n".join(' + next_line.split('".join(', 1)[1])
        i += 2
    else:
        new_lines.append(line)
        i += 1

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Done. Total lines: {len(new_lines)}")
