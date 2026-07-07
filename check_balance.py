with open(r"c:\Users\indra\Desktop\modelens\modelens\app\dashboard\campaigns\page.jsx", "r", encoding="utf-8") as f:
    code = f.read()

idx = 0
in_tag = False
tag_string_char = None
tag_content = []
line_no = 1
brace_depth = 0
in_tag_backtick = False

tags = []

while idx < len(code):
    char = code[idx]
    if char == '\n':
        line_no += 1

    if in_tag:
        if tag_string_char:
            if char == tag_string_char:
                tag_string_char = None
            tag_content.append(char)
        elif in_tag_backtick:
            if char == '`':
                in_tag_backtick = False
            tag_content.append(char)
        elif char in ('"', "'"):
            tag_string_char = char
            tag_content.append(char)
        elif char == '`':
            in_tag_backtick = char
            tag_content.append(char)
        elif char == '{':
            brace_depth += 1
            tag_content.append(char)
        elif char == '}':
            brace_depth -= 1
            tag_content.append(char)
        elif char == '>' and brace_depth == 0:
            in_tag = False
            tag_str = "".join(tag_content)
            tag_str_stripped = tag_str.strip()
            is_closing = tag_str_stripped.startswith('/')
            is_self_closing = tag_str_stripped.endswith('/')
            
            cleaned = tag_str_stripped[1:] if is_closing else tag_str_stripped
            cleaned = cleaned[:-1] if is_self_closing else cleaned
            parts = cleaned.strip().split()
            tag_name = parts[0] if parts else ""
            
            if tag_name and (tag_name[0].isupper() or tag_name.islower() or '.' in tag_name):
                tags.append((tag_name, is_closing, is_self_closing, line_no))
            
            tag_content = []
        else:
            tag_content.append(char)
    else:
        # Detect tag start
        if char == '<' and idx + 1 < len(code) and (code[idx+1].isalpha() or code[idx+1] in ('/', '!')):
            if code[idx+1] == '!':
                idx += 1
                continue
            in_tag = True
            tag_content = []
            brace_depth = 0
            tag_string_char = None 
            in_tag_backtick = False
            
    idx += 1

print(f"Total tags found: {len(tags)}")

# Now run tag balance matching
stack = [] 
for tag_name, is_closing, is_self_closing, l in tags:
    if is_self_closing:
        continue
    if is_closing: 
        if not stack:
            print(f"Error: unexpected closing </{tag_name}> at line {l}")
        else: 
            last_tag, last_line = stack.pop()
            if last_tag != tag_name:
                print(f"Error: mismatched closing </{tag_name}> at line {l}. Expected matching for <{last_tag}> from line {last_line}")
                stack.append((last_tag, last_line))
    else:
        stack.append((tag_name, l))

print("Remaining open tags in stack:", len(stack))
for item in stack:
    print(item)

    