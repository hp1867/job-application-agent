"""Exercise the installed AIHawk MCP server without opening a browser or job site."""
import asyncio, importlib.metadata, json, os, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def check():
    import aihawk
    runtime=Path(sys.executable).resolve().parent.parent
    # Do not inherit job-agent secrets or load its .env in the MCP subprocess.
    names={'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','USERPROFILE','APPDATA','LOCALAPPDATA','PROGRAMDATA','COMSPEC'}
    environment={k:v for k,v in os.environ.items() if k.upper() in names}
    params=StdioServerParameters(command=sys.executable,args=['-m','aihawk'],cwd=str(runtime),env=environment)
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=await session.list_tools()
            names=sorted(tool.name for tool in result.tools)
    expected={'browser_navigate','browser_snapshot','browser_type','browser_click'}
    if not expected.issubset(names):raise RuntimeError('Installed AIHawk browser contract is missing required tools')
    return {'result':'PASS','aihawk_version':importlib.metadata.version('aihawk'),
            'package_path':str(Path(aihawk.__file__).resolve()),'python':sys.executable,
            'mcp_tools':names,'browser_tools_invoked':0,'employer_pages_opened':0,
            'submitted':False,'scope':'Real installed AIHawk MCP initialization and tool discovery only'}

if __name__=='__main__':print(json.dumps(asyncio.run(asyncio.wait_for(check(),60)),indent=2))
