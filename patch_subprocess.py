import os
import glob

folders = [
    r"e:\Tool\movie_ai_tool",
    r"e:\Tool\movie_ai_tool_1",
    r"e:\Tool\movie_ai_tool_2"
]

for folder in folders:
    app_dir = os.path.join(folder, "app")
    for root, dirs, files in os.walk(app_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if ("subprocess.run(" in content or "subprocess.Popen(" in content) and "CREATE_NO_WINDOW" not in content:
                    # Make sure subprocess is imported
                    if "import subprocess" not in content:
                        content = "import subprocess\n" + content
                    
                    # Safe replacement
                    content = content.replace("subprocess.run(", "subprocess.run(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000), ")
                    content = content.replace("subprocess.Popen(", "subprocess.Popen(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000), ")
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"Patched: {filepath}")

print("All files patched successfully!")
