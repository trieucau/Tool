Set WshShell = CreateObject("WScript.Shell")

' Launch App 1 (CPU) - Direct Python execution for maximum speed
WshShell.CurrentDirectory = "E:\Tool\movie_ai_tool_1"
WshShell.Run """E:\Tool\movie_ai_tool_1\venv\Scripts\pythonw.exe"" main.py", 0, False

' Launch App 2 (CPU) - Direct Python execution for maximum speed
WshShell.CurrentDirectory = "E:\Tool\movie_ai_tool_2"
WshShell.Run """E:\Tool\movie_ai_tool_2\venv\Scripts\pythonw.exe"" main.py", 0, False

' Launch App 0 (GPU) - Add CUDA DLLs to PATH for GPU acceleration, then execute directly
WshShell.CurrentDirectory = "E:\Tool\movie_ai_tool"
env_path = WshShell.Environment("Process").Item("PATH")
nv_base = "E:\Tool\movie_ai_tool\venv\Lib\site-packages\nvidia\"
cuda_path = nv_base & "cublas\bin;" & nv_base & "cuda_runtime\bin;" & nv_base & "cuda_nvrtc\bin;" & nv_base & "cudnn\bin;" & nv_base & "cufft\bin;" & nv_base & "curand\bin;" & nv_base & "cusolver\bin;" & nv_base & "cusparse\bin;"
WshShell.Environment("Process").Item("PATH") = cuda_path & env_path
WshShell.Run """E:\Tool\movie_ai_tool\venv\Scripts\pythonw.exe"" main.py", 0, False
