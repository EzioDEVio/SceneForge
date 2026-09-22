import importlib.util, pathlib, tempfile
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('auto_images',root/'scripts/auto_images.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp);(p/'webui-user.bat').write_text('@echo off')
    fake_os=SimpleNamespace(name='nt',environ={'SCENEFORGE_SD_DIR':tmp})
    with patch.object(m,'os',fake_os),patch.object(m,'ready',side_effect=[False,True]),patch.object(m.socket,'create_connection',side_effect=OSError),patch.object(m.subprocess,'CREATE_NO_WINDOW',0,create=True),patch.object(m.subprocess,'Popen') as launch:
        m.main();assert launch.call_count==1
        assert launch.call_args.args[0]==['cmd.exe','/d','/c','webui-user.bat']
        assert launch.call_args.kwargs['cwd']==tmp
    with patch.object(m,'os',fake_os),patch.object(m,'ready',return_value=True),patch.object(m.subprocess,'Popen') as launch:
        m.main();launch.assert_not_called()
    fake_os.environ['SCENEFORGE_SD_AUTOSTART']='0'
    with patch.object(m,'os',fake_os),patch.object(m.subprocess,'Popen') as launch:
        m.main();launch.assert_not_called()
print('PASS Windows launcher invocation, existing ready service and opt-out (mocked Windows process)')
