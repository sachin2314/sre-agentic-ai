def safe_tool_wrapper(tool_func, *args, **kwargs):
        forbidden = ["delete", "drop", "remove", "shutdown", "restart", "terminate", "kill", "stop", "format", "wipe", "destroy"]
        for arg in args: 
            if any(f in str(arg).lower() for f in forbidden):
                 return "Blocked: Forbidden operation detected."
        return tool_func(*args, **kwargs)