import os
import glob

folders = [
    r"e:\Tool\movie_ai_tool",
    r"e:\Tool\movie_ai_tool_1",
    r"e:\Tool\movie_ai_tool_2"
]

for folder in folders:
    app_dir = os.path.join(folder, "app")
    for filepath in glob.glob(os.path.join(app_dir, "**", "*.py"), recursive=True):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        orig_content = content
        content = content.replace("subprocess.run(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000), ", "subprocess.run(")
        content = content.replace("subprocess.Popen(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000), ", "subprocess.Popen(")
        
        if content != orig_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed SyntaxError in: {filepath}")

print("Syntax errors reverted!")
