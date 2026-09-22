"""Frozen backend entrypoint. Bind an OS-selected loopback port; exit with the shell."""
import json,os,socket,sys,threading,time

def main():
    if len(os.environ.get('SCENEFORGE_DESKTOP_TOKEN',''))<32:
        raise RuntimeError('Desktop backend requires a per-launch authentication token.')
    import uvicorn
    from app.main import app
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(('127.0.0.1',0));sock.listen(128)
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',access_log=False,loop='asyncio',http='h11',ws='none'))
    def announce():
        while not server.started and not server.should_exit:time.sleep(.05)
        if server.started:print('SCENEFORGE_READY '+json.dumps({'port':port}),flush=True)
    def parent_closed():
        # Electron holds stdin open for the lifetime of its owned backend.
        sys.stdin.buffer.read();server.should_exit=True
    threading.Thread(target=announce,daemon=True).start()
    threading.Thread(target=parent_closed,daemon=True).start()
    try:server.run(sockets=[sock])
    finally:sock.close()
if __name__=='__main__':main()
