import requests

def get_jenkins_build_log(job, build):
    url = f"http://http://localhost:8080/job/{job}/{build}/consoleText"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch logs: {response.status_code}")
    

from langchain_core.tools import tool
@tool
def jenkins_log_tool(job: str, build: str):
    """Fetches Jenkins build logs"""
    return get_jenkins_build_log(job, build)


